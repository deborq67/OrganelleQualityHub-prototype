import csv
import io
import json
import os
import time
from multiprocessing import Pool

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

BATCH_SIZE = 5000  # How many rows before upload.
DEFAULT_WORKERS   = 2  # Safe default for small boards; override with --workers on bigger hardware
DEFAULT_CHUNKSIZE = 50  # Cap so results trickle back often enough to hit the batch flush size above


def parse_file(args):
    accession, filepath = args
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    django.setup()
    from pipelines.parsers.genome_operations import GenomeOperations
    try:
        return accession, GenomeOperations(filepath).gene_list(), None
    except Exception as e:
        return accession, None, str(e)


class Command(BaseCommand):
    help = 'One-off: backfills gene_list on existing OrganelleMetadata rows from their GenBank files.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Files per worker task (default: auto, capped at {DEFAULT_CHUNKSIZE}).')
        parser.add_argument('--limit', type=int, default=None,
                            help='Process at most N rows (useful for testing storage impact before a full run).')

    def handle(self, *args, **options):
        from apps.organelle_quality.models import OrganelleMetadata

        gb_dirs = [os.path.join(settings.GENBANK_ROOT, d) for d in ('plastid_files', 'mitochondrial_files')]
        gb_dirs = [d for d in gb_dirs if os.path.isdir(d)]
        if not gb_dirs:
            raise CommandError('Neither "plastid_files" nor "mitochondrial_files" could be found.')

        file_by_accession = {
            os.path.splitext(e.name)[0]: e.path
            for gb_dir in gb_dirs for e in os.scandir(gb_dir) if e.name.endswith('.gb')
        }

        pending = set(OrganelleMetadata.objects.filter(gene_list__isnull=True).values_list('accession', flat=True))
        if not pending:
            raise CommandError('No OrganelleMetadata rows need backfilling.')

        to_process = [(acc, file_by_accession[acc]) for acc in pending if acc in file_by_accession]
        missing_files = len(pending) - len(to_process)
        if not to_process:
            raise CommandError('None of the pending accessions have a matching GenBank file.')

        if options['limit']:
            to_process = to_process[:options['limit']]

        self.stdout.write(f'{len(to_process)} row(s) to backfill '
                           f'({missing_files} pending row(s) have no matching .gb file).')

        n_workers = options['workers'] or DEFAULT_WORKERS
        chunksize = options['chunksize'] or max(1, min(DEFAULT_CHUNKSIZE, len(to_process) // (n_workers * 4)))

        # Closes DB connections first so worker processes do not share one by accident.
        connections.close_all()

        db = connections['supabase']
        updated = failed = 0
        batch = []

        def flush():
            nonlocal updated, batch
            if not batch:
                return
            buf = io.StringIO()
            writer = csv.writer(buf)
            for accession, gene_list in batch:
                writer.writerow([accession, json.dumps(gene_list)])

            # Retries on a fresh connection since the pooler can drop the old one mid-run.
            for attempt in range(1, 4):
                try:
                    buf.seek(0)
                    with db.cursor() as cursor:
                        cursor.execute(
                            'CREATE TEMP TABLE IF NOT EXISTS gene_list_staging '
                            '(accession varchar(50), gene_list jsonb)')
                        cursor.execute('TRUNCATE gene_list_staging')
                        cursor.copy_expert(
                            "COPY gene_list_staging (accession, gene_list) FROM STDIN WITH (FORMAT csv)", buf)
                        cursor.execute('''
                            UPDATE organism_metadata_organellemetadata AS t
                            SET gene_list = s.gene_list
                            FROM gene_list_staging AS s
                            WHERE t.accession = s.accession
                        ''')
                    break
                except OperationalError as e:
                    self.stdout.write(self.style.WARNING(
                        f'  DB connection dropped ({e}); reconnecting (attempt {attempt}/3)'))
                    db.close()
                    time.sleep(2)
            else:
                raise CommandError('DB connection kept failing after 3 retries.')

            updated += len(batch)
            self.stdout.write(self.style.SUCCESS(f'  wrote {len(batch)} row(s) ({updated} total)'))
            batch = []

        with Pool(processes=n_workers) as pool:
            for accession, gene_list, error in pool.imap_unordered(parse_file, to_process, chunksize=chunksize):
                if error:
                    failed += 1
                    self.stdout.write(self.style.WARNING(f'  {accession} failed: {error}'))
                    continue
                batch.append((accession, gene_list))
                if len(batch) >= BATCH_SIZE:
                    flush()

        flush()

        self.stdout.write(self.style.SUCCESS(
            f'Done. Backfilled {updated} row(s), {failed} failed, {missing_files} skipped (no file).'
        ))

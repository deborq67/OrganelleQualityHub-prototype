import os
from multiprocessing import Pool

import polars as pl
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

BATCH_SIZE = 1000
DEFAULT_WORKERS   = 2  # safe default for small boards (e.g. Pi 3B+); override with --workers on bigger hardware
DEFAULT_CHUNKSIZE = 50  # cap so results trickle back often enough to hit the batch flush size above


# Separate function for parsing needed for multiprocessing to work.
def parse_file(filepath):
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    django.setup()
    from pipelines.analyses.ir_operations import IROperations
    try:
        return IROperations(filepath).info
    except Exception as e:
        print(f"FAILED {filepath}: {e}")
        return None


class Command(BaseCommand):
    help = 'Processes all GB files and saves IR Identification.'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--update",
            "-u",
            action="store_true",
            help="Updates duplicates instead of ignoring them.",
        )
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Files per worker task. Smaller = more frequent DB flushes and '
                                 f'less work lost on a crash; larger = less IPC overhead on fast/many-core '
                                 f'hardware (default: auto, capped at {DEFAULT_CHUNKSIZE}).')

    def _flush(self, rows, update):
        from apps.inverted_repeats.models import IR_Identification
        if not rows:
            return 0
        records = [
            IR_Identification(
                accession=row['ACCESSION'],
                title=row['TITLE'],
                updated=row['UPDATED'],
                ir_reported=row['IR_REPORTED'],
                ira_reported=row['IRa_REPORTED'],
                ira_reported_start=row['IRa_REPORTED_START'],
                ira_reported_end=row['IRa_REPORTED_END'],
                ira_reported_length=row['IRa_REPORTED_LENGTH'],
                irb_reported=row['IRb_REPORTED'],
                irb_reported_start=row['IRb_REPORTED_START'],
                irb_reported_end=row['IRb_REPORTED_END'],
                irb_reported_length=row['IRb_REPORTED_LENGTH'],
            )
            for row in pl.concat(rows).to_dicts()
        ]
        if update:
            IR_Identification.objects.bulk_create(
                records,
                batch_size=1000,
                update_conflicts=True,
                unique_fields=['accession'],
                update_fields=[
                    'title',
                    'updated',
                    'checked',
                    'ir_reported',
                    'ira_reported',
                    'ira_reported_start',
                    'ira_reported_end',
                    'ira_reported_length',
                    'irb_reported',
                    'irb_reported_start',
                    'irb_reported_end',
                    'irb_reported_length'
                ]
            )
        else:
            IR_Identification.objects.bulk_create(
                records,
                batch_size=1000,
                ignore_conflicts=True
            )
        self.stdout.write(self.style.SUCCESS(f'  wrote {len(records)} entries'))
        return len(records)

    def handle(self, *args, **options):
        genbank_dir = os.path.join(settings.GENBANK_ROOT, 'plastid_files')
        if not os.path.exists(genbank_dir):
            raise CommandError(
                'The "plastid_files" directory can not be found. '
                'Make sure it is on the same level as manage.py.'
            )

        from apps.inverted_repeats.models import IR_Identification
        file_list = [
            file.path
            for file in os.scandir(genbank_dir)
            if file.name.endswith(".gb")
        ]

        # Ignore duplicates by default.
        if not options["update"]:
            current_records = set(IR_Identification.objects.values_list('accession', flat=True))
            file_list = [
                f for f in file_list
                if os.path.splitext(os.path.basename(f))[0]
                not in current_records
            ]
            if not file_list:
                raise CommandError(
                    'No .gb files found in the "plastid_files" directory.'
                )
        self.stdout.write(f'{len(file_list)} new files to process.')
        self.stdout.write('Processing...')

        n_workers = options['workers'] or DEFAULT_WORKERS

        # imap_unordered streams results instead of holding every parsed file in
        # memory (pool.map would) — needed on low-memory hardware like a Pi. The
        # DEFAULT_CHUNKSIZE cap keeps flushes frequent and bounds crash loss;
        # pass --chunksize to override.
        chunksize = options['chunksize'] or max(1, min(DEFAULT_CHUNKSIZE, len(file_list) // (n_workers * 4)))

        self.stdout.write(f'Using {n_workers} worker process(es), chunksize={chunksize}.')
        batch, written = [], 0

        with Pool(processes=n_workers) as pool:
            for result in pool.imap_unordered(parse_file, file_list, chunksize=chunksize):
                if result is None:
                    continue
                batch.append(result)
                if len(batch) >= BATCH_SIZE:
                    written += self._flush(batch, options["update"])
                    batch = []

        written += self._flush(batch, options["update"])

        if written == 0:
            raise CommandError(
                'No files could be processed. Check your .gb files for errors.'
            )

        verb = 'Updated' if options["update"] else 'Wrote'
        self.stdout.write(self.style.SUCCESS(f'{verb} {written} entries total.'))

import json
import os
import time
from multiprocessing import Pool

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Q

from apps.inverted_repeats.models import IR_Identification
from pipelines.analyses.ir_confirm import _check_blast_tools

BATCH_SIZE = 500
DEFAULT_WORKERS   = 2  # safe default for small boards (e.g. Pi 3B+); override with --workers on bigger hardware
DEFAULT_CHUNKSIZE = 50  # cap so results trickle back often enough to hit the batch flush size above

FIELDS = [
    'ira_blastinferred', 'ira_blastinferred_start', 'ira_blastinferred_end', 'ira_blastinferred_length',
    'irb_blastinferred', 'irb_blastinferred_start', 'irb_blastinferred_end', 'irb_blastinferred_length',
    'notes',
]


def blast_accession(args):
    """Worker: run SelfBlasting for one accession. Runs in a subprocess."""
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    django.setup()

    accession, datadir, minlength, maxlength = args
    from pipelines.analyses.ir_confirm import main as ir_main
    return ir_main(accession, datadir, minlength, maxlength)


class Command(BaseCommand):
    help = 'Re-confirms IR positions via self-BLAST, writing results onto IR_Identification.'

    def add_arguments(self, parser):
        parser.add_argument('--update', '-u', action='store_true',
                            help='Re-run and overwrite accessions already confirmed.')
        parser.add_argument('--minlength', '-min', type=int, default=10000,
                            help='Minimum IR length for BLAST filtering (default: 10000).')
        parser.add_argument('--maxlength', '-max', type=int, default=50000,
                            help='Maximum IR length for BLAST filtering (default: 50000).')
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Accessions per worker task. Smaller = more frequent DB flushes and '
                                 f'less work lost on a crash; larger = less IPC overhead on fast/many-core '
                                 f'hardware (default: auto, capped at {DEFAULT_CHUNKSIZE}).')

    def _flush(self, rows):
        if not rows:
            return 0
        records = [
            IR_Identification(
                accession=row['accession'],
                ira_blastinferred=row['ira_blastinferred'],
                ira_blastinferred_start=row['ira_blastinferred_start'],
                ira_blastinferred_end=row['ira_blastinferred_end'],
                ira_blastinferred_length=row['ira_blastinferred_length'],
                irb_blastinferred=row['irb_blastinferred'],
                irb_blastinferred_start=row['irb_blastinferred_start'],
                irb_blastinferred_end=row['irb_blastinferred_end'],
                irb_blastinferred_length=row['irb_blastinferred_length'],
                notes=row['notes'],
            )
            for row in rows
        ]
        try:
            IR_Identification.objects.bulk_create(
                records,
                batch_size=1000,
                update_conflicts=True,
                unique_fields=['accession'],
                update_fields=FIELDS,
            )
        except Exception as e:
            fallback = f'/tmp/ir_confirmation_failed_batch_{int(time.time())}.json'
            with open(fallback, 'w') as f:
                json.dump(rows, f, default=str)
            self.stdout.write(self.style.ERROR(
                f'  DB write failed ({e}); saved {len(rows)} row(s) to {fallback}'
            ))
            return 0
        self.stdout.write(self.style.SUCCESS(f'  wrote {len(rows)} record(s)'))
        return len(rows)

    def handle(self, *args, **options):
        _check_blast_tools()

        datadir = os.path.join(settings.GENBANK_ROOT, 'plastid_files')
        if not os.path.exists(datadir):
            raise CommandError(f'Data directory "{datadir}" not found.')

        accessions = list(IR_Identification.objects.values_list('accession', flat=True))
        if not accessions:
            raise CommandError('No accessions found in IR_Identification.')

        if not options['update']:
            '''Already attempted - either confirmed ira_blastinferred yes or a
            documented failure notes set. A never-attempted row has neither.'''
            attempted = set(IR_Identification.objects.filter(
                Q(ira_blastinferred='yes') | Q(notes__isnull=False)
            ).values_list('accession', flat=True))
            accessions = [a for a in accessions if a not in attempted]
            if not accessions:
                raise CommandError('All accessions already confirmed. Use --update to re-run.')

        self.stdout.write(f'{len(accessions)} accessions to confirm.')
        self.stdout.write('Processing...')

        task_args = [
            (accession, datadir, options['minlength'], options['maxlength'])
            for accession in accessions
        ]

        n_workers = options['workers'] or DEFAULT_WORKERS

        # Streams and writes results in batches to save memory and limit progress lost on a crash.
        chunksize = options['chunksize'] or max(1, min(DEFAULT_CHUNKSIZE, len(task_args) // (n_workers * 4)))

        self.stdout.write(f'Using {n_workers} worker process(es), chunksize={chunksize}.')
        batch, written = [], 0

        with Pool(processes=n_workers) as pool:
            for result in pool.imap_unordered(blast_accession, task_args, chunksize=chunksize):
                batch.append(result)
                if len(batch) >= BATCH_SIZE:
                    written += self._flush(batch)
                    batch = []

        written += self._flush(batch)

        if written == 0:
            raise CommandError('No accessions could be processed.')

        self.stdout.write(self.style.SUCCESS(f'Confirmed {written} accession(s) total.'))

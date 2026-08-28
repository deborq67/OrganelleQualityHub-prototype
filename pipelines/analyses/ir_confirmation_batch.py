"""Re-confirms IR positions via self-BLAST, writing results onto IR_Identification.

Extracted from pipelines/management/commands/ir_confirmation.py so the command
stays a thin CLI wrapper and this logic can be tested/imported independently.
"""
import json
import os
import time
from multiprocessing import Pool

from django.conf import settings
from django.db.models import Q

from apps.inverted_repeats.models import IR_Identification
from pipelines.analyses.ir_confirm import _check_blast_tools
from pipelines.exceptions import PipelineError

BATCH_SIZE = 500
DEFAULT_WORKERS = 2  # safe default for small boards (e.g. Pi 3B+); override with --workers on bigger hardware
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


def _flush(rows, stdout, style):
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
        stdout.write(style.ERROR(
            f'  DB write failed ({e}); saved {len(rows)} row(s) to {fallback}'
        ))
        return 0
    stdout.write(style.SUCCESS(f'  wrote {len(rows)} record(s)'))
    return len(rows)


def run(options, stdout, style):
    """Re-confirms IR positions for pending accessions. Returns the number of records written."""
    _check_blast_tools()

    datadir = os.path.join(settings.GENBANK_ROOT, 'plastid_files')
    if not os.path.exists(datadir):
        raise PipelineError(f'Data directory "{datadir}" not found.')

    accessions = list(IR_Identification.objects.values_list('accession', flat=True))
    if not accessions:
        raise PipelineError('No accessions found in IR_Identification.')

    if not options['update']:
        # Already attempted - either confirmed ira_blastinferred yes or a
        # documented failure notes set. A never-attempted row has neither.
        attempted = set(IR_Identification.objects.filter(
            Q(ira_blastinferred='yes') | Q(notes__isnull=False)
        ).values_list('accession', flat=True))
        accessions = [a for a in accessions if a not in attempted]
        if not accessions:
            raise PipelineError('All accessions already confirmed. Use --update to re-run.')

    stdout.write(f'{len(accessions)} accessions to confirm.')
    stdout.write('Processing...')

    task_args = [
        (accession, datadir, options['minlength'], options['maxlength'])
        for accession in accessions
    ]

    n_workers = options['workers'] or DEFAULT_WORKERS

    # Streams and writes results in batches to save memory and limit progress lost on a crash.
    chunksize = options['chunksize'] or max(1, min(DEFAULT_CHUNKSIZE, len(task_args) // (n_workers * 4)))

    stdout.write(f'Using {n_workers} worker process(es), chunksize={chunksize}.')
    batch, written = [], 0

    with Pool(processes=n_workers) as pool:
        for result in pool.imap_unordered(blast_accession, task_args, chunksize=chunksize):
            batch.append(result)
            if len(batch) >= BATCH_SIZE:
                written += _flush(batch, stdout, style)
                batch = []

    written += _flush(batch, stdout, style)

    if written == 0:
        raise PipelineError('No accessions could be processed.')

    return written

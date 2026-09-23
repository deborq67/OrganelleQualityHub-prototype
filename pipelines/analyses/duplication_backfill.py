"""Backfills duplicate/duplicate_accession on OrganelleMetadata rows by
re-parsing their GenBank files for the "identical to" comment.

Mirrors the structure of gene_list_backfill.py, but uses
duplication_check.find_duplicate_reference() instead of GenomeOperations,
since this only needs the file's COMMENT field, not a full sequence parse.
"""

import csv
import io
import os
import time
from multiprocessing import Pool

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError

from pipelines.exceptions import PipelineError

BATCH_SIZE = 5000
DEFAULT_WORKERS = 2
DEFAULT_CHUNKSIZE = 50


def parse_file(args):
    accession, filepath = args
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    django.setup()
    # Imported after django.setup() so worker processes don't need Django
    # configured at import time, matching gene_list_backfill.py's pattern.
    from pipelines.analyses.duplication_check import find_duplicate_reference

    try:
        _, referenced = find_duplicate_reference(filepath)
        duplicate = "yes" if referenced is not None else "no"
        return accession, duplicate, referenced, None
    except Exception as e:
        return accession, None, None, str(e)


def _flush(db, batch, stdout, style):
    if not batch:
        return 0
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for accession, duplicate, referenced in batch:
        writer.writerow([accession, duplicate, referenced])

    # Retries on a fresh connection since the pooler can drop the old one mid-run.
    for attempt in range(1, 4):
        try:
            buffer.seek(0)
            with db.cursor() as cursor:
                cursor.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS duplication_staging "
                    "(accession varchar(50), duplicate varchar(10), "
                    "duplicate_accession varchar(50))"
                )
                cursor.execute("TRUNCATE duplication_staging")
                cursor.copy_expert(
                    "COPY duplication_staging "
                    "(accession, duplicate, duplicate_accession) "
                    "FROM STDIN WITH (FORMAT csv)",
                    buffer,
                )
                cursor.execute("""
                    UPDATE organism_metadata_organellemetadata AS t
                    SET duplicate = s.duplicate,
                        duplicate_accession = s.duplicate_accession
                    FROM duplication_staging AS s
                    WHERE t.accession = s.accession
                """)
            break
        except OperationalError as e:
            stdout.write(
                style.WARNING(
                    f"  DB connection dropped ({e}); reconnecting (attempt {attempt}/3)"
                )
            )
            db.close()
            time.sleep(2)
    else:
        raise PipelineError("DB connection kept failing after 3 retries.")

    stdout.write(style.SUCCESS(f"  wrote {len(batch)} row(s)"))
    return len(batch)


def run(options, stdout, style):
    """Backfills duplicate/duplicate_accession for pending OrganelleMetadata rows.
    Returns (updated, failed, missing_files)."""
    from apps.organelle_quality.models import OrganelleMetadata

    gb_dirs = [
        os.path.join(settings.GENBANK_ROOT, d)
        for d in ("plastid_files", "mitochondrial_files")
    ]
    gb_dirs = [d for d in gb_dirs if os.path.isdir(d)]
    if not gb_dirs:
        raise PipelineError(
            'Neither "plastid_files" nor "mitochondrial_files" could be found.'
        )

    file_by_accession = {
        os.path.splitext(e.name)[0]: e.path
        for gb_dir in gb_dirs
        for e in os.scandir(gb_dir)
        if e.name.endswith(".gb")
    }

    pending = set(
        OrganelleMetadata.objects.filter(duplicate__isnull=True).values_list(
            "accession", flat=True
        )
    )
    if not pending:
        raise PipelineError("No OrganelleMetadata rows need backfilling.")

    to_process = [
        (acc, file_by_accession[acc]) for acc in pending if acc in file_by_accession
    ]
    missing_files = len(pending) - len(to_process)
    if not to_process:
        raise PipelineError(
            "None of the pending accessions have a matching GenBank file."
        )

    if options.get("limit"):
        to_process = to_process[: options["limit"]]

    stdout.write(
        f"{len(to_process)} row(s) to backfill "
        f"({missing_files} pending row(s) have no matching .gb file)."
    )

    n_workers = options.get("workers") or DEFAULT_WORKERS
    chunksize = options.get("chunksize") or max(
        1, min(DEFAULT_CHUNKSIZE, len(to_process) // (n_workers * 4))
    )

    # Closes DB connections first so worker processes do not share one by accident.
    connections.close_all()

    db = connections["supabase"]
    updated = failed = 0
    batch = []

    with Pool(processes=n_workers) as pool:
        for accession, duplicate, referenced, error in pool.imap_unordered(
            parse_file, to_process, chunksize=chunksize
        ):
            if error:
                failed += 1
                stdout.write(style.WARNING(f"  {accession} failed: {error}"))
                continue
            batch.append((accession, duplicate, referenced))
            if len(batch) >= BATCH_SIZE:
                updated += _flush(db, batch, stdout, style)
                batch = []

    updated += _flush(db, batch, stdout, style)

    return updated, failed, missing_files

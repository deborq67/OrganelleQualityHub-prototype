"""Backfills gene_list and/or longest_ambiguity_stretch on OrganelleMetadata rows by
re-parsing their GenBank files.

Extracted from pipelines/management/commands/backfill_gene_list.py so the command
stays a thin CLI wrapper and this logic can be tested/imported independently.
"""

import csv
import io
import json
import os
import time
from functools import partial, reduce
from multiprocessing import Pool
from operator import or_

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.db.models import Q

from pipelines.exceptions import PipelineError

BATCH_SIZE = 5000  # How many rows before upload.
DEFAULT_WORKERS = (
    2  # Safe default for small boards; override with --workers on bigger hardware
)
DEFAULT_CHUNKSIZE = (
    50  # Cap so results trickle back often enough to hit the batch flush size above
)

# NOTE 3: maps the --only CLI choice to the OrganelleMetadata column it fills,
# and to the Postgres type the staging table needs for that column. Order here
# fixes the column order everywhere else (CSV row, COPY, UPDATE SET).
FIELD_COLUMNS = {
    "genes": "gene_list",
    "amb_length": "longest_ambiguity_stretch",
}
COLUMN_SQL_TYPES = {
    "gene_list": "jsonb",
    "longest_ambiguity_stretch": "integer",
}


def parse_file(args, columns):
    accession, filepath = args
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    django.setup()
    # Since it's multiprocessed, it has to be imported later into file.
    from pipelines.analyses._genome_operations import GenomeOperations

    try:
        go = GenomeOperations(filepath)
        result = {}
        if "gene_list" in columns:
            result["gene_list"] = go.gene_list()
        if "longest_ambiguity_stretch" in columns:
            seq = str(go.record.seq).upper()
            result["longest_ambiguity_stretch"] = go._longest_ambiguity_stretch(seq)
        return accession, result, None
    except Exception as e:
        return accession, None, str(e)


def _flush(db, batch, columns, stdout, style):
    if not batch:
        return 0
    buf = io.StringIO()
    writer = csv.writer(buf)
    for accession, result in batch:
        row = [accession]
        for col in columns:
            value = result[col]
            row.append(json.dumps(value) if col == "gene_list" else value)
        writer.writerow(row)

    # NOTE 4: staging table/COPY/UPDATE are built from `columns` so a run only
    # touches the fields actually requested via --only.
    col_defs = ", ".join(f"{col} {COLUMN_SQL_TYPES[col]}" for col in columns)
    col_list = ", ".join(["accession", *columns])
    set_clause = ", ".join(f"{col} = s.{col}" for col in columns)

    # Retries on a fresh connection since the pooler can drop the old one mid-run.
    for attempt in range(1, 4):
        try:
            buf.seek(0)
            with db.cursor() as cursor:
                cursor.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS gene_list_staging "
                    f"(accession varchar(50), {col_defs})"
                )
                cursor.execute("TRUNCATE gene_list_staging")
                cursor.copy_expert(
                    f"COPY gene_list_staging ({col_list}) FROM STDIN WITH (FORMAT csv)",
                    buf,
                )
                cursor.execute(f"""
                    UPDATE organism_metadata_organellemetadata AS t
                    SET {set_clause}
                    FROM gene_list_staging AS s
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
    """Backfills the fields selected via --only for pending OrganelleMetadata rows.
    Returns (updated, failed, missing_files)."""
    from apps.organelle_quality.models import OrganelleMetadata

    # NOTE 5: --only is required (argparse enforces this), so `columns` is never
    # empty; de-duped while kept in FIELD_COLUMNS' fixed order.
    selected = set(options["only"])
    columns = [col for key, col in FIELD_COLUMNS.items() if key in selected]

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

    # Either missing field (among the ones requested via --only) routes the row
    # through the same re-parse, since parse_file() computes all of them from a
    # single GenomeOperations instance.
    pending_filter = reduce(or_, (Q(**{f"{col}__isnull": True}) for col in columns))
    pending = set(
        OrganelleMetadata.objects.filter(pending_filter).values_list(
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
        f"{len(to_process)} row(s) to backfill ({', '.join(columns)}) "
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
        for accession, result, error in pool.imap_unordered(
            partial(parse_file, columns=columns), to_process, chunksize=chunksize
        ):
            if error:
                failed += 1
                stdout.write(style.WARNING(f"  {accession} failed: {error}"))
                continue
            batch.append((accession, result))
            if len(batch) >= BATCH_SIZE:
                updated += _flush(db, batch, columns, stdout, style)
                batch = []

    updated += _flush(db, batch, columns, stdout, style)

    return updated, failed, missing_files

"""Extracts taxonomy and organelle stats from GenBank files into TaxonomyData and OrganelleMetadata.

Extracted from pipelines/management/commands/metadata_generator.py so the command
stays a thin CLI wrapper and this logic can be tested/imported independently.
"""

import json
import os
import time
from multiprocessing import Pool

import polars as pl
from Bio import Entrez
from django.conf import settings

from pipelines.exceptions import PipelineError

Entrez.email = os.getenv("ncbi_email")
Entrez.api_key = os.getenv("ncbi_api_key")

# This schema helps in organizing taxonomic data.

RANK_TO_FIELD = {
    "superkingdom": "superkingdom",
    "kingdom": "kingdom",
    "subkingdom": "subkingdom",
    "phylum": "phylum",
    "subphylum": "subphylum",
    "class": "tax_class",
    "subclass": "subclass",
    "order": "order",
    "suborder": "suborder",
    "family": "family",
    "subfamily": "subfamily",
    "tribe": "tribe",
    "subtribe": "subtribe",
    "genus": "genus",
    "subgenus": "subgenus",
    "species": "species",
    "subspecies": "subspecies",
    "varietas": "varietas",
    "forma": "forma",
}

# Write to db for every 1000 records for the stats, 500 for taxonomy.

STATS_BATCH_SIZE = 1000
TAX_BATCH_SIZE = 500

# Output to terminal for every 1000 files written.

PROGRESS_EVERY = 1000

"""
Small miltiprocessing default for autorunning this on small computers. Override
Override with workers on bigger computers.
"""

DEFAULT_WORKERS = 2

# Each process does 50 files at a time before reporting it.

DEFAULT_CHUNKSIZE = (
    50  # Cap so results trickle back often enough to hit the batch flush sizes above
)

"""
This is what the OrganelleMetadata table looks like. To ensure smooth
parsing to PostgreSQL entry this part is done making a Polars structure.
"""

STATS_SCHEMA = {
    "gene_count": pl.Int64,
    "gene_list": pl.Utf8,
    "r_rnas_reported": pl.Int64,
    "t_rnas_reported": pl.Int64,
    "gc_content": pl.Float64,
    "ambiguity_content": pl.Float64,
    "longest_ambiguity_stretch": pl.Int64,
    "base_pair_length": pl.Int64,
    "updated": pl.Datetime,
    "title": pl.Utf8,
    "organelle_type": pl.Utf8,
}

"""



"""

TAX_SCHEMA = {
    f: pl.Utf8 for f in ("accession", "taxid", "common_name", *RANK_TO_FIELD.values())
}


def parse_file(filepath):

    # To multiprocess, modules have to be imported directly at function start.

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    django.setup()

    from pipelines.analyses._genome_operations import GenomeOperations

    # Try everything in GenomeOperations first.

    try:
        go = GenomeOperations(filepath)
        return go.taxid(), go.stats()
    except Exception as e:
        print(f"FAILED {filepath}: {e}")
        return None, None


# NCBI's ScientificName at and below species rank is the full binomial/trinomial
# (e.g. "Arabidopsis thaliana", "Homo sapiens neanderthalensis") — only the last
# word is this rank's own epithet; genus/etc. are already captured separately.

_EPITHET_RANKS = {"species", "subspecies", "varietas", "forma"}

# Get species and not genus.


def _epithet(rank, scientific_name):
    return scientific_name.split()[-1] if rank in _EPITHET_RANKS else scientific_name


# Fetch taxonomy.


def fetch_lineage(taxid):

    # Retrieve taxonomy data.

    handle = Entrez.efetch(db="taxonomy", id=taxid, retmode="xml")
    records = Entrez.read(handle)
    handle.close()

    # Show blanks if no records.

    if not records:
        return {}

    # Get only first result.

    rec = records[0]

    # We use the _epithet function here.
    row = {}
    for t in rec.get("LineageEx", []):
        if t["Rank"] in RANK_TO_FIELD:
            key = RANK_TO_FIELD[t["Rank"]]
            value = _epithet(t["Rank"], t["ScientificName"])
            row[key] = value

    # Now get the lineage from the GB file itself.

    if rec.get("Rank") in RANK_TO_FIELD:
        row[RANK_TO_FIELD[rec["Rank"]]] = _epithet(rec["Rank"], rec["ScientificName"])
    row["common_name"] = rec.get("OtherNames", {}).get("GenbankCommonName", "")
    return row


# Convert polars to PostgreSQL


def _write(rows, table, conn_str, schema, stdout, style):
    if not rows:
        return
    df = pl.DataFrame(rows, schema_overrides=schema)
    try:
        df.write_database(table, conn_str, if_table_exists="append")
        stdout.write(style.SUCCESS(f"  wrote {len(rows)} row(s) to {table}"))
    except Exception as e:
        fallback = f"/tmp/{table}_failed_batch_{int(time.time())}.json"
        df.write_json(fallback)
        stdout.write(
            style.ERROR(
                f"  DB write to {table} failed ({e}); saved {len(rows)} row(s) to {fallback}"
            )
        )


# This is the main command.


def run(options, stdout, style):
    """Extracts taxonomy/stats from new GenBank files.
    Returns (stats_written, tax_written, new_taxa_seen)."""

    from apps.organelle_quality.models import OrganelleMetadata
    from apps.taxonomy.models import TaxonomyData

    # Find our directories.

    gb_dirs = [
        os.path.join(settings.GENBANK_ROOT, d)
        for d in ("plastid_files", "mitochondrial_files")
    ]
    gb_dirs = [d for d in gb_dirs if os.path.isdir(d)]
    if not gb_dirs:
        raise PipelineError(
            'Neither "plastid_files" nor "mitochondrial_files" could be found.'
        )

    # Extract all OrganelleMetadata and TaxonomyData accessions.
    # Turn them into a list.

    done_stats = set(OrganelleMetadata.objects.values_list("accession", flat=True))
    done_tax = set(TaxonomyData.objects.values_list("accession", flat=True))

    # Loop through every directory and make sure both the OrganelleMetadata
    # and TaxonomyData tables are filled.
    file_list = [
        e.path
        for gb_dir in gb_dirs
        for e in os.scandir(gb_dir)
        if e.name.endswith(".gb")
        and (
            os.path.splitext(e.name)[0] not in done_stats
            or os.path.splitext(e.name)[0] not in done_tax
        )
    ]
    if not file_list:
        raise PipelineError("No new .gb files to process.")

    stdout.write(f"{len(file_list)} file(s) to process.")

    # This is the info to write to Suoabase

    # TODO: Will most likely change in the future to non-Supabase PGSQL.

    db = settings.DATABASES["supabase"]
    conn_str = f"postgresql+psycopg2://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"

    """ 
    Cache TaxonomyData relationships so if the same species appears more than once,
    we can use locally-stored taxonomic data rather than another NCBI call.
    """
    cache = {}

    # Exclude NAs

    for row in TaxonomyData.objects.exclude(taxid__isnull=True).values():
        cache.setdefault(
            row["taxid"],
            {k: v for k, v in row.items() if k not in ("id", "accession", "taxid")},
        )

    n_workers = options["workers"] or DEFAULT_WORKERS

    # imap_unordered streams results instead of holding every parsed file in
    # memory (pool.map would) — needed on low-memory hardware like a Pi. The
    # DEFAULT_CHUNKSIZE cap keeps flushes frequent and bounds crash loss;
    # pass --chunksize to override.
    chunksize = options["chunksize"] or max(
        1, min(DEFAULT_CHUNKSIZE, len(file_list) // (n_workers * 4))
    )

    stdout.write(f"Using {n_workers} worker process(es), chunksize={chunksize}.")

    stats_batch, tax_batch = [], []
    stats_written = tax_written = new_taxa_seen = processed = 0

    with Pool(processes=n_workers) as pool:
        for taxid, stats in pool.imap_unordered(
            parse_file, file_list, chunksize=chunksize
        ):
            processed += 1

            if stats and stats["accession"] not in done_stats:
                # gene_list needs to be a JSON string before being written to the database.
                stats["gene_list"] = (
                    json.dumps(stats["gene_list"]) if stats["gene_list"] else None
                )
                stats_batch.append(stats)
                if len(stats_batch) >= STATS_BATCH_SIZE:
                    _write(
                        stats_batch,
                        "organism_metadata_organellemetadata",
                        conn_str,
                        STATS_SCHEMA,
                        stdout,
                        style,
                    )
                    stats_written += len(stats_batch)
                    stats_batch = []

            if stats and taxid and stats["accession"] not in done_tax:
                if taxid not in cache:
                    new_taxa_seen += 1
                    try:
                        cache[taxid] = fetch_lineage(taxid)
                    except Exception as e:
                        stdout.write(
                            style.WARNING(
                                f"  taxonomy fetch failed for taxid {taxid}: {e}"
                            )
                        )
                        continue
                    time.sleep(0.11)
                tax_batch.append(
                    {"accession": stats["accession"], "taxid": taxid, **cache[taxid]}
                )
                if len(tax_batch) >= TAX_BATCH_SIZE:
                    _write(
                        tax_batch,
                        "organism_metadata_taxonomydata",
                        conn_str,
                        TAX_SCHEMA,
                        stdout,
                        style,
                    )
                    tax_written += len(tax_batch)
                    tax_batch = []

            if processed % PROGRESS_EVERY == 0:
                stdout.write(
                    f"  ...{processed}/{len(file_list)} files processed, "
                    f"{new_taxa_seen} new taxa fetched so far"
                )

    _write(
        stats_batch,
        "organism_metadata_organellemetadata",
        conn_str,
        STATS_SCHEMA,
        stdout,
        style,
    )
    stats_written += len(stats_batch)
    _write(
        tax_batch, "organism_metadata_taxonomydata", conn_str, TAX_SCHEMA, stdout, style
    )
    tax_written += len(tax_batch)

    return stats_written, tax_written, new_taxa_seen

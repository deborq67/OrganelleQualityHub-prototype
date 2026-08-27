import django.contrib.postgres.indexes
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations

# Same reasoning as 0006/0008: CONCURRENTLY can't run inside a transaction,
# and a trigram GIN build over this many rows times out against Supabase's
# pooled connection. Must be run against Postgres via a direct (non-pooled)
# connection, not the pooled 'supabase' alias used for normal app traffic.
TRIGRAM_FIELDS = [
    "genus",
    "species",
    "subspecies",
    "family",
    "subfamily",
    "order",
    "suborder",
]


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("organism_metadata", "0008_title_trigram_index"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="taxonomydata",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=[field],
                name=f"taxdata_{field}_trgm_gin",
                opclasses=["gin_trgm_ops"],
            ),
        )
        for field in TRIGRAM_FIELDS
    ]

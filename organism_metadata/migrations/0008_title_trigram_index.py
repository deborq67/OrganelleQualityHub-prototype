import django.contrib.postgres.indexes
from django.contrib.postgres.operations import AddIndexConcurrently, TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    # Same reasoning as 0006: CONCURRENTLY can't run inside a transaction,
    # and a trigram GIN build over this many rows of title text times out
    # against Supabase's pooled connection. Must be run against Postgres via
    # a direct (non-pooled) connection, not the pooled 'supabase' alias used
    # for normal app traffic.
    atomic = False

    dependencies = [
        ("organism_metadata", "0007_alter_organellemetadata_title_and_more"),
    ]

    operations = [
        TrigramExtension(),
        AddIndexConcurrently(
            model_name="organellemetadata",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["title"],
                name="organism_me_title_trgm_gin",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]

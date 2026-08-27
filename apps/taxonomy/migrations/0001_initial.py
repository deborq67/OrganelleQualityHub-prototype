# Consolidated initial migration for the new `taxonomy` app, split out of
# the old `organism_metadata` app (which held TaxonomyData and
# OrganelleMetadata together, migrated by 9 interleaved migrations).
#
# db_table is pinned to organism_metadata_taxonomydata, the physical table's
# existing name — no schema change, no data move. This migration exists so
# Django has migration state for the new app label; apply it against
# Supabase with `migrate taxonomy --fake-initial` (table + indexes already
# exist, built by organism_metadata's old migrations 0001 and 0009 — the
# trigram GIN indexes below were originally built with AddIndexConcurrently
# to avoid locking a large table over Supabase's pooled connection; they
# are declared here only so Django's model state matches reality, not to
# be rebuilt).

import django.contrib.postgres.indexes
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TaxonomyData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(max_length=50, unique=True)),
                ('taxid', models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ('common_name', models.CharField(blank=True, max_length=200, null=True, verbose_name='Common Name')),
                ('superkingdom', models.CharField(blank=True, max_length=100, null=True, verbose_name='Superkingdom')),
                ('kingdom', models.CharField(blank=True, max_length=100, null=True, verbose_name='Kingdom')),
                ('subkingdom', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subkingdom')),
                ('phylum', models.CharField(blank=True, max_length=100, null=True, verbose_name='Phylum')),
                ('subphylum', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subphylum')),
                ('tax_class', models.CharField(blank=True, max_length=100, null=True, verbose_name='Class')),
                ('subclass', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subclass')),
                ('order', models.CharField(blank=True, max_length=100, null=True, verbose_name='Order')),
                ('suborder', models.CharField(blank=True, max_length=100, null=True, verbose_name='Suborder')),
                ('family', models.CharField(blank=True, max_length=100, null=True, verbose_name='Family')),
                ('subfamily', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subfamily')),
                ('tribe', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tribe')),
                ('subtribe', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subtribe')),
                ('genus', models.CharField(blank=True, max_length=100, null=True, verbose_name='Genus')),
                ('subgenus', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subgenus')),
                ('species', models.CharField(blank=True, max_length=100, null=True, verbose_name='Species')),
                ('subspecies', models.CharField(blank=True, max_length=100, null=True, verbose_name='Subspecies')),
                ('varietas', models.CharField(blank=True, max_length=100, null=True, verbose_name='Varietas')),
                ('forma', models.CharField(blank=True, max_length=100, null=True, verbose_name='Forma')),
            ],
            options={
                'db_table': 'organism_metadata_taxonomydata',
                'verbose_name': 'Taxonomic Information',
                'verbose_name_plural': 'Taxonomic Information',
                'indexes': [
                    django.contrib.postgres.indexes.GinIndex(
                        fields=[field], name=f'taxdata_{field}_trgm_gin', opclasses=['gin_trgm_ops']
                    )
                    for field in ('genus', 'species', 'subspecies', 'family', 'subfamily', 'order', 'suborder')
                ],
            },
        ),
    ]

# Consolidated initial migration for the new `organelle_quality` app, split
# out of the old `organism_metadata` app (which held OrganelleMetadata and
# TaxonomyData together, migrated by 9 interleaved migrations).
#
# db_table is pinned to organism_metadata_organellemetadata, the physical
# table's existing name — no schema change, no data move. This migration
# exists so Django has migration state for the new app label; apply it
# against Supabase with `migrate organelle_quality --fake-initial` (table +
# indexes already exist, built by organism_metadata's old migrations
# 0001-0008 — the GIN indexes below were originally built with
# AddIndexConcurrently to avoid locking a large table over Supabase's
# pooled connection; they are declared here only so Django's model state
# matches reality, not to be rebuilt).

import django.contrib.postgres.indexes
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OrganelleMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(max_length=50, unique=True)),
                ('title', models.TextField(blank=True, db_index=True, null=True)),
                ('organelle_type', models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name='Organelle Type')),
                ('base_pair_length', models.IntegerField(blank=True, null=True, verbose_name='Base Pair Length')),
                ('updated', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Last Updated')),
                ('r_rnas_reported', models.IntegerField(blank=True, null=True, verbose_name='rRNAs Reported')),
                ('t_rnas_reported', models.IntegerField(blank=True, null=True, verbose_name='tRNAs Reported')),
                ('gene_count', models.IntegerField(blank=True, null=True, verbose_name='Total Genes Present')),
                ('gc_content', models.FloatField(blank=True, null=True)),
                ('ambiguity_content', models.FloatField(blank=True, null=True)),
                ('gene_list', models.JSONField(blank=True, null=True, verbose_name='Gene List')),
            ],
            options={
                'db_table': 'organism_metadata_organellemetadata',
                'verbose_name': 'Organelle Metadata',
                'verbose_name_plural': 'Organelle Metadata',
                'indexes': [
                    django.contrib.postgres.indexes.GinIndex(fields=['gene_list'], name='organism_me_gene_li_964402_gin'),
                    django.contrib.postgres.indexes.GinIndex(
                        fields=['title'], name='organism_me_title_trgm_gin', opclasses=['gin_trgm_ops']
                    ),
                ],
            },
        ),
    ]

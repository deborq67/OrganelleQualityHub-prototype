# Consolidated initial migration for the new `genome_maps` app, split out
# of the old `genome_map` app (single migration, unchanged schema).
#
# db_table is pinned to genome_map_genomemap, Django's original default
# table name for the old app_label/model — no schema change, no data move.
# Apply against Supabase with `migrate genome_maps --fake-initial`.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='GenomeMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(max_length=50, unique=True)),
                ('storage_path', models.CharField(help_text='Path inside the Supabase Storage bucket, e.g. NC_001666.png', max_length=255)),
                ('public_url', models.URLField(help_text='Public URL returned by Supabase Storage', max_length=500)),
                ('uploaded_at', models.DateTimeField(auto_now=True, verbose_name='Last Uploaded')),
            ],
            options={
                'db_table': 'genome_map_genomemap',
                'verbose_name': 'Genome Map',
                'verbose_name_plural': 'Genome Maps',
                'ordering': ['accession'],
            },
        ),
    ]

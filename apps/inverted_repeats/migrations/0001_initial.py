# Consolidated initial migration for the new `inverted_repeats` app, split
# out of the old `plastid_interaction` app (4 migrations, including a
# short-lived IR_Confirmation model that was later deleted).
#
# db_table was already pinned to plastid_interaction_ir_identification by
# the old app's own migration 0002 — unchanged here, no schema change, no
# data move. Apply against Supabase with
# `migrate inverted_repeats --fake-initial`.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='IR_Identification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(max_length=50, unique=True)),
                ('title', models.TextField(default='No Title')),
                ('updated', models.DateTimeField(blank=True, null=True, verbose_name='Last Updated')),
                ('checked', models.DateTimeField(auto_now=True, verbose_name='Last Checked')),
                ('ir_reported', models.CharField(
                    choices=[
                        ('yes', 'Yes'),
                        ('no', 'No'),
                        ('exception', 'No, or only 1 IR occurs naturally in this species.'),
                    ],
                    default='no', max_length=50, verbose_name='Inverted Repeats Reported',
                )),
                ('ira_reported', models.CharField(max_length=50)),
                ('ira_reported_start', models.IntegerField(blank=True, null=True, verbose_name='Start of Inverted Repeat A (bp position)')),
                ('ira_reported_end', models.IntegerField(blank=True, null=True, verbose_name='End of Inverted Repeat A (bp position)')),
                ('ira_reported_length', models.IntegerField(blank=True, null=True, verbose_name='Length of Inverted Repeat A (bp)')),
                ('irb_reported', models.CharField(blank=True, choices=[('yes', 'Yes'), ('no', 'No')], max_length=50, null=True)),
                ('irb_reported_start', models.IntegerField(blank=True, null=True, verbose_name='Start of Inverted Repeat B (bp position)')),
                ('irb_reported_end', models.IntegerField(blank=True, null=True, verbose_name='End of Inverted Repeat B (bp position)')),
                ('irb_reported_length', models.IntegerField(blank=True, null=True, verbose_name='Length of Inverted Repeat B (bp)')),
                ('ira_blastinferred', models.CharField(choices=[('yes', 'Yes'), ('no', 'No')], default='no', max_length=10)),
                ('ira_blastinferred_start', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred Start of IRa (bp)')),
                ('ira_blastinferred_end', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred End of IRa (bp)')),
                ('ira_blastinferred_length', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred Length of IRa (bp)')),
                ('irb_blastinferred', models.CharField(choices=[('yes', 'Yes'), ('no', 'No')], default='no', max_length=10)),
                ('irb_blastinferred_start', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred Start of IRb (bp)')),
                ('irb_blastinferred_end', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred End of IRb (bp)')),
                ('irb_blastinferred_length', models.IntegerField(blank=True, null=True, verbose_name='BLAST-inferred Length of IRb (bp)')),
                ('notes', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'plastid_interaction_ir_identification',
                'verbose_name': 'IR Identification',
            },
        ),
    ]

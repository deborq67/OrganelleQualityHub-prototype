from django.db import migrations, models


def backfill_ir_equal(apps, schema_editor):
    ir_identification = apps.get_model("inverted_repeats", "IR_Identification")
    for record in ir_identification.objects.all().iterator():
        if (
            record.ira_reported_length is None
            or record.irb_reported_length is None
        ):
            ir_equal = None
        else:
            ir_equal = (
                "yes"
                if record.ira_reported_length == record.irb_reported_length
                else "no"
            )
        ir_identification.objects.filter(pk=record.pk).update(ir_equal=ir_equal)


class Migration(migrations.Migration):
    dependencies = [
        ("inverted_repeats", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ir_identification",
            name="ir_equal",
            field=models.CharField(
                blank=True,
                choices=[("yes", "Yes"), ("no", "No")],
                max_length=10,
                null=True,
                verbose_name="IRs Equal",
            ),
        ),
        migrations.RunPython(backfill_ir_equal, migrations.RunPython.noop),
    ]
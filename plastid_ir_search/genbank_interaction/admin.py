from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import IR_Identification
from django.forms import DateInput
from django import forms


class IRIdentificationForm(forms.ModelForm):
    class Meta:
        model = IR_Identification
        fields = "__all__"
        widgets = {
            "updated": DateInput(attrs={"type": "date"}),
        }


@admin.register(IR_Identification)
class IRCalculationAdmin(ModelAdmin):
    form = IRIdentificationForm

    list_display = ["accession", "title", "updated_date", "ir_reported"]
    list_filter = ["updated", "ir_reported"]
    list_editable = ["ir_reported"]
    exclude = ["ira_reported", "irb_reported"]

    conditional_fields = {
        "ira_reported": "ir_reported == 'yes' || ir_reported == 'exception'",
        "ira_reported_start": "ir_reported == 'yes' || ir_reported == 'exception' ",
        "ira_reported_end": "ir_reported == 'yes' || ir_reported == 'exception'",
        "ira_reported_length": "ir_reported == 'yes' || ir_reported == 'exception'",
        "irb_reported_start": "ir_reported == 'yes'",
        "irb_reported_end": "ir_reported == 'yes'",
        "irb_reported_length": "ir_reported == 'yes'",
    }
    search_fields = ["accession", "title", "updated"]

    # Make date ONLY appear.
    def updated_date(self, obj):
        return obj.updated.strftime('%B %d, %Y') if obj.updated else None
    updated_date.short_description = "Last Updated"

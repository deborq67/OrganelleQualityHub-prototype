from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import TaxonomyData


@admin.register(TaxonomyData)
class TaxonomyDataAdmin(ModelAdmin):
    list_display = ["accession", "common_name", "genus", "species"]
    search_fields = ["accession", "common_name", "genus", "species"]

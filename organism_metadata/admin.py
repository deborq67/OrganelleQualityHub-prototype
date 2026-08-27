from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import TaxonomyData, OrganelleMetadata


@admin.register(TaxonomyData)
class TaxonomyDataAdmin(ModelAdmin):
    list_display = ["accession", "common_name", "genus", "species"]
    search_fields = ["accession", "common_name", "genus", "species"]


@admin.register(OrganelleMetadata)
class OrganelleMetadataAdmin(ModelAdmin):
    list_display = ["accession", "gene_count", "gc_content"]
    search_fields = ["accession"]

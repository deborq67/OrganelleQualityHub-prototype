from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import OrganelleMetadata


@admin.register(OrganelleMetadata)
class OrganelleMetadataAdmin(ModelAdmin):
    list_display = ["accession", "gene_count", "gc_content"]
    search_fields = ["accession"]

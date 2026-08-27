from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import GenomeMap


@admin.register(GenomeMap)
class GenomeMapAdmin(ModelAdmin):
    list_display = ["accession", "public_url", "uploaded_at"]
    search_fields = ["accession"]

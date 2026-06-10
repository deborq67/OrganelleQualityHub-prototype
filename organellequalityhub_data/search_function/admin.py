from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(ModelAdmin):
    readonly_fields = ["session_key", "search_term", "total_records", "searched_at"]
    search_fields = ["search_term", "searched_at"]

from django.db import models


class SearchResult(models.Model):
    accession = models.CharField(max_length=50)
    title = models.TextField()
    bp_length = models.IntegerField()
    updated = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(null=True, blank=True)
    ir_info = models.ForeignKey(
        'genbank_interaction.IR_Identification',
        to_field='accession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_results'
    )

    def __str__(self):
        return f"{self.accession}"


class SearchHistory(models.Model):
    class Meta:
        # Correcting spelling on admin page.
        verbose_name = "Search History"
        verbose_name_plural = "Search History"

    session_key = models.CharField(max_length=50)
    search_term = models.CharField(max_length=255)
    total_records = models.IntegerField()
    searched_at = models.DateTimeField(auto_now_add=True)
    search_accessions = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.search_term} - {self.searched_at.strftime('%B %d, %Y %H:%M')}"

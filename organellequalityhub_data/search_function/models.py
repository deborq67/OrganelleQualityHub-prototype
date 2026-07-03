from django.db import models


class SearchResult(models.Model):
    accession = models.CharField(max_length=50)
    title = models.TextField()

    def __str__(self):
        return f"{self.accession}"

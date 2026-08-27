from django.db import models


class GenomeMap(models.Model):
    accession = models.CharField(max_length=50, unique=True)
    storage_path = models.CharField(
        max_length=255,
        help_text='Path inside the Supabase Storage bucket, e.g. NC_001666.png'
    )
    public_url = models.URLField(
        max_length=500,
        help_text='Public URL returned by Supabase Storage'
    )
    uploaded_at = models.DateTimeField(verbose_name='Last Uploaded', auto_now=True)

    def __str__(self):
        return self.accession

    class Meta:
        db_table = 'genome_map_genomemap'
        verbose_name = 'Genome Map'
        verbose_name_plural = 'Genome Maps'
        ordering = ['accession']

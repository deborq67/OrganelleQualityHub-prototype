from django.db import models
from django.contrib.postgres.indexes import GinIndex


class OrganelleMetadata(models.Model):
    accession = models.CharField(max_length=50, unique=True)
    title = models.TextField(null=True, blank=True, db_index=True)
    organelle_type = models.CharField(
        verbose_name="Organelle Type",
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
    )
    base_pair_length = models.IntegerField(
        verbose_name="Base Pair Length", null=True, blank=True
    )
    updated = models.DateTimeField(
        verbose_name="Last Updated", null=True, blank=True, db_index=True
    )
    r_rnas_reported = models.IntegerField(
        verbose_name="rRNAs Reported", null=True, blank=True
    )
    t_rnas_reported = models.IntegerField(
        verbose_name="tRNAs Reported", null=True, blank=True
    )
    gene_count = models.IntegerField(
        verbose_name="Total Genes Present", null=True, blank=True
    )
    gc_content = models.FloatField(blank=True, null=True)
    ambiguity_content = models.FloatField(blank=True, null=True)
    longest_ambiguity_stretch = models.IntegerField(
        verbose_name="Longest Ambiguity Stretch (bp)", null=True, blank=True
    )
    gene_list = models.JSONField(verbose_name="Gene List", null=True, blank=True)

    def __str__(self):
        return f"{self.accession} Metadata"

    class Meta:
        db_table = "organism_metadata_organellemetadata"
        verbose_name = "Organelle Metadata"
        verbose_name_plural = "Organelle Metadata"
        indexes = [
            GinIndex(fields=["gene_list"]),
            GinIndex(
                fields=["title"],
                name="organism_me_title_trgm_gin",
                opclasses=["gin_trgm_ops"],
            ),
        ]

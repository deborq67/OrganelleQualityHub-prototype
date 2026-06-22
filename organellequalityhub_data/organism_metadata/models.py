from django.db import models


class TaxonomyData(models.Model):
    accession = models.CharField(max_length=50, unique=True)
    taxid = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    common_name = models.CharField(max_length=200, verbose_name='Common Name', null=True, blank=True)
    superkingdom = models.CharField(max_length=100, verbose_name='Superkingdom', null=True, blank=True)
    kingdom = models.CharField(max_length=100, verbose_name='Kingdom', null=True, blank=True)
    subkingdom = models.CharField(max_length=100, verbose_name='Subkingdom', null=True, blank=True)
    phylum = models.CharField(max_length=100, verbose_name='Phylum', null=True, blank=True)
    subphylum = models.CharField(max_length=100, verbose_name='Subphylum', null=True, blank=True)
    tax_class = models.CharField(max_length=100, verbose_name='Class', null=True, blank=True)
    subclass = models.CharField(max_length=100, verbose_name='Subclass', null=True, blank=True)
    order = models.CharField(max_length=100, verbose_name='Order', null=True, blank=True)
    suborder = models.CharField(max_length=100, verbose_name='Suborder', null=True, blank=True)
    family = models.CharField(max_length=100, verbose_name='Family', null=True, blank=True)
    subfamily = models.CharField(max_length=100, verbose_name='Subfamily', null=True, blank=True)
    tribe = models.CharField(max_length=100, verbose_name='Tribe', null=True, blank=True)
    subtribe = models.CharField(max_length=100, verbose_name='Subtribe', null=True, blank=True)
    genus = models.CharField(max_length=100, verbose_name='Genus', null=True, blank=True)
    subgenus = models.CharField(max_length=100, verbose_name='Subgenus', null=True, blank=True)
    species = models.CharField(max_length=100, verbose_name='Species', null=True, blank=True)
    subspecies = models.CharField(max_length=100, verbose_name='Subspecies', null=True, blank=True)
    varietas = models.CharField(max_length=100, verbose_name='Varietas', null=True, blank=True)
    forma = models.CharField(max_length=100, verbose_name='Forma', null=True, blank=True)

    def __str__(self):
        for combo in (
            [self.genus, self.species, self.subspecies],
            [self.family, self.subfamily],
            [self.order, self.suborder],
        ):
            name = ' '.join(filter(None, combo))
            if name:
                return f"{self.accession} - {name}"
        return f"{self.accession} - Unidentified"

    class Meta:
        verbose_name = 'Taxonomic Information'
        verbose_name_plural = 'Taxonomic Information'


class OrganelleMetadata(models.Model):
    accession = models.CharField(max_length=50, unique=True)
    title = models.TextField(null=True, blank=True)
    base_pair_length = models.IntegerField(verbose_name='Base Pair Length', null=True, blank=True)
    updated = models.DateTimeField(verbose_name='Last Updated', null=True, blank=True)
    r_rnas_reported = models.IntegerField(verbose_name='rRNAs Reported', null=True, blank=True)
    t_rnas_reported = models.IntegerField(verbose_name='tRNAs Reported', null=True, blank=True)
    gene_count = models.IntegerField(verbose_name='Total Genes Present', null=True, blank=True)
    gc_content = models.FloatField(blank=True, null=True)
    ambiguity_content = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.accession} Metadata"

    class Meta:
        verbose_name = 'Organelle Metadata'
        verbose_name_plural = 'Organelle Metadata'

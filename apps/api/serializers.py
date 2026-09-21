from rest_framework import serializers
from apps.taxonomy.models import TaxonomyData
from apps.organelle_quality.models import OrganelleMetadata
from apps.inverted_repeats.models import IR_Identification
from apps.genome_maps.models import GenomeMap


class TaxonomyDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxonomyData
        fields = "__all__"


class OrganelleMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganelleMetadata
        fields = "__all__"


class IRIdentificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = IR_Identification
        fields = "__all__"


class GenomeMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenomeMap
        fields = "__all__"

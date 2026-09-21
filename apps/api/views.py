from rest_framework.viewsets import ReadOnlyModelViewSet
from apps.taxonomy.models import TaxonomyData
from apps.organelle_quality.models import OrganelleMetadata
from apps.inverted_repeats.models import IR_Identification
from apps.genome_maps.models import GenomeMap
from .serializers import (
    TaxonomyDataSerializer,
    OrganelleMetadataSerializer,
    IRIdentificationSerializer,
    GenomeMapSerializer,
)


class TaxonomyDataViewSet(ReadOnlyModelViewSet):
    queryset = TaxonomyData.objects.all()
    serializer_class = TaxonomyDataSerializer
    lookup_field = "accession"
    # Makes it ok to include dots in the regex.
    lookup_value_regex = r"[^/]+"


class OrganelleMetadataViewSet(ReadOnlyModelViewSet):
    queryset = OrganelleMetadata.objects.all()
    serializer_class = OrganelleMetadataSerializer
    lookup_field = "accession"
    lookup_value_regex = r"[^/]+"


class IRIdentificationViewSet(ReadOnlyModelViewSet):
    queryset = IR_Identification.objects.all()
    serializer_class = IRIdentificationSerializer
    lookup_field = "accession"
    lookup_value_regex = r"[^/]+"


class GenomeMapViewSet(ReadOnlyModelViewSet):
    queryset = GenomeMap.objects.all()
    serializer_class = GenomeMapSerializer
    lookup_field = "accession"
    lookup_value_regex = r"[^/]+"

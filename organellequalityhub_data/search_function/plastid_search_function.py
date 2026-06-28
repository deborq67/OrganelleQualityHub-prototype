import hashlib

import polars as pl
from django.core.cache import cache
from django.db.models import Q

from organism_metadata.models import TaxonomyData, OrganelleMetadata

'''
Purpose: Searches the locally stored taxonomy records for organisms matching
the search term, then joins in title, base pair length, and last updated
from OrganelleMetadata by accession.
'''

# Taxonomic fields to match each search term word against.
TAXONOMY_SEARCH_FIELDS = [
    'common_name', 'superkingdom', 'kingdom', 'phylum',
    'tax_class', 'order', 'family', 'genus', 'species', 'subspecies',
]

# Narrower taxonomic field sets for the category dropdown.
CATEGORY_TAXONOMY_FIELDS = {
    'Genus & Species': ['genus', 'species', 'subspecies'],
    'Family': ['family', 'subfamily'],
    'Order': ['order', 'suborder'],
}

# Organelle type filter for the category dropdown.
ORGANELLE_TYPE_FILTERS = {
    'Mitochondrion': Q(organelle_type__icontains='mitochondrion'),
    'Chloroplast/Plastid': (
        Q(organelle_type__icontains='chloroplast') | Q(organelle_type__icontains='plastid')
    ),
}

EMPTY_SCHEMA = {
    'Accession': pl.String,
    'Title': pl.String,
    'BP_Length': pl.Int64,
    'Updated': pl.String,
    'Ambiguity_Content': pl.Float64,
}


def initiate_search(search_term, category='Genus & Species'):
    search_term = search_term.strip()
    if not search_term and category not in ORGANELLE_TYPE_FILTERS:
        return pl.DataFrame(schema=EMPTY_SCHEMA), 0

    # Cache the result to save on speed.

    cache_key = 'search:' + hashlib.md5(f'{category}:{search_term}'.encode()).hexdigest()

    cached = cache.get(cache_key)
    if cached:
        return cached

    # Every word in the search term must match at least one field for the
    # chosen category, e.g. "Arabidopsis thaliana" under Genus & Species
    # matches genus="Arabidopsis" AND species="thaliana".

    words = search_term.split()
    if category == 'Gene':
        matches = OrganelleMetadata.objects.all()
        for word in words:
            matches = matches.filter(gene_list__icontains=word)
    else:
        matches = TaxonomyData.objects.all()
        if category in ORGANELLE_TYPE_FILTERS:
            organelle_accessions = OrganelleMetadata.objects.filter(
                ORGANELLE_TYPE_FILTERS[category]
            ).values_list('accession', flat=True)
            matches = matches.filter(accession__in=organelle_accessions)

        fields = CATEGORY_TAXONOMY_FIELDS.get(category, TAXONOMY_SEARCH_FIELDS)
        for word in words:
            word_filter = Q()
            for field in fields:
                word_filter |= Q(**{f'{field}__icontains': word})
            matches = matches.filter(word_filter)

    accessions = list(matches.values_list('accession', flat=True))
    total_records = len(accessions)

    metadata_by_accession = {
        metadata.accession: metadata
        for metadata in OrganelleMetadata.objects.filter(accession__in=accessions)
    }

    records = []
    for accession in accessions:
        metadata = metadata_by_accession.get(accession)
        records.append({
            'Accession': accession,
            'Title': metadata.title if metadata and metadata.title else 'No Title',
            'BP_Length': metadata.base_pair_length if metadata else None,
            'Updated': (
                metadata.updated.strftime('%Y/%m/%d')
                if metadata and metadata.updated else None
            ),
            'Ambiguity_Content': metadata.ambiguity_content if metadata else None,
        })

    df = pl.DataFrame(records) if records else pl.DataFrame(schema=EMPTY_SCHEMA)

    # Cache records if already searched.
    cache.set(cache_key, (df, total_records))

    return df, total_records

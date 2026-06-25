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

# Taxonomic fields to match each search term token against.
TAXONOMY_SEARCH_FIELDS = [
    'common_name', 'superkingdom', 'kingdom', 'phylum',
    'tax_class', 'order', 'family', 'genus', 'species', 'subspecies',
]

EMPTY_SCHEMA = {
    'Accession': pl.String,
    'Title': pl.String,
    'BP_Length': pl.Int64,
    'Updated': pl.String,
    'Ambiguity_Content': pl.Float64,
}


def initiate_search(search_term):
    search_term = search_term.strip()
    if not search_term:
        return pl.DataFrame(schema=EMPTY_SCHEMA), 0

    # Cache the result to save on speed.
    
    cache_key = 'search:' + hashlib.md5(search_term.encode()).hexdigest()

    cached = cache.get(cache_key)
    if cached:
        return cached

    # Every token in the search term must match at least one taxonomic
    # field, e.g. "Arabidopsis thaliana" matches genus="Arabidopsis" AND
    # species="thaliana".

    matches = TaxonomyData.objects.all()
    for token in search_term.split():
        token_filter = Q()
        for field in TAXONOMY_SEARCH_FIELDS:
            token_filter |= Q(**{f'{field}__icontains': token})
        matches = matches.filter(token_filter)

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

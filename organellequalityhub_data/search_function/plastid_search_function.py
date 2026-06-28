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
        metadata_query = OrganelleMetadata.objects.all()
        for word in words:
            metadata_query = metadata_query.filter(gene_list__icontains=word)
    else:
        metadata_query = OrganelleMetadata.objects.all()
        if category in ORGANELLE_TYPE_FILTERS:
            metadata_query = metadata_query.filter(ORGANELLE_TYPE_FILTERS[category])

        # Only interact with TaxonomyData when there's an actual word to match against it.
        if words:
            fields = CATEGORY_TAXONOMY_FIELDS.get(category, TAXONOMY_SEARCH_FIELDS)
            taxonomy_matches = TaxonomyData.objects.all()
            for word in words:
                word_filter = Q()
                for field in fields:
                    word_filter |= Q(**{f'{field}__icontains': word})
                taxonomy_matches = taxonomy_matches.filter(word_filter)
            metadata_query = metadata_query.filter(
                accession__in=taxonomy_matches.values_list('accession', flat=True)
            )

    metadata_rows = list(
        metadata_query.values('accession', 'title', 'base_pair_length', 'updated', 'ambiguity_content')
    )
    total_records = len(metadata_rows)

    records = [
        {
            'Accession': row['accession'],
            'Title': row['title'] or 'No Title',
            'BP_Length': row['base_pair_length'],
            'Updated': row['updated'].strftime('%Y/%m/%d') if row['updated'] else None,
            'Ambiguity_Content': row['ambiguity_content'],
        }
        for row in metadata_rows
    ]

    df = pl.DataFrame(records) if records else pl.DataFrame(schema=EMPTY_SCHEMA)

    # Cache records if already searched.
    cache.set(cache_key, (df, total_records))

    return df, total_records

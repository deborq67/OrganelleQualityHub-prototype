import hashlib

import polars as pl
from django.core.cache import cache
from django.db.models import Q

from organism_metadata.models import TaxonomyData, OrganelleMetadata
from plastid_interaction.models import IR_Identification

"""
Purpose: Searches the locally stored taxonomy records for organisms matching
the search term, then joins in title, base pair length, and last updated
from OrganelleMetadata by accession.
"""

# Taxonomic fields to match each search term word against.

TAXONOMY_SEARCH_FIELDS = [
    "common_name",
    "superkingdom",
    "kingdom",
    "phylum",
    "tax_class",
    "order",
    "family",
    "genus",
    "species",
    "subspecies",
]

# Narrower taxonomic field sets for the category dropdown.

CATEGORY_TAXONOMY_FIELDS = {
    "Genus and Species": ["genus", "species", "subspecies"],
    "Family": ["family", "subfamily"],
    "Order": ["order", "suborder"],
}

# Organelle type filter for the category dropdown.

ORGANELLE_TYPE_FILTERS = {
    "Mitochondrion": Q(organelle_type__icontains="mitochondrion"),
    "Chloroplast/Plastid": (
        Q(organelle_type__icontains="chloroplast")
        | Q(organelle_type__icontains="plastid")
    ),
    "IR Reported": Q(
        accession__in=IR_Identification.objects.filter(ir_reported=True).values_list(
            "accession", flat=True
        )
    ),
}


def initiate_search(search_term, category="Genus and Species"):
    search_term = search_term.strip()

    # Cache the result to save on speed.

    cache_key = (
        "search:" + hashlib.md5(f"{category}:{search_term}".encode()).hexdigest()
    )

    cached = cache.get(cache_key)
    if cached:
        return cached

    # Turn db query into list.

    metadata_query = build_metadata_queryset(search_term, category)

    metadata_rows = list(
        metadata_query.values(
            "accession",
            "title",
            "base_pair_length",
            "updated",
            "r_rnas_reported",
            "t_rnas_reported",
            "gc_content",
            "ambiguity_content",
            "gene_count",
        )
    )
    total_records = len(metadata_rows)

    df = pl.DataFrame(
        {
            "Accession": [row["accession"] for row in metadata_rows],
            "Title": [row["title"] or "No Title" for row in metadata_rows],
            "BP_Length": [row["base_pair_length"] for row in metadata_rows],
            "Updated": [
                row["updated"].strftime("%Y/%m/%d") if row["updated"] else None
                for row in metadata_rows
            ],
            "RRNAs_Reported": [row["r_rnas_reported"] for row in metadata_rows],
            "TRNAs_Reported": [row["t_rnas_reported"] for row in metadata_rows],
            "GC_Content": [row["gc_content"] for row in metadata_rows],
            "Ambiguity_Content": [row["ambiguity_content"] for row in metadata_rows],
            "Gene_Count": [row["gene_count"] for row in metadata_rows],
        }
    )

    # Cache records if already searched.
    cache.set(cache_key, (df, total_records), timeout=3600)

    return df, total_records


# Links organelle records to taxonomy.


def build_metadata_queryset(search_term, category="Genus and Species"):
    search_term = search_term.strip()
    is_wildcard = search_term == "*"
    words = [] if is_wildcard else search_term.split()

    if not words and not is_wildcard:
        return OrganelleMetadata.objects.none()

    if category == "Gene":
        metadata_query = OrganelleMetadata.objects.all()
        for word in words:
            metadata_query = metadata_query.filter(gene_list__has_key=word)

    else:
        metadata_query = OrganelleMetadata.objects.all()
        if category in ORGANELLE_TYPE_FILTERS:
            metadata_query = metadata_query.filter(ORGANELLE_TYPE_FILTERS[category])
        if words:
            fields = CATEGORY_TAXONOMY_FIELDS.get(category, TAXONOMY_SEARCH_FIELDS)
            taxonomy_matches = TaxonomyData.objects.all()
            for word in words:
                word_filter = Q()
                for field in fields:
                    word_filter |= Q(**{f"{field}__icontains": word})
                taxonomy_matches = taxonomy_matches.filter(word_filter)
            metadata_query = metadata_query.filter(
                accession__in=taxonomy_matches.values_list("accession", flat=True)
            )

    return metadata_query

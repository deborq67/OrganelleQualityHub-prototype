from django.shortcuts import render, redirect
from .services import build_metadata_queryset
from random import choice
from apps.inverted_repeats.models import IR_Identification
from apps.organelle_quality.models import OrganelleMetadata
from apps.taxonomy.models import TaxonomyData
from datetime import datetime
import polars as pl
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
import plotly.express as px
from django.core.cache import cache
from django.db.models import Sum

"""
Names for the columns from left to right for main table:
Django database, Download headers, HTML Display
"""

RESULT_COLUMNS = [
    ("accession", "Accession", "Accession"),
    ("title", "Title", "Title"),
    ("updated", "Updated", "Updated"),
    ("base_pair_length", "BP_Length", "Base Pair Length"),
    ("r_rnas_reported", "RRNAs_Reported", "N rRNAs"),
    ("t_rnas_reported", "TRNAs_Reported", "N tRNAs"),
    ("gc_content", "GC_Content", "GC"),
    ("ambiguity_content", "Ambiguity_Content", "N ambig."),
    (
        "longest_ambiguity_stretch",
        "Longest_Ambiguity_Stretch",
        "Longest ambig. stretch",
    ),
    ("gene_count", "Gene_Count", "N genes"),
]

"""
Same thing for our chloroplast values:
Django database, Download headers, HTML Display
"""

IR_RESULT_COLUMNS = [
    ("accession", "Accession", "Accession"),
    ("ira_reported", "IRa_Reported", "IRa Reported"),
    ("irb_reported", "IRb_Reported", "IRb Reported"),
    ("ira_blastinferred", "IRa_Inferred", "IRa Inferred"),
    ("irb_blastinferred", "IRb_Inferred", "IRb Inferred"),
]

# For the Django db, get first value.
RESULTS_DATA_FIELDS = [col[0] for col in RESULT_COLUMNS]

# Same thing, but for IR values.
IR_RESULTS_DATA_FIELDS = [col[0] for col in IR_RESULT_COLUMNS]

# For the download headers, get second value.
RESULTS_COLUMNS = [col[1] for col in RESULT_COLUMNS]
IR_RESULTS_COLUMNS = [col[1] for col in IR_RESULT_COLUMNS]

# For the column displayed in HTML, make a dictionary.
RESULTS_COLUMN_LABELS = {col[1]: col[2] for col in RESULT_COLUMNS}

# IR version
IR_RESULTS_COLUMN_LABELS = {col[1]: col[2] for col in IR_RESULT_COLUMNS}

# Only these are worth matching against free-text search input - the rest
# are numbers/dates nobody meaningfully searches by typing text.

SEARCHABLE_FIELDS = ["accession", "title"]

DOWNLOAD_FIELDS = [
    "accession",
    "title",
    "base_pair_length",
    "updated",
    "ambiguity_content",
    "longest_ambiguity_stretch",
    "gc_content",
    "r_rnas_reported",
    "t_rnas_reported",
    "gene_count",
    "gene_list",
]


# Deal with filters.


def _int_param(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Allows download button to only use searchable fields.


def _apply_search_filter(qs, search_value, fields=SEARCHABLE_FIELDS):
    search_value = (search_value or "").strip()
    if not search_value:
        return qs
    search_filter = Q()
    for field in fields:
        search_filter |= Q(**{f"{field}__icontains": search_value})
    return qs.filter(search_filter)


# Allows CSV exports.

CSV_EXPORT_SCHEMA = {
    "accession": pl.String,
    "title": pl.String,
    "base_pair_length": pl.Int64,
    "updated": pl.Datetime,
    "ambiguity_content": pl.Float64,
    "longest_ambiguity_stretch": pl.Int64,
    "gc_content": pl.Float64,
    "r_rnas_reported": pl.Int64,
    "t_rnas_reported": pl.Int64,
    "gene_count": pl.Int64,
    "gene": pl.String,
    "start": pl.Int64,
    "end": pl.Int64,
}

IR_EXPORT_SCHEMA = {
    "ira_reported": pl.String,
    "ira_reported_start": pl.Int64,
    "ira_reported_end": pl.Int64,
    "ira_reported_length": pl.Int64,
    "ira_blastinferred": pl.String,
    "ira_blastinferred_start": pl.Int64,
    "ira_blastinferred_end": pl.Int64,
    "ira_blastinferred_length": pl.Int64,
    "irb_reported": pl.String,
    "irb_reported_start": pl.Int64,
    "irb_reported_end": pl.Int64,
    "irb_reported_length": pl.Int64,
    "irb_blastinferred": pl.String,
    "irb_blastinferred_start": pl.Int64,
    "irb_blastinferred_end": pl.Int64,
    "irb_blastinferred_length": pl.Int64,
}


#
RECORD_INFO_EXPORT_SCHEMA = {**CSV_EXPORT_SCHEMA, **IR_EXPORT_SCHEMA}

#
IR_FIELDS = list(IR_EXPORT_SCHEMA.keys())


##############################################
#
# INDEX.HTML'S VIEW
#
# ############################################


def create_graph(request):
    """
    Main purpose of the function is to make a graph and
    get certain values to display on the home page.
    """

    # Graph portion

    plastid_records = list(IR_Identification.objects.values("updated", "accession"))
    plastid_histogram_df = (
        pl.DataFrame(plastid_records)
        if plastid_records
        else pl.DataFrame(schema={"updated": pl.Date, "accession": pl.String})
    )

    plastid_histogram_df = plastid_histogram_df.filter(pl.col("updated").is_not_null())

    plastid_histogram_df = plastid_histogram_df.with_columns(
        pl.col("updated").cast(pl.Date)
    )
    plastid_histogram_df = (
        plastid_histogram_df.group_by("updated")
        .agg(pl.len().alias("count"))
        .sort("updated")
    )
    if plastid_histogram_df.height:
        plastid_full_range = pl.DataFrame(
            {
                "updated": pl.date_range(
                    plastid_histogram_df["updated"].min(),
                    plastid_histogram_df["updated"].max(),
                    "1d",
                    eager=True,
                )
            }
        )
        plastid_histogram_df = (
            plastid_full_range.join(plastid_histogram_df, on="updated", how="left")
            .fill_null(0)
            .with_columns(pl.col("count").cum_sum().alias("Total Records"))
            .rename({"updated": "Last Update"})
            .with_columns(pl.lit("Plastid").alias("Type"))
        )
    else:
        plastid_histogram_df = pl.DataFrame(
            schema={
                "Last Update": pl.Date,
                "Total Records": pl.Int64,
                "Type": pl.String,
            }
        )

    mito_records = list(
        OrganelleMetadata.objects.filter(
            organelle_type__startswith="mitochondrion"
        ).values("updated")
    )
    mito_histogram_df = (
        pl.DataFrame(mito_records)
        if mito_records
        else pl.DataFrame(schema={"updated": pl.Date})
    )
    mito_histogram_df = mito_histogram_df.filter(pl.col("updated").is_not_null())
    mito_histogram_df = mito_histogram_df.with_columns(pl.col("updated").cast(pl.Date))
    mito_histogram_df = (
        mito_histogram_df.group_by("updated")
        .agg(pl.len().alias("count"))
        .sort("updated")
    )
    if mito_histogram_df.height:
        mito_full_range = pl.DataFrame(
            {
                "updated": pl.date_range(
                    mito_histogram_df["updated"].min(),
                    mito_histogram_df["updated"].max(),
                    "1d",
                    eager=True,
                )
            }
        )
        mito_histogram_df = (
            mito_full_range.join(mito_histogram_df, on="updated", how="left")
            .fill_null(0)
            .with_columns(pl.col("count").cum_sum().alias("Total Records"))
            .rename({"updated": "Last Update"})
            .with_columns(pl.lit("Mitochondrion").alias("Type"))
        )
    else:
        mito_histogram_df = pl.DataFrame(
            schema={
                "Last Update": pl.Date,
                "Total Records": pl.Int64,
                "Type": pl.String,
            }
        )

    total_df = (
        mito_histogram_df.select(["Last Update", "Total Records"])
        .join(
            plastid_histogram_df.select(["Last Update", "Total Records"]),
            on="Last Update",
            how="full",
            coalesce=True,
        )
        .sort("Last Update")
        .with_columns(
            pl.col("Total Records").forward_fill().fill_null(0),
            pl.col("Total Records_right").forward_fill().fill_null(0),
        )
        .with_columns(
            (pl.col("Total Records") + pl.col("Total Records_right")).alias(
                "Total Records"
            )
        )
        .select(["Last Update", "Total Records"])
        .with_columns(pl.lit("Total").alias("Type"))
    )

    cols = ["Last Update", "Total Records", "Type"]
    combined_df = pl.concat(
        [
            total_df.select(cols),
            mito_histogram_df.select(cols),
            plastid_histogram_df.select(cols),
        ]
    )

    total_histogram = px.bar(
        combined_df,
        x="Last Update",
        y="Total Records",
        color="Type",
        category_orders={"Type": ["Total", "Mitochondrion", "Plastid"]},
        color_discrete_map={
            "Plastid": "forestgreen",
            "Mitochondrion": "yellow",
            "Total": "purple",
        },
        title="Total Annotated Records Uploaded to GenBank Over Time",
        template="none",
    )
    latest_record_date = combined_df.select(
        pl.col("Last Update").max().dt.strftime("%Y-%m-%d")
    ).item()

    total_histogram.update_layout(
        barmode="overlay",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=["2015-01-01", latest_record_date or "2015-01-01"]),
        yaxis=dict(range=[0, combined_df["Total Records"].max() or 0], title="Records"),
        font=dict(family="Merriweather, serif", color="black"),
        height=225,
    )
    total_histogram.update_traces(marker_opacity=1.0)

    total_histogram = total_histogram.to_html(
        full_html=False, include_plotlyjs=False, config={"responsive": True}
    )

    ######################
    ##### Value part #####
    ######################
    plastid_count = OrganelleMetadata.objects.filter(
        organelle_type__startswith="plastid"
    ).count()
    taxonomy_count = TaxonomyData.objects.values("genus").distinct().count()
    last_update = datetime.strptime(latest_record_date, "%Y-%m-%d").strftime("%B %d %Y")
    gene_count = (
        OrganelleMetadata.objects.aggregate(Sum("gene_count"))["gene_count__sum"] or 0
    )

    return render(
        request,
        "index.html",
        {
            "total_histogram": total_histogram,
            "plastid_count": plastid_count,
            "taxonomy_count": taxonomy_count,
            "last_update": last_update,
            "gene_count": gene_count,
        },
    )


#####################################################################


def about(request):
    return render(request, "about.html")


#####################################################################


def search(request):
    if request.method == "POST":
        # Take out white space if user makes a search.

        search_term = request.POST.get("search_term", "").strip()
        category = request.POST.get("category", "Genus and Species").strip()
        organelle_type = request.POST.get("organelle_type", "plastid").strip()
        qs = build_metadata_queryset(search_term, category, organelle_type)

        # Generate a session if not one yet made.
        if not request.session.session_key:
            request.session.create()

        # If no records found, return to results page with message.
        if not qs.exists():
            return render(
                request,
                "search/results.html",
                {
                    "search_term": search_term,
                    "results": [],
                    "total_records": 0,
                },
            )

        request.session["search_term"] = search_term

        return redirect(
            f'/results/?q={search_term or "*"}&category={category}&organelle_type={organelle_type}'
        )

    # For random results:
    if "random" in request.GET:

        organelle = request.GET.get("organelle", "")
        qs = OrganelleMetadata.objects.all()
        if organelle:
            qs = qs.filter(organelle_type__icontains=organelle)
        accessions = list(qs.values_list("accession", flat=True))
        return (
            redirect(f"/results/{choice(accessions)}/") if accessions else redirect("/")
        )

    if "q" in request.GET:
        search_term = request.GET.get("q", "")
        category = request.GET.get("category", "Genus and Species")
    else:
        search_term = request.session.get("search_term", "")
        category = request.GET.get("category", "")
    organelle_type = request.GET.get("organelle_type", "plastid")

    total_records = build_metadata_queryset(
        search_term, category, organelle_type
    ).count()
    accessions = build_metadata_queryset(
        search_term, category, organelle_type
    ).values_list("accession", flat=True)
    has_ir_data = IR_Identification.objects.filter(accession__in=accessions).exists()

    columns = [
        {"field": field, "label": RESULTS_COLUMN_LABELS[field]}
        for field in RESULTS_COLUMNS
    ]

    ir_columns = [
        {"field": field, "label": IR_RESULTS_COLUMN_LABELS[field]}
        for field in IR_RESULTS_COLUMNS
    ]

    return render(
        request,
        "search/results.html",
        {
            "search_term": search_term,
            "category": category,
            "organelle_type": organelle_type,
            "total_records": total_records,
            "columns": columns,
            "ir_columns": ir_columns,
            "has_ir_data": has_ir_data,
        },
    )


#####################################################################


def results_data(request):
    # Makes it where DataTables only loads what's needed rather than entire db.

    q = request.GET.get("q", "")
    category = request.GET.get("category", "Genus and Species")
    organelle_type = request.GET.get("organelle_type", "plastid")
    draw = _int_param(request.GET.get("draw"), 1)
    start = _int_param(request.GET.get("start"), 0)
    length = _int_param(request.GET.get("length"), 10)
    search_value = request.GET.get("search[value]", "").strip()
    order_col_index = _int_param(request.GET.get("order[0][column]"), 2)
    order_dir = request.GET.get("order[0][dir]", "desc")

    qs = build_metadata_queryset(q, category, organelle_type)
    total_cache_key = f"results_total:{category}:{organelle_type}:{q}"
    records_total = cache.get(total_cache_key)
    if records_total is None:
        records_total = qs.count()
        cache.set(total_cache_key, records_total, timeout=3600)

    # If entry has been searched.

    if search_value:
        qs = _apply_search_filter(qs, search_value)

    # Filter by organelle.

    filtered_cache_key = (
        f"results_filtered:{category}:{organelle_type}:{q}:{search_value}"
    )
    records_filtered = cache.get(filtered_cache_key)
    if records_filtered is None:
        records_filtered = qs.count() if search_value else records_total
        cache.set(filtered_cache_key, records_filtered, timeout=3600)

    if 0 <= order_col_index < len(RESULTS_DATA_FIELDS):
        order_field = RESULTS_DATA_FIELDS[order_col_index]
    else:
        order_field = "updated"
    if order_dir == "desc":
        order_field = f"-{order_field}"

    length = length if length > 0 else records_filtered or 1
    page = qs.order_by(order_field)[start : start + length].values(*RESULTS_DATA_FIELDS)

    data = [
        {
            "accession": row["accession"],
            "href": f'https://www.ncbi.nlm.nih.gov/nuccore/{row["accession"]}',
            "title": row["title"] or "",
            "updated": row["updated"].strftime("%Y/%m/%d") if row["updated"] else "",
            "bp_length": (
                row["base_pair_length"] if row["base_pair_length"] is not None else ""
            ),
            "r_rnas": (
                row["r_rnas_reported"] if row["r_rnas_reported"] is not None else ""
            ),
            "t_rnas": (
                row["t_rnas_reported"] if row["t_rnas_reported"] is not None else ""
            ),
            "gc_content": row["gc_content"],
            "ambiguity_content": row["ambiguity_content"],
            "longest_ambiguity_stretch": (
                row["longest_ambiguity_stretch"]
                if row["longest_ambiguity_stretch"] is not None
                else ""
            ),
            "gene_count": row["gene_count"] if row["gene_count"] is not None else "",
        }
        for row in page
    ]

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        }
    )


#####################################################################


def ir_data(request):
    # Same as results_data but for the chloroplast table.

    q = request.GET.get("q", "")
    category = request.GET.get("category", "Genus and Species")
    organelle_type = request.GET.get("organelle_type", "plastid")
    draw = _int_param(request.GET.get("draw"), 1)
    start = _int_param(request.GET.get("start"), 0)
    length = _int_param(request.GET.get("length"), 10)
    search_value = request.GET.get("search[value]", "").strip()
    order_col_index = _int_param(request.GET.get("order[0][column]"), 2)
    order_dir = request.GET.get("order[0][dir]", "desc")

    # Here we use build_metadata_queryset ONLY to pull accessions. Then use that to pull IR info.
    accessions = build_metadata_queryset(q, category, organelle_type).values_list(
        "accession", flat=True
    )
    qs = IR_Identification.objects.filter(accession__in=accessions)
    total_cache_key = f"ir_total:{category}:{organelle_type}:{q}"
    records_total = cache.get(total_cache_key)
    if records_total is None:
        records_total = qs.count()
        cache.set(total_cache_key, records_total, timeout=3600)

    # Makes search in table functional.

    if search_value:
        qs = _apply_search_filter(qs, search_value, fields=IR_RESULTS_DATA_FIELDS)

    # Caches depending on DataTables search box.

    filtered_cache_key = f"ir_filtered:{category}:{organelle_type}:{q}:{search_value}"
    records_filtered = cache.get(filtered_cache_key)
    if records_filtered is None:
        records_filtered = qs.count() if search_value else records_total
        cache.set(filtered_cache_key, records_filtered, timeout=3600)

    if 0 <= order_col_index < len(IR_RESULTS_DATA_FIELDS):
        order_field = IR_RESULTS_DATA_FIELDS[order_col_index]
    else:
        order_field = "updated"
    if order_dir == "desc":
        order_field = f"-{order_field}"

    length = length if length > 0 else records_filtered or 1
    page = qs.order_by(order_field)[start : start + length].values(
        *IR_RESULTS_DATA_FIELDS
    )

    data = [
        {
            "accession": row["accession"],
            "ira_reported": row["ira_reported"] or "Not Reported.",
            "ira_blastinferred": row["ira_blastinferred"] or "Not Reported.",
            "irb_reported": row["irb_reported"] or "Not Reported.",
            "irb_blastinferred": row["irb_blastinferred"] or "Not Reported.",
        }
        for row in page
    ]

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        }
    )


def general_info(request, accession):
    # Pulls together the OrganelleMetadata fields for one accession, for the
    # general organelle info page.

    ORGANELLE_TYPE_LABELS = {
        "mitochondrion": "Mitochondrion",
        "mitochondrion:kinetoplast": "Kinetoplast",
        "plastid": "Plastid",
        "plastid:chloroplast": "Chloroplast",
        "plastid:apicoplast": "Apicoplast",
        "plastid:chromoplast": "Chromoplast",
        "plastid:leucoplast": "Leucoplast",
        "plastid:cyanelle": "Cyanelle",
    }

    general_result = OrganelleMetadata.objects.filter(accession=accession).first()

    ir_result = IR_Identification.objects.filter(accession=accession).first()  # add

    is_plastid = (getattr(general_result, "organelle_type", "") or "").startswith(
        "plastid"
    )

    organelle_type = general_result.organelle_type if general_result else None
    organelle_label = (
        ORGANELLE_TYPE_LABELS.get(organelle_type) if organelle_type else None
    )

    return render(
        request,
        "search/general_info.html",
        {
            "general_result": general_result,
            "accession": accession,
            "organelle_label": organelle_label,
            "ir_result": ir_result,
            "is_plastid": is_plastid,
            "is_gene_search": request.GET.get("category", "") == "Gene",
        },
    )


def download_results(request):
    q = request.GET.get("q")
    category = request.GET.get("category")
    accession_filter = request.GET.get("accessions")

    if q is not None or category is not None:
        # Table search box mode: same filter results_data() uses, so the
        # download matches whatever's currently visible in the table.
        organelle_type = request.GET.get("organelle_type", "plastid")
        qs = build_metadata_queryset(q or "", category or "", organelle_type)
        qs = _apply_search_filter(qs, request.GET.get("search", ""))
        results = list(qs.values(*DOWNLOAD_FIELDS))
    else:
        qs = OrganelleMetadata.objects.values(*DOWNLOAD_FIELDS)
        if accession_filter:
            qs = qs.filter(accession__in=accession_filter.split(","))
        results = list(qs)

    expanded = []
    for r in results:
        gene_list = r.pop("gene_list") or {}
        if not gene_list:
            expanded.append({**r, "gene": None, "start": None, "end": None})
        for gene, locs in gene_list.items():
            for loc in locs:
                expanded.append({**r, "gene": gene, "start": loc[0], "end": loc[1]})

    df = pl.DataFrame(expanded, schema=CSV_EXPORT_SCHEMA)

    # Makes the time readable.

    df = df.with_columns(pl.col("updated").cast(pl.Datetime).dt.strftime("%Y-%m-%d"))
    df = df.rename(
        {
            "accession": "Accession",
            "title": "Title",
            "updated": "Updated",
            "base_pair_length": "Base_Pair_Length",
            "ambiguity_content": "Ambiguity_Content",
            "longest_ambiguity_stretch": "Longest_Ambiguity_Stretch",
            "gc_content": "GC_Content",
            "r_rnas_reported": "rRNAs_Reported",
            "t_rnas_reported": "tRNAs_Reported",
            "gene_count": "Gene_Count",
            "gene": "Gene",
            "start": "Start",
            "end": "End",
        }
    )
    response = HttpResponse(df.write_csv(), content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="organellequalityhub_results.csv"'
    )
    return response


def download_record_info(request, accession=None):
    accession_filter = accession or request.GET.get("accessions")
    filename = (
        f"organellequalityhub_{accession_filter}.csv"
        if accession_filter
        else "organellequalityhub_data_results.csv"
    )
    qs = OrganelleMetadata.objects.values("accession", "title")
    if accession_filter:
        qs = qs.filter(accession__in=accession_filter.split(","))
    results = list(qs)

    metadata_by_accession = {
        metadata.accession: metadata
        for metadata in OrganelleMetadata.objects.filter(
            accession__in=[result["accession"] for result in results]
        )
    }
    ir_by_accession = {
        ir.accession: ir
        for ir in IR_Identification.objects.filter(
            accession__in=[result["accession"] for result in results]
        )
    }
    any_plastid = False
    for result in results:
        metadata = metadata_by_accession.get(result["accession"])
        result["base_pair_length"] = metadata.base_pair_length if metadata else None
        result["updated"] = metadata.updated if metadata else None
        result["ambiguity_content"] = metadata.ambiguity_content if metadata else None
        result["longest_ambiguity_stretch"] = (
            metadata.longest_ambiguity_stretch if metadata else None
        )
        result["gc_content"] = metadata.gc_content if metadata else None
        result["r_rnas_reported"] = metadata.r_rnas_reported if metadata else None
        result["t_rnas_reported"] = metadata.t_rnas_reported if metadata else None
        result["gene_count"] = metadata.gene_count if metadata else None
        result["gene_list"] = metadata.gene_list if metadata else None

        result["_is_plastid"] = bool(metadata) and (
            metadata.organelle_type or ""
        ).startswith("plastid")
        any_plastid = any_plastid or result["_is_plastid"]

    expanded = []
    for r in results:
        is_plastid = r.pop("_is_plastid")
        gene_list = r.pop("gene_list") or {}
        if any_plastid:
            ir_result = ir_by_accession.get(r["accession"]) if is_plastid else None
            for field in IR_FIELDS:
                r[field] = getattr(ir_result, field) if ir_result else None
        if not gene_list:
            expanded.append({**r, "gene": None, "start": None, "end": None})
        for gene, locs in gene_list.items():
            for loc in locs:
                expanded.append({**r, "gene": gene, "start": loc[0], "end": loc[1]})

    schema = RECORD_INFO_EXPORT_SCHEMA if any_plastid else CSV_EXPORT_SCHEMA
    df = pl.DataFrame(expanded, schema=schema)

    # Makes the time readable.

    df = df.with_columns(pl.col("updated").cast(pl.Datetime).dt.strftime("%Y-%m-%d"))
    df = df.rename(
        {
            "accession": "Accession",
            "title": "Title",
            "updated": "Updated",
            "base_pair_length": "Base_Pair_Length",
            "ambiguity_content": "Ambiguity_Content",
            "longest_ambiguity_stretch": "Longest_Ambiguity_Stretch",
            "gc_content": "GC_Content",
            "r_rnas_reported": "rRNAs_Reported",
            "t_rnas_reported": "tRNAs_Reported",
            "gene_count": "Gene_Count",
            "gene": "Gene",
            "start": "Start",
            "end": "End",
            "ira_reported": "IRa_Reported",
            "ira_reported_start": "IRa_Reported_Start",
            "ira_reported_end": "IRa_Reported_End",
            "ira_reported_length": "IRa_Reported_Length",
            "ira_blastinferred": "IRa_BlastInferred",
            "ira_blastinferred_start": "IRa_BlastInferred_Start",
            "ira_blastinferred_end": "IRa_BlastInferred_End",
            "ira_blastinferred_length": "IRa_BlastInferred_Length",
            "irb_reported": "IRb_Reported",
            "irb_reported_start": "IRb_Reported_Start",
            "irb_reported_end": "IRb_Reported_End",
            "irb_reported_length": "IRb_Reported_Length",
            "irb_blastinferred": "IRb_BlastInferred",
            "irb_blastinferred_start": "IRb_BlastInferred_Start",
            "irb_blastinferred_end": "IRb_BlastInferred_End",
            "irb_blastinferred_length": "IRb_BlastInferred_Length",
        },
        strict=False,
    )
    response = HttpResponse(df.write_csv(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

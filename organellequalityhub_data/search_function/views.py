import re
from django.shortcuts import render, redirect
from .plastid_search_function import initiate_search
from .models import SearchResult
from random import choice
from plastid_interaction.models import IR_Identification
from organism_metadata.models import OrganelleMetadata
from datetime import date
import polars as pl
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.http import urlencode
import plotly.express as px

RESULTS_COLUMNS = ['Accession', 'Title', 'BP_Length', 'Updated', 'Ambiguity_Content']


def _apply_datatable_search(df, search_value):
    """Shared global-search filter for the results table and its download."""
    search_value = (search_value or '').strip()
    if not search_value or df.is_empty():
        return df
    pattern = re.escape(search_value)
    mask = pl.any_horizontal([
        pl.col(c).cast(pl.String, strict=False).str.contains(f'(?i){pattern}')
        for c in RESULTS_COLUMNS
    ])
    return df.filter(mask)

CSV_EXPORT_SCHEMA = {
    'accession': pl.String,
    'title': pl.String,
    'base_pair_length': pl.Int64,
    'updated': pl.Datetime,
    'ambiguity_content': pl.Float64,
    'gc_content': pl.Float64,
    'r_rnas_reported': pl.Int64,
    't_rnas_reported': pl.Int64,
    'gene_count': pl.Int64,
    'gene': pl.String,
    'start': pl.Int64,
    'end': pl.Int64,
}

IR_EXPORT_SCHEMA = {
    'ira_reported': pl.String,
    'ira_reported_start': pl.Int64,
    'ira_reported_end': pl.Int64,
    'ira_reported_length': pl.Int64,
    'ira_blastinferred': pl.String,
    'ira_blastinferred_start': pl.Int64,
    'ira_blastinferred_end': pl.Int64,
    'ira_blastinferred_length': pl.Int64,
    'irb_reported': pl.String,
    'irb_reported_start': pl.Int64,
    'irb_reported_end': pl.Int64,
    'irb_reported_length': pl.Int64,
    'irb_blastinferred': pl.String,
    'irb_blastinferred_start': pl.Int64,
    'irb_blastinferred_end': pl.Int64,
    'irb_blastinferred_length': pl.Int64,
}

RECORD_INFO_EXPORT_SCHEMA = {**CSV_EXPORT_SCHEMA, **IR_EXPORT_SCHEMA}

IR_FIELDS = list(IR_EXPORT_SCHEMA.keys())


def create_graph(request):
    
    # This whole part is to render a html graph.
    plastid_records = list(IR_Identification.objects.values('updated', 'accession'))
    plastid_histogram_df = pl.DataFrame(plastid_records) if plastid_records else pl.DataFrame(schema={'updated': pl.Date, 'accession': pl.String})

    plastid_histogram_df = plastid_histogram_df.filter(pl.col('updated').is_not_null())

    plastid_histogram_df = plastid_histogram_df.with_columns(pl.col('updated').cast(pl.Date))
    plastid_histogram_df = plastid_histogram_df.group_by('updated').agg(pl.len().alias('count')).sort('updated')
    plastid_full_range = pl.DataFrame({'updated': pl.date_range(plastid_histogram_df['updated'].min(), plastid_histogram_df['updated'].max(), '1d', eager=True)})
    plastid_histogram_df = (
        plastid_full_range
        .join(plastid_histogram_df, on='updated', how='left')
        .fill_null(0)
        .with_columns(pl.col('count').cum_sum().alias('Total Records'))
        .rename({'updated': 'Last Update'})
        .with_columns(pl.lit('Plastid').alias('Type'))
    )

    mito_records = list(OrganelleMetadata.objects.filter(organelle_type__startswith='mitochondrion').values('updated'))
    mito_histogram_df = pl.DataFrame(mito_records) if mito_records else pl.DataFrame(schema={'updated': pl.Date})
    mito_histogram_df = mito_histogram_df.filter(pl.col('updated').is_not_null())
    mito_histogram_df = mito_histogram_df.with_columns(pl.col('updated').cast(pl.Date))
    mito_histogram_df = mito_histogram_df.group_by('updated').agg(pl.len().alias('count')).sort('updated')
    mito_full_range = pl.DataFrame({'updated': pl.date_range(mito_histogram_df['updated'].min(), mito_histogram_df['updated'].max(), '1d', eager=True)})
    mito_histogram_df = (
        mito_full_range
        .join(mito_histogram_df, on='updated', how='left')
        .fill_null(0)
        .with_columns(pl.col('count').cum_sum().alias('Total Records'))
        .rename({'updated': 'Last Update'})
        .with_columns(pl.lit('Mitochondrion').alias('Type'))
    )

    total_df = (
        mito_histogram_df.select(['Last Update', 'Total Records'])
        .join(plastid_histogram_df.select(['Last Update', 'Total Records']), on='Last Update', how='full', coalesce=True)
        .sort('Last Update')
        .with_columns(
            pl.col('Total Records').forward_fill().fill_null(0),
            pl.col('Total Records_right').forward_fill().fill_null(0),
        )
        .with_columns((pl.col('Total Records') + pl.col('Total Records_right')).alias('Total Records'))
        .select(['Last Update', 'Total Records'])
        .with_columns(pl.lit('Total').alias('Type'))
    )

    cols = ['Last Update', 'Total Records', 'Type']
    combined_df = pl.concat([total_df.select(cols), mito_histogram_df.select(cols), plastid_histogram_df.select(cols)])

    total_histogram = px.bar(
        combined_df,
        x='Last Update',
        y='Total Records',
        color='Type',
        category_orders={'Type': ['Total', 'Mitochondrion', 'Plastid']},
        color_discrete_map={'Plastid': 'forestgreen', 'Mitochondrion': 'yellow', 'Total': 'purple'},
        title='Total Annotated Records Uploaded to GenBank Over Time',
        template='none'
    )
    latest_record_date = combined_df.select(pl.col('Last Update').max().dt.strftime('%Y-%m-%d')).item()

    total_histogram.update_layout(
        barmode='overlay',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(range=['2015-01-01', latest_record_date]),
        yaxis=dict(range=[0, combined_df['Total Records'].max()], title="Records"),
        font=dict(family='Merriweather, serif', color='black'),
    )
    total_histogram.update_traces(marker_opacity=1.0)

    total_histogram = total_histogram.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True}
    )

    return render(request, 'index.html', {'total_histogram': total_histogram})


def about(request):
    return render(request, 'about.html')


def search(request):
    if request.method == 'POST':
        if SearchResult.objects.exists():
            ''' Clear the SearchResult model at the beginning of each new search to
             keep it from being too bloated.'''
            SearchResult.objects.all().delete()

        # Take out white space if user makes a search. Convert to dictionary for model conversion.

        search_term = request.POST.get('search_term', '').strip()
        category = request.POST.get('category', 'Genus and Species').strip()
        search_query, total_records = initiate_search(search_term, category)

        # Generate a session if not one yet made.
        if not request.session.session_key:
            request.session.create()

        # If no records found, return to results page with message.
        if search_query.is_empty():
            return render(
                request,
                'search_function/results.html',
                {
                    'search_term': search_term,
                    'results': [],
                    'total_records': 0,
                }
            )

        # Sort by most recently updates THEN turn to a dictionary for model purposes.
        search_dict = search_query.sort(
            'Updated',
            descending=True,
            nulls_last=True
        ).to_dicts()

        SearchResult.objects.bulk_create([
            SearchResult(
                accession=record['Accession'],
                title=record['Title'],
            )
            for record in search_dict
        ])

        # Save terms for paginator.
        request.session['search_dict'] = search_dict
        request.session['search_term'] = search_term
        request.session['total_records'] = total_records

        return redirect(f'/results/?q={search_term or "all"}&category={category}')
    
    if 'random' in request.GET:
        organelle = request.GET.get('organelle', '')
        qs = OrganelleMetadata.objects.all()
        if organelle:
            qs = qs.filter(organelle_type__icontains=organelle)
        accessions = list(qs.values_list('accession', flat=True))
        return redirect(f'/results/{choice(accessions)}/') if accessions else redirect('/')


    # Table rows now come from results_data(); only the count is needed here.
    if 'q' in request.GET:
        search_term = request.GET.get('q', '')
        category = request.GET.get('category', 'Genus and Species')
        _, total_records = initiate_search(search_term, category)
    else:
        search_term = request.session.get('search_term', '')
        total_records = request.session.get('total_records', 0)
        category = request.GET.get('category', '')

    return render(request, 'search_function/results.html', {
        'search_term': search_term,
        'total_records': total_records,
        'category': category,
    })


def results_data(request):
    """DataTables serverSide endpoint for the results table."""
    search_term = request.GET.get('q', '')
    category = request.GET.get('category', '')
    df, total_records = initiate_search(search_term, category)

    filtered_df = _apply_datatable_search(df, request.GET.get('search[value]', ''))
    records_filtered = filtered_df.height

    order_col_idx = request.GET.get('order[0][column]', '')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_col = (
        RESULTS_COLUMNS[int(order_col_idx)]
        if order_col_idx.isdigit() and int(order_col_idx) < len(RESULTS_COLUMNS)
        else 'Updated'
    )
    if not filtered_df.is_empty():
        filtered_df = filtered_df.sort(order_col, descending=(order_dir == 'desc'), nulls_last=True)

    start = int(request.GET.get('start', 0) or 0)
    length = int(request.GET.get('length', 10) or 10)
    page_df = filtered_df.slice(start, length)

    data = [
        {
            'accession': row['Accession'],
            'href': reverse('general_info', args=[row['Accession']]) + '?' + urlencode({'category': category}),
            'title': row['Title'] or '',
            'bp_length': row['BP_Length'] if row['BP_Length'] is not None else '',
            'updated': row['Updated'] or '',
            'ambiguity_content': row['Ambiguity_Content'],
        }
        for row in page_df.to_dicts()
    ]

    return JsonResponse({
        'draw': int(request.GET.get('draw', 1) or 1),
        'recordsTotal': total_records,
        'recordsFiltered': records_filtered,
        'data': data,
    })


def general_info(request, accession):
    # Pulls together the SearchResult title and the OrganelleMetadata
    # fields for one accession, for the general organelle info page.

    ORGANELLE_TYPE_LABELS = {
        'mitochondrion': 'Mitochondrion',
        'mitochondrion:kinetoplast': 'Kinetoplast',
        'plastid': 'Plastid',
        'plastid:chloroplast': 'Chloroplast',
        'plastid:apicoplast': 'Apicoplast',
        'plastid:chromoplast': 'Chromoplast',
        'plastid:leucoplast': 'Leucoplast',
        'plastid:cyanelle': 'Cyanelle',
    }

    search_result = SearchResult.objects.filter(accession=accession).first()
    general_result = OrganelleMetadata.objects.filter(accession=accession).first()

    ir_result = IR_Identification.objects.filter(accession=accession).first()  # add

    is_plastid = (getattr(general_result, 'organelle_type', '') or '').startswith('plastid')

    return render(
        request,
        'search_function/general_info.html',
        {
            'general_result': general_result,
            'search_result': search_result,
            'accession': accession,
            'organelle_label': ORGANELLE_TYPE_LABELS.get(
                general_result.organelle_type,
                general_result.organelle_type,
            ) if general_result else None,
            'ir_result': ir_result,
            'is_plastid': is_plastid,
            'is_gene_search': request.GET.get('category', '') == 'Gene',
        }
    )


def download_results(request):
    q = request.GET.get('q')
    category = request.GET.get('category')
    accession_filter = request.GET.get('accessions')

    if q is not None or category is not None:
        # Table search box mode: same filter results_data() uses, so the
        # download matches whatever's currently visible in the table.
        df, _ = initiate_search(q or '', category or '')
        df = _apply_datatable_search(df, request.GET.get('search', ''))
        results = [{'accession': r['Accession'], 'title': r['Title']} for r in df.to_dicts()]
    else:
        qs = SearchResult.objects.values('accession', 'title')
        if accession_filter:
            qs = qs.filter(accession__in=accession_filter.split(','))
        results = list(qs)

    metadata_by_accession = {
        metadata.accession: metadata
        for metadata in OrganelleMetadata.objects.filter(
            accession__in=[result['accession'] for result in results]
        )
    }
    for result in results:
        metadata = metadata_by_accession.get(result['accession'])
        result['base_pair_length'] = metadata.base_pair_length if metadata else None
        result['updated'] = metadata.updated if metadata else None
        result['ambiguity_content'] = metadata.ambiguity_content if metadata else None
        result['gc_content'] = metadata.gc_content if metadata else None
        result['r_rnas_reported'] = metadata.r_rnas_reported if metadata else None
        result['t_rnas_reported'] = metadata.t_rnas_reported if metadata else None
        result['gene_count'] = metadata.gene_count if metadata else None
        result['gene_list'] = metadata.gene_list if metadata else None

    expanded = []
    for r in results:
        gene_list = r.pop('gene_list') or {}
        if not gene_list:
            expanded.append({**r, 'gene': None, 'start': None, 'end': None})
        for gene, locs in gene_list.items():
            for loc in locs:
                expanded.append({**r, 'gene': gene, 'start': loc[0], 'end': loc[1]})

    df = pl.DataFrame(expanded, schema=CSV_EXPORT_SCHEMA)

    #Makes the time readable.

    df = df.with_columns(pl.col('updated').cast(pl.Datetime).dt.strftime('%Y-%m-%d'))
    df = df.rename(
        {
            'accession': 'Accession',
            'title': 'Title',
            'updated': 'Updated',
            'base_pair_length': 'Base_Pair_Length',
            'ambiguity_content': 'Ambiguity_Content',
            'gc_content': 'GC_Content',
            'r_rnas_reported': 'rRNAs_Reported',
            't_rnas_reported': 'tRNAs_Reported',
            'gene_count': 'Gene_Count',
            'gene': 'Gene',
            'start': 'Start',
            'end': 'End',
        }
    )
    response = HttpResponse(df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="organellequalityhub_results.csv"'
    )
    return response

def download_record_info(request, accession=None):
    accession_filter = accession or request.GET.get('accessions')
    filename = f"organellequalityhub_{accession_filter}.csv" if accession_filter else "organellequalityhub_data_results.csv"
    qs = SearchResult.objects.values('accession', 'title')
    if accession_filter:
        qs = qs.filter(accession__in=accession_filter.split(','))
    results = list(qs)

    metadata_by_accession = {
        metadata.accession: metadata
        for metadata in OrganelleMetadata.objects.filter(
            accession__in=[result['accession'] for result in results]
        )
    }
    ir_by_accession = {
        ir.accession: ir
        for ir in IR_Identification.objects.filter(
            accession__in=[result['accession'] for result in results]
        )
    }
    any_plastid = False
    for result in results:
        metadata = metadata_by_accession.get(result['accession'])
        result['base_pair_length'] = metadata.base_pair_length if metadata else None
        result['updated'] = metadata.updated if metadata else None
        result['ambiguity_content'] = metadata.ambiguity_content if metadata else None
        result['gc_content'] = metadata.gc_content if metadata else None
        result['r_rnas_reported'] = metadata.r_rnas_reported if metadata else None
        result['t_rnas_reported'] = metadata.t_rnas_reported if metadata else None
        result['gene_count'] = metadata.gene_count if metadata else None
        result['gene_list'] = metadata.gene_list if metadata else None

        result['_is_plastid'] = bool(metadata) and (metadata.organelle_type or '').startswith('plastid')
        any_plastid = any_plastid or result['_is_plastid']

    expanded = []
    for r in results:
        is_plastid = r.pop('_is_plastid')
        gene_list = r.pop('gene_list') or {}
        if any_plastid:
            ir_result = ir_by_accession.get(r['accession']) if is_plastid else None
            for field in IR_FIELDS:
                r[field] = getattr(ir_result, field) if ir_result else None
        if not gene_list:
            expanded.append({**r, 'gene': None, 'start': None, 'end': None})
        for gene, locs in gene_list.items():
            for loc in locs:
                expanded.append({**r, 'gene': gene, 'start': loc[0], 'end': loc[1]})

    schema = RECORD_INFO_EXPORT_SCHEMA if any_plastid else CSV_EXPORT_SCHEMA
    df = pl.DataFrame(expanded, schema=schema)

    #Makes the time readable.

    df = df.with_columns(pl.col('updated').cast(pl.Datetime).dt.strftime('%Y-%m-%d'))
    df = df.rename(
        {
            'accession': 'Accession',
            'title': 'Title',
            'updated': 'Updated',
            'base_pair_length': 'Base_Pair_Length',
            'ambiguity_content': 'Ambiguity_Content',
            'gc_content': 'GC_Content',
            'r_rnas_reported': 'rRNAs_Reported',
            't_rnas_reported': 'tRNAs_Reported',
            'gene_count': 'Gene_Count',
            'gene': 'Gene',
            'start': 'Start',
            'end': 'End',
            'ira_reported': 'IRa_Reported',
            'ira_reported_start': 'IRa_Reported_Start',
            'ira_reported_end': 'IRa_Reported_End',
            'ira_reported_length': 'IRa_Reported_Length',
            'ira_blastinferred': 'IRa_BlastInferred',
            'ira_blastinferred_start': 'IRa_BlastInferred_Start',
            'ira_blastinferred_end': 'IRa_BlastInferred_End',
            'ira_blastinferred_length': 'IRa_BlastInferred_Length',
            'irb_reported': 'IRb_Reported',
            'irb_reported_start': 'IRb_Reported_Start',
            'irb_reported_end': 'IRb_Reported_End',
            'irb_reported_length': 'IRb_Reported_Length',
            'irb_blastinferred': 'IRb_BlastInferred',
            'irb_blastinferred_start': 'IRb_BlastInferred_Start',
            'irb_blastinferred_end': 'IRb_BlastInferred_End',
            'irb_blastinferred_length': 'IRb_BlastInferred_Length',
        },
        strict=False,
    )
    response = HttpResponse(df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

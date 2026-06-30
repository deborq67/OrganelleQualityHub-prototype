from django.shortcuts import render, redirect
from .plastid_search_function import initiate_search
from .accessions import attach_ir_status
from .models import SearchResult, SearchHistory
from genbank_interaction.models import IR_Identification
from organism_metadata.models import OrganelleMetadata
from datetime import date
import polars as pl
from django.http import HttpResponse
import plotly.express as px
from django.core.paginator import (Paginator, EmptyPage, PageNotAnInteger)


def get_page_range(paginator, current_page, max_pages=6):
    ''' Caps the number of page shown to 6. Once there are more pages than
     6, the leading block follows the current page (e.g. on page 4:
     2 3 4 ... 18 19 20), while the trailing block stays anchored to the
     last page. Once the leading block would close in on the trailing one,
     show as continuous instead of a ...'''
    total_pages = paginator.num_pages
    if total_pages <= max_pages:
        return list(range(1, total_pages + 1))

    edge = max_pages // 2

    if current_page >= total_pages - max_pages + 1:
        left_start = max(1, total_pages - max_pages + 1)
        return list(range(left_start, total_pages + 1))

    left_end = max(edge, current_page)
    left_block = list(range(left_end - edge + 1, left_end + 1))
    right_block = list(range(total_pages - edge + 1, total_pages + 1))

    return left_block + [None] + right_block


def index(request):
    
    # This whole part is to render a html graph.
    records = list(IR_Identification.objects.values('updated', 'accession'))
    histogram_df = pl.DataFrame(records) if records else pl.DataFrame(schema={'updated': pl.Date, 'accession': pl.String})

    histogram_df = histogram_df.filter(pl.col('updated').is_not_null())

    histogram_df = histogram_df.with_columns(pl.col('updated').cast(pl.Date))
    histogram_df = histogram_df.group_by('updated').agg(pl.len().alias('count')).sort('updated')
    full_range = pl.DataFrame({'updated': pl.date_range(histogram_df['updated'].min(), histogram_df['updated'].max(), '1d', eager=True)})
    histogram_df = (
        full_range
        .join(histogram_df, on='updated', how='left')
        .fill_null(0)
        .with_columns(pl.col('count').cum_sum().alias('Total Records'))
        .rename({'updated': 'Last Update'})
    )

    plastid_histogram = px.bar(
        histogram_df,
        x='Last Update',
        y='Total Records',
        title='Total Annotated Plastid Records Uploaded to GenBank Over Time',
        template='none'
    )
    plastid_histogram.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(range=['2015-01-01', date.today().isoformat()]),
        yaxis=dict(rangemode='nonnegative', title="Records"),
        font=dict(family='Patrick Hand, cursive'),
    )

    plastid_histogram = plastid_histogram.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True}
    )

    return render(request, 'index.html', {'plastid_histogram': plastid_histogram})


def about(request):
    return render(request, 'about.html')


def search(request):
    if request.method == 'POST':
        if SearchResult.objects.exists():
            ''' Clear the SearchResult model at the beginning of each new search to
             keep it from being too bloated. It's only meant to
            link to SearchHistory anyway, which is persistent.'''
            SearchResult.objects.all().delete()

        # Take out white space if user makes a search. Convert to dictionary for model conversion.

        search_term = request.POST.get('search_term', '').strip()
        category = request.POST.get('category', 'Genus & Species').strip()
        search_query, total_records = initiate_search(search_term, category)

        # Generate a session if not one yet made.
        if not request.session.session_key:
            request.session.create()

        # If no records found, return to results page with message.
        if search_query.is_empty():
            SearchHistory.objects.create(
                session_key=request.session.session_key,
                search_term=search_term,
                total_records=0,
                search_accessions='',
            )
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

        # Put the search term into history.
        history_record = SearchHistory.objects.create(
            session_key=request.session.session_key,
            search_term=search_term,
            total_records=total_records,
            search_accessions=','.join(
                [record['Accession'] for record in search_dict]
            )
        )

        SearchResult.objects.bulk_create([
            SearchResult(
                accession=record['Accession'],
                title=record['Title'],
            )
            for record in search_dict
        ])

        # Save history.
        history_record.save()

        # Save terms for paginator.
        request.session['search_dict'] = search_dict
        request.session['search_term'] = search_term
        request.session['total_records'] = total_records

        return redirect('/results/')

    # Use search results for paginator.
    search_dict = request.session.get('search_dict', [])
    search_term = request.session.get('search_term', '')
    total_records = request.session.get('total_records', 0)

    return render(request, 'search_function/results.html', {
        'search_term': search_term,
        'results': search_dict,
        'total_records': total_records,
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
        }
    )


# This loads the history into a table.
def history(request):
    if not request.session.session_key:
        request.session.create()
    history_records = SearchHistory.objects.filter(
        session_key=request.session.session_key
    ).values('id', 'search_term', 'total_records', 'searched_at').order_by('-searched_at')
   
    #Once again using a paginator.
    default_page = 1
    page = request.GET.get('page', default_page)
    paginator = Paginator(history_records, 20)
    try:
        results_page = paginator.page(page)
    except PageNotAnInteger:
        results_page = paginator.page(default_page)
    except EmptyPage:
        results_page = paginator.page(paginator.num_pages)

    return render(request, 'search_function/history.html', {
        'history_records': results_page,
        'page_range': get_page_range(paginator, results_page.number),
    })


# This extracts a list of Accession numbers for a separate page.
def accession_list(request):
    #Linked to search ID.
    search_id = request.GET.get('id')
    history_accessions = SearchHistory.objects.get(
        id=search_id, session_key=request.session.session_key
    ).search_accessions.split(',')

    #Prevents crash if there are no accessions. Also sorts the accessions alphabetically.
    history_accessions = [accession for accession in history_accessions if accession]
    history_accessions.sort()
    history_accessions = attach_ir_status(history_accessions)
    return render(
        request,
        'search_function/accessions.html',
        {
            'history_accessions': history_accessions,
            'search_id': search_id
        }
    )


def download_results(request):
    results = list(SearchResult.objects.values('accession', 'title'))

    metadata_by_accession = {
        metadata.accession: metadata
        for metadata in OrganelleMetadata.objects.filter(
            accession__in=[result['accession'] for result in results]
        )
    }
    for result in results:
        metadata = metadata_by_accession.get(result['accession'])
        result['bp_length'] = metadata.base_pair_length if metadata else None
        result['updated'] = metadata.updated if metadata else None
        result['ambiguity_content'] = metadata.ambiguity_content if metadata else None

    df = pl.DataFrame(results)

    #Makes the time readable.

    df = df.with_columns(pl.col('updated').cast(pl.Datetime).dt.strftime('%Y-%m-%d'))
    df = df.rename(
        {
            'accession': 'Accession',
            'title': 'Title',
            'bp_length': 'Base_Pair_Length',
            'updated': 'Updated',
            'ambiguity_content': 'Ambiguity_Content',
        }
    )
    response = HttpResponse(df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="organellequalityhub_data_results.csv"'
    )
    return response


def download_history(request):

    # Same logic as download_results, but for the history page.

    df = pl.DataFrame(list(SearchHistory.objects.filter(
        session_key=request.session.session_key
    ).values('search_term', 'total_records', 'searched_at')))
    df = df.with_columns(pl.col('searched_at').cast(pl.Datetime).dt.strftime('%Y-%m-%d %H:%M:%S'))
    df = df.rename(
        {
            'search_term': 'Search_Term',
            'total_records': 'Records_Found',
            'searched_at': 'Timestamp'
        }
    )
    response = HttpResponse(df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="organellequalityhub_data_history.csv"'
    )
    return response


def download_accessions(request):
    # Same logic as download_results, but for the accession records.

    search_id = request.GET.get('id')
    history_accession_df = pl.DataFrame(
        list(SearchHistory.objects.values('id', 'search_accessions'))
    )
    history_accession_df = (
        history_accession_df
        # Splits the comma-separated accessions into a list and then explodes for one accession per row.
        .with_columns(
            pl.col('search_accessions').str.split(',')
        )
        .explode('search_accessions')
    )
    history_accession_df = history_accession_df.rename({'search_accessions': 'accession'})

    ir_info_df = pl.DataFrame(
        list(IR_Identification.objects.values('accession', 'ir_reported'))
    )
    final_df = (
        history_accession_df
        .filter(pl.col('id') == int(search_id))
        .join(ir_info_df, on='accession', how='inner')
    )
    final_df = final_df.rename({
        'accession': 'Accession_ID',
        'ir_reported': 'IR_Reported'
    })
    final_df = final_df.drop('id')
    if final_df.is_empty():
        final_df = pl.DataFrame({'Accession_ID': [], 'IR_Reported': []})
    response = HttpResponse(final_df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="plastid_ir_history_accessions.csv"'
    )
    return response

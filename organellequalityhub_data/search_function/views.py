from django.shortcuts import render, redirect
from .plastid_search_function import initiate_search
from .models import SearchResult, SearchHistory
from genbank_interaction.models import IR_Identification
from datetime import datetime, date
import polars as pl
from django.http import HttpResponse
import plotly.express as px
from django_pandas.io import read_frame
from django.core.paginator import (Paginator, EmptyPage, PageNotAnInteger)


def index(request):
    # This whole part is to render a html graph.
    histogram_qs = IR_Identification.objects.all()
    histogram_df = read_frame(histogram_qs, fieldnames=['updated', 'accession', 'ir_reported'])

    histogram_df = pl.from_pandas(histogram_df)

    histogram_df = histogram_df.filter(pl.col('updated').is_not_null())
    histogram_df = histogram_df.filter(pl.col('ir_reported') == 'Yes')
    histogram_df = histogram_df.drop('ir_reported')

    histogram_df = histogram_df.with_columns(pl.col('updated').cast(pl.Date))
    histogram_df = histogram_df.rename(
        {'accession': 'Accession IDs', 'updated': 'Last Update'}
    )

    plastid_histogram = px.histogram(
        histogram_df,
        x='Last Update',
        title='Total Annotated Plastid Records Uploaded to GenBank Over Time',
        template='none'
    )

    plastid_histogram.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(range=['2015-01-01', date.today().isoformat()]),
        yaxis=dict(rangemode='nonnegative', title="Records"),
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
        search_query, total_records = initiate_search(search_term)

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
            return render(request, 'search_function/results.html', {
            'search_term': search_term,
            'results': [],
            'total_records': 0,
            })
        
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

        # Make a dictionary of dictionaries
        result_instances = []

        for record in search_dict:
            ir_result = IR_Identification.objects.filter(
                accession=record['Accession']
            ).first()
            result = SearchResult.objects.create(
                accession=record['Accession'],
                title=record['Title'],
                bp_length=record['BP_Length'],
                updated=datetime.strptime(
                    record['Updated'],
                    '%Y/%m/%d'
                ) if record['Updated'] else None,
                created=datetime.strptime(
                    record['Created'],
                    '%Y/%m/%d'
                ) if record['Created'] else None,
                ir_info=ir_result,
            )
            result_instances.append(result)
            if ir_result:
                record['ir_reported'] = ir_result.ir_reported
            else:
                record['ir_reported'] = 'n/a'

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

    # Do it by 20 results per page.
    default_page = 1
    page = request.GET.get('page', default_page)
    paginator = Paginator(search_dict, 20)
    try:
        results_page = paginator.page(page)
    except PageNotAnInteger:
        results_page = paginator.page(default_page)
    except EmptyPage:
        results_page = paginator.page(paginator.num_pages)

    return render(request, 'search_function/results.html', {
        'search_term': search_term,
        'results': results_page,
        'total_records': total_records,
    })


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

    return render(request, 'search_function/history.html', {'history_records': results_page})


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
    return render(
        request,
        'search_function/accessions.html',
        {
            'history_accessions': history_accessions,
            'search_id': search_id
        }
    )


def download_results(request):
    # Django-Pandas is great at turning the df into a Pandas df since there
    # isn't really a good Polars equivalent. From there I can convert to
    # Polars and do the rest.
    searchresult_qs = SearchResult.objects.all()
    df = read_frame(
        searchresult_qs,
        fieldnames=[
            'accession',
            'title',
            'bp_length',
            'updated',
            'created',
            'ir_info__ir_reported'
        ]
    )
    #Main thing here is formatting the time.
    df = pl.from_pandas(df)
    df = df.with_columns(pl.col('updated').dt.strftime('%Y-%m-%d'))
    df = df.with_columns(pl.col('created').dt.strftime('%Y-%m-%d'))
    #Make rows human-readable.
    df = df.rename(
        {
            'accession': 'Accession',
            'title': 'Title',
            'bp_length': 'Base_Pair_Length',
            'updated': 'Updated',
            'created': 'Created',
            'ir_info__ir_reported': 'IRs_Reported'
        }
    )
    response = HttpResponse(df.write_csv(), content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="plastid_ir_search_results.csv"'
    )
    return response


def download_history(request):
    # Same logic as download_results, but for the history page.

    searchhistory_qs = SearchHistory.objects.filter(
        session_key=request.session.session_key
    )
    df = read_frame(
        searchhistory_qs,
        fieldnames=['search_term', 'total_records', 'searched_at']
    )
    df = pl.from_pandas(df)
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
        'attachment; filename="plastid_ir_search_history.csv"'
    )
    return response


def download_accessions(request):
    # Same logic as download_results, but for the accession records.

    search_id = request.GET.get('id')
    searchhistory_qs = SearchHistory.objects.all()
    history_accession_df = read_frame(
        searchhistory_qs,
        fieldnames=['id', 'search_accessions']
    )
    history_accession_df = pl.from_pandas(history_accession_df)
    history_accession_df = (
        history_accession_df
        # Splits the comma-separated accessions into a list and then explodes for one accession per row.
        .with_columns(
            pl.col('search_accessions').str.split(',')
        )
        .explode('search_accessions')
    )
    history_accession_df = history_accession_df.rename({'search_accessions': 'accession'})

    ir_info_qs = IR_Identification.objects.all()
    ir_info_df = read_frame(ir_info_qs, fieldnames=['accession', 'ir_reported'])
    ir_info_df = pl.from_pandas(ir_info_df)
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

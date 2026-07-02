from django.contrib import admin
from django.urls import path
from search_function.views import (
    search,
    general_info,
    create_graph,
    history,
    download_history,
    download_results,
    download_record_info,
    accession_list,
    download_accessions,
    about,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', create_graph, name='index'),
    path('results/', search, name='search'),
    path('results/download/', download_results, name='download_results'),
    path('results/<str:accession>/download/', download_record_info, name='download_record_info'),
    path('results/<str:accession>/', general_info, name='general_info'),
    path('history/', history, name='history'),
    path('history/accessions/', accession_list, name='accession_list'),
    path('history/download/', download_history, name='download_history'),
    path('history/accession/download/', download_accessions, name='download_accessions'),
    path('about/', about, name='about'),
]

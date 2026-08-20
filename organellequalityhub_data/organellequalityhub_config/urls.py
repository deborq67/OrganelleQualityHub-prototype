from django.contrib import admin
from django.urls import path
from search_function.views import (
    search,
    results_data,
    ir_data,
    general_info,
    create_graph,
    download_results,
    download_record_info,
    about,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", create_graph, name="index"),
    path("results/", search, name="search"),
    path("results/data/", results_data, name="results_data"),
    path("results/ir-data/", ir_data, name="ir_data"),
    path("results/download/", download_results, name="download_results"),
    path(
        "results/<str:accession>/download/",
        download_record_info,
        name="download_record_info",
    ),
    path("results/<str:accession>/", general_info, name="general_info"),
    path("about/", about, name="about"),
]

from django.shortcuts import render

from .models import IR_Identification
from search_function.models import SearchResult


def ir_info(request, accession):
    # ir_setup already sets up the model for us so all we need to really do is
    # associate SearchResult's Accession # with the IR_Identification model's
    # Accession #.

    search_result = SearchResult.objects.filter(accession=accession).first()
    ir_result = IR_Identification.objects.filter(accession=accession).first()

    return render(
        request,
        'genbank_interaction/info.html',
        {
            'ir_result': ir_result,
            'search_result': search_result,
            'accession': accession,
        }
    )





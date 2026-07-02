from django.shortcuts import render

from .models import IR_Identification
from search_function.models import SearchResult


def ir_info(request, accession):

 # We associate SearchResult's accession with the IR_Identification model's accession.


    search_result = SearchResult.objects.filter(accession=accession).first()
    ir_result = IR_Identification.objects.filter(accession=accession).first()

    return render(
        request,
        'plastid_interaction/ir_info.html',
        {
            'ir_result': ir_result,
            'search_result': search_result,
            'accession': accession,
        }
    )





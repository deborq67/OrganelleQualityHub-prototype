from genbank_interaction.models import IR_Identification

'''
Purpose: Attaches IR-reported status to a list of accessions, used by the
accessions page rather than the search results page.
'''


def attach_ir_status(accessions):
    # Bulk-fetch IR info instead of querying per record to avoid an N+1
    # round trip to the remote database for every single result.
    ir_by_accession = {
        ir.accession: ir
        for ir in IR_Identification.objects.filter(accession__in=accessions)
    }

    return [
        {
            'accession': accession,
            'ir_reported': (
                ir_by_accession[accession].ir_reported
                if accession in ir_by_accession else 'n/a'
            ),
        }
        for accession in accessions
    ]

from django.core.management.base import BaseCommand, CommandError

from pipelines.analyses.metadata_extraction import DEFAULT_WORKERS, DEFAULT_CHUNKSIZE, run
from pipelines.exceptions import PipelineError


class Command(BaseCommand):
    help = 'Extracts taxonomy and organelle stats from GenBank files into TaxonomyData and OrganelleMetadata.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Files per worker task. Smaller = more frequent DB flushes and '
                                 f'less work lost on a crash; larger = less IPC overhead on fast/many-core '
                                 f'hardware (default: auto, capped at {DEFAULT_CHUNKSIZE}).')

    def handle(self, *args, **options):
        try:
            stats_written, tax_written, new_taxa_seen = run(options, self.stdout, self.style)
        except PipelineError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(
            f'Done. Wrote {stats_written} organelle metadata record(s), '
            f'{tax_written} taxonomy record(s) ({new_taxa_seen} new NCBI lookups).'
        ))

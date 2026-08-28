from django.core.management.base import BaseCommand, CommandError

from pipelines.analyses.genome_map_upload import DEFAULT_WORKERS, run
from pipelines.exceptions import PipelineError


class Command(BaseCommand):
    help = ('Generates circular genome-map PNGs from plastid_files/, uploads them to '
            'Supabase Storage (bucket: genome_graphs), and records URLs in the DB.')

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true',
                            help='Re-generate and re-upload maps that are already in the DB.')
        parser.add_argument('--keep-local', action='store_true',
                            help='Keep local PNG files after uploading (default: delete to save disk).')
        parser.add_argument('--limit', type=int, default=None,
                            help='Process at most N GenBank files (useful for testing).')
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes for PNG rendering (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--legend', action='store_true',
                            help='Also generate and upload a Legend.png to the bucket root.')

    def handle(self, *args, **options):
        try:
            legend_uploaded = run(options, self.stdout)
        except PipelineError as e:
            raise CommandError(str(e)) from e

        if legend_uploaded:
            self.stdout.write(self.style.SUCCESS('Legend uploaded.'))
        self.stdout.write(self.style.SUCCESS('Done.'))

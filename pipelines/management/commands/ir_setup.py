from django.core.management.base import BaseCommand, CommandError

from pipelines.analyses.ir_identification_batch import DEFAULT_WORKERS, DEFAULT_CHUNKSIZE, run
from pipelines.exceptions import PipelineError


class Command(BaseCommand):
    help = 'Processes all GB files and saves IR Identification.'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--update",
            "-u",
            action="store_true",
            help="Updates duplicates instead of ignoring them.",
        )
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Files per worker task. Smaller = more frequent DB flushes and '
                                 f'less work lost on a crash; larger = less IPC overhead on fast/many-core '
                                 f'hardware (default: auto, capped at {DEFAULT_CHUNKSIZE}).')

    def handle(self, *args, **options):
        try:
            written, verb = run(options, self.stdout, self.style)
        except PipelineError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(f'{verb} {written} entries total.'))

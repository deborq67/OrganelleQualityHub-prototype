from django.core.management.base import BaseCommand, CommandError

from pipelines.analyses.ir_confirmation_batch import DEFAULT_WORKERS, DEFAULT_CHUNKSIZE, run
from pipelines.exceptions import PipelineError


class Command(BaseCommand):
    help = 'Re-confirms IR positions via self-BLAST, writing results onto IR_Identification.'

    def add_arguments(self, parser):
        parser.add_argument('--update', '-u', action='store_true',
                            help='Re-run and overwrite accessions already confirmed.')
        parser.add_argument('--minlength', '-min', type=int, default=10000,
                            help='Minimum IR length for BLAST filtering (default: 10000).')
        parser.add_argument('--maxlength', '-max', type=int, default=50000,
                            help='Maximum IR length for BLAST filtering (default: 50000).')
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Accessions per worker task. Smaller = more frequent DB flushes and '
                                 f'less work lost on a crash; larger = less IPC overhead on fast/many-core '
                                 f'hardware (default: auto, capped at {DEFAULT_CHUNKSIZE}).')

    def handle(self, *args, **options):
        try:
            written = run(options, self.stdout, self.style)
        except PipelineError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(f'Confirmed {written} accession(s) total.'))

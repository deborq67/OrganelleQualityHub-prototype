from django.core.management.base import BaseCommand, CommandError

from pipelines.analyses.gene_list_backfill import DEFAULT_WORKERS, DEFAULT_CHUNKSIZE, run
from pipelines.exceptions import PipelineError


class Command(BaseCommand):
    help = 'One-off: backfills gene_list and/or longest_ambiguity_stretch (pick via -o) on existing OrganelleMetadata rows from their GenBank files.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=None,
                            help=f'Number of worker processes (default: {DEFAULT_WORKERS}).')
        parser.add_argument('--chunksize', type=int, default=None,
                            help=f'Files per worker task (default: auto, capped at {DEFAULT_CHUNKSIZE}).')
        parser.add_argument('--limit', type=int, default=None,
                            help='Process at most N rows (useful for testing storage impact before a full run).')
        parser.add_argument('-o', '--only', action='append', required=True,
                            choices=['genes', 'amb_length'],
                            help='Field to backfill: "genes" (gene_list) or "amb_length" '
                                 '(longest_ambiguity_stretch). Repeat to backfill both: '
                                 '-o genes -o amb_length.')

    def handle(self, *args, **options):
        try:
            updated, failed, missing_files = run(options, self.stdout, self.style)
        except PipelineError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(
            f'Done. Backfilled {updated} row(s), {failed} failed, {missing_files} skipped (no file).'
        ))

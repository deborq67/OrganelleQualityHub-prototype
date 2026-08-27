import datetime
import sys

from django.core.management.base import BaseCommand

from organelle_file_generator.organelle_file_finder import download_mitochondrial_files, download_plastid_files


class Command(BaseCommand):
    help = 'Generates Genbank files for organelles.'

    def handle(self, *args, **options):
        download_plastid_files()
        download_mitochondrial_files()
        self.stdout.write(datetime.datetime.now().isoformat())
        sys.stdout.flush()
        return

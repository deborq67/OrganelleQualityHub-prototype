import os
import multiprocessing
from multiprocessing import Pool

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

DEFAULT_WORKERS = 2  # capped for memory-constrained hardware (e.g. Pi 3B+)


def _render_worker(args):
    """Generate a single circular genome map PNG.

    Runs inside a worker process; sets up Django so genome_graph can import models.
    """
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organellequalityhub_config.settings')
    django.setup()

    from genome_map.genome_graph import generate_map, OUTPUT_DIR
    gb_path, ir_data = args
    accession = os.path.splitext(os.path.basename(gb_path))[0]
    svg_path  = os.path.join(OUTPUT_DIR, accession + '.svg')
    try:
        generate_map(gb_path, ir_data=ir_data)
        return accession, svg_path, None
    except Exception as exc:
        return accession, svg_path, str(exc)


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

    def _upload_legend(self, client, bucket):
        from genome_map.genome_graph import save_legend
        legend_path = save_legend()
        with open(legend_path, 'rb') as f:
            data = f.read()
        client.storage.from_(bucket).upload(
            path='Legend.svg',
            file=data,
            file_options={'content-type': 'image/svg+xml', 'upsert': 'true'},
        )

    def handle(self, *args, **options):
        from genome_map.genome_graph import OUTPUT_DIR
        from genome_map.models import GenomeMap
        from plastid_interaction.models import IR_Identification
        from supabase import create_client

        plastid_dir = os.path.join(settings.GENBANK_ROOT, 'plastid_files')
        if not os.path.isdir(plastid_dir):
            raise CommandError(f'plastid_files/ not found at {plastid_dir}. Run ir_setup first.')

        gb_files = sorted(
            e.path for e in os.scandir(plastid_dir)
            if e.name.endswith('.gb')
        )
        if not gb_files:
            raise CommandError('No .gb files found in plastid_files/.')

        if not options['update']:
            uploaded = set(GenomeMap.objects.values_list('accession', flat=True))
            gb_files = [f for f in gb_files
                        if os.path.splitext(os.path.basename(f))[0] not in uploaded]
            if not gb_files:
                self.stdout.write('All maps are already uploaded. Use --update to re-upload.')
                return

        if options['limit']:
            gb_files = gb_files[:options['limit']]

        self.stdout.write(f'{len(gb_files)} file(s) to process.')

        # Build IR data lookup from IR_Identification's BLAST-confirmed fields
        ir_lookup = {
            row['accession']: {k: v for k, v in row.items() if k != 'accession'}
            for row in IR_Identification.objects.values(
                'accession',
                'ira_blastinferred', 'ira_blastinferred_start',
                'ira_blastinferred_end', 'ira_blastinferred_length',
                'irb_blastinferred', 'irb_blastinferred_start',
                'irb_blastinferred_end', 'irb_blastinferred_length',
            )
        }

        tasks = [
            (f, ir_lookup.get(os.path.splitext(os.path.basename(f))[0]))
            for f in gb_files
        ]

        n_workers = options['workers'] or DEFAULT_WORKERS
        self.stdout.write(f'Rendering with {n_workers} worker process(es)…')

        supabase_url = getattr(settings, 'SUPABASE_URL', '')
        supabase_key = getattr(settings, 'SUPABASE_SERVICE_KEY', '')
        if not supabase_url or not supabase_key:
            raise CommandError('SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file.')

        client = create_client(supabase_url, supabase_key)
        bucket = 'genome_graphs'

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        with Pool(n_workers) as pool:
            for accession, svg_path, err in pool.imap_unordered(_render_worker, tasks):
                if err:
                    self.stdout.write(f'  ✗ {accession}: {err}')
                    continue
                if not os.path.isfile(svg_path):
                    self.stdout.write(f'  ✗ {accession}: SVG not found after render')
                    continue
                try:
                    with open(svg_path, 'rb') as f:
                        data = f.read()
                    storage_path = f'{accession}.svg'
                    client.storage.from_(bucket).upload(
                        path=storage_path,
                        file=data,
                        file_options={'content-type': 'image/svg+xml', 'upsert': 'true'},
                    )
                    public_url = client.storage.from_(bucket).get_public_url(storage_path)
                    GenomeMap.objects.update_or_create(
                        accession=accession,
                        defaults={'storage_path': storage_path, 'public_url': public_url},
                    )
                    self.stdout.write(f'  ✓ {accession}')
                except Exception as exc:
                    self.stdout.write(f'  ✗ Upload failed: {exc}')
                finally:
                    if not options['keep_local'] and os.path.isfile(svg_path):
                        os.remove(svg_path)

        if options['legend']:
            try:
                self._upload_legend(client, bucket)
                self.stdout.write(self.style.SUCCESS('Legend uploaded.'))
            except Exception as exc:
                self.stdout.write(f'Legend upload failed: {exc}')

        self.stdout.write(self.style.SUCCESS('Done.'))

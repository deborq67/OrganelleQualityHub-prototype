"""Renders circular genome-map SVGs and uploads them to Supabase Storage (bucket: genome_graphs).

Extracted from pipelines/management/commands/genome_upload.py so the command
stays a thin CLI wrapper and this logic can be tested/imported independently.
"""
import os
from multiprocessing import Pool

from django.conf import settings

from pipelines.exceptions import PipelineError

DEFAULT_WORKERS = 2  # capped for memory-constrained hardware (e.g. Pi 3B+)


def _render_worker(args):
    """Generate a single circular genome map SVG.

    Runs inside a worker process; sets up Django so genome_graph can import models.
    """
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    django.setup()

    from pipelines.analyses.genome_graph import generate_map, OUTPUT_DIR
    gb_path, ir_data = args
    accession = os.path.splitext(os.path.basename(gb_path))[0]
    svg_path = os.path.join(OUTPUT_DIR, accession + '.svg')
    try:
        generate_map(gb_path, ir_data=ir_data)
        return accession, svg_path, None
    except Exception as exc:
        return accession, svg_path, str(exc)


def upload_legend(client, bucket):
    from pipelines.analyses.genome_graph import save_legend
    legend_path = save_legend()
    with open(legend_path, 'rb') as f:
        data = f.read()
    client.storage.from_(bucket).upload(
        path='Legend.svg',
        file=data,
        file_options={'content-type': 'image/svg+xml', 'upsert': 'true'},
    )


def run(options, stdout):
    """Renders + uploads genome maps for plastid_files/. Returns True if the legend was requested and uploaded."""
    from pipelines.analyses.genome_graph import OUTPUT_DIR
    from apps.genome_maps.models import GenomeMap
    from apps.inverted_repeats.models import IR_Identification
    from supabase import create_client

    plastid_dir = os.path.join(settings.GENBANK_ROOT, 'plastid_files')
    if not os.path.isdir(plastid_dir):
        raise PipelineError(f'plastid_files/ not found at {plastid_dir}. Run ir_setup first.')

    gb_files = sorted(
        e.path for e in os.scandir(plastid_dir)
        if e.name.endswith('.gb')
    )
    if not gb_files:
        raise PipelineError('No .gb files found in plastid_files/.')

    if not options['update']:
        uploaded = set(GenomeMap.objects.values_list('accession', flat=True))
        gb_files = [f for f in gb_files
                    if os.path.splitext(os.path.basename(f))[0] not in uploaded]
        if not gb_files:
            stdout.write('All maps are already uploaded. Use --update to re-upload.')
            return False

    if options['limit']:
        gb_files = gb_files[:options['limit']]

    stdout.write(f'{len(gb_files)} file(s) to process.')

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
    stdout.write(f'Rendering with {n_workers} worker process(es)…')

    supabase_url = getattr(settings, 'SUPABASE_URL', '')
    supabase_key = getattr(settings, 'SUPABASE_SERVICE_KEY', '')
    if not supabase_url or not supabase_key:
        raise PipelineError('SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file.')

    client = create_client(supabase_url, supabase_key)
    bucket = 'genome_graphs'

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with Pool(n_workers) as pool:
        for accession, svg_path, err in pool.imap_unordered(_render_worker, tasks):
            if err:
                stdout.write(f'  ✗ {accession}: {err}')
                continue
            if not os.path.isfile(svg_path):
                stdout.write(f'  ✗ {accession}: SVG not found after render')
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
                stdout.write(f'  ✓ {accession}')
            except Exception as exc:
                stdout.write(f'  ✗ Upload failed: {exc}')
            finally:
                if not options['keep_local'] and os.path.isfile(svg_path):
                    os.remove(svg_path)

    if options['legend']:
        try:
            upload_legend(client, bucket)
            return True
        except Exception as exc:
            stdout.write(f'Legend upload failed: {exc}')

    return False

from Bio import Entrez, SeqIO
from dotenv import load_dotenv
from http.client import IncompleteRead
import io, os, time, sys
from django.conf import settings
from django.core.cache import cache

load_dotenv()
Entrez.email   = os.getenv("ncbi_email")
Entrez.api_key = os.getenv("ncbi_api_key")


def download_plastid_files(target_dir=None):
    target_dir = target_dir or os.path.join(settings.GENBANK_ROOT, 'plastid_files')
    plastid_query = '(chloroplast[filter] OR plastid[filter]) AND "complete genome"[Title]'
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    cached = cache.get(plastid_query)
    if cached:
        return cached
    handle = Entrez.esearch(db="nuccore", term=plastid_query, retmax=0, usehistory="y")
    record = Entrez.read(handle)
    handle.close()
    total     = int(record["Count"])
    web_env   = record["WebEnv"]
    query_key = record["QueryKey"]
    batch_size = 100
    for i in range(0, total, batch_size):
        current_size = batch_size
        success = False
        for attempt in range(3):
            try:
                handle = Entrez.efetch(
                    db="nuccore", retmax=current_size, retstart=i,
                    rettype="gb", retmode="text",
                    webenv=web_env, query_key=query_key,
                )
                data = handle.read()
                handle.close()
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                for record in SeqIO.parse(io.StringIO(data), "genbank"):
                    path = os.path.join(target_dir, f"{record.id}.gb")
                    if not os.path.exists(path):
                        with open(path, "w") as f:
                            SeqIO.write(record, f, "genbank")
                success = True
                break
            except IncompleteRead as e:
                current_size = max(10, current_size // 2)
                sys.stdout.write(
                    f"Batch {i} attempt {attempt + 1} failed: {e}, "
                    f"retrying with size {current_size}\n"
                )
                sys.stdout.flush()
                time.sleep(10)
            except Exception as e:
                sys.stdout.write(f"Batch {i} attempt {attempt + 1} failed: {e}\n")
                sys.stdout.flush()
                time.sleep(10)
        if success:
            sys.stdout.write(f"Downloaded batch {i} of {total} for plastid files.\n")
        else:
            sys.stdout.write(f"FAILED batch {i} of {total} for plastid files after 3 attempts.\n")
        sys.stdout.flush()
        time.sleep(0.11)
    cache.set(plastid_query, total)
    return plastid_query


def download_mitochondrial_files(target_dir=None):
    target_dir = target_dir or os.path.join(settings.GENBANK_ROOT, 'mitochondrial_files')
    mito_query = '(mitochondrion[filter] OR mitochondrial[filter]) AND "complete genome"[Title]'
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    cached = cache.get(mito_query)
    if cached:
        return cached
    handle = Entrez.esearch(db="nuccore", term=mito_query, retmax=0, usehistory="y")
    record = Entrez.read(handle)
    handle.close()
    total     = int(record["Count"])
    web_env   = record["WebEnv"]
    query_key = record["QueryKey"]
    batch_size = 250
    for i in range(0, total, batch_size):
        current_size = batch_size
        success = False
        for attempt in range(3):
            try:
                handle = Entrez.efetch(
                    db="nuccore", retmax=current_size, retstart=i,
                    rettype="gb", retmode="text",
                    webenv=web_env, query_key=query_key,
                )
                data = handle.read()
                handle.close()
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                for record in SeqIO.parse(io.StringIO(data), "genbank"):
                    path = os.path.join(target_dir, f"{record.id}.gb")
                    if not os.path.exists(path):
                        with open(path, "w") as f:
                            SeqIO.write(record, f, "genbank")
                success = True
                break
            except IncompleteRead as e:
                current_size = max(10, current_size // 2)
                sys.stdout.write(
                    f"Batch {i} attempt {attempt + 1} failed: {e}, "
                    f"retrying with size {current_size}\n"
                )
                sys.stdout.flush()
                time.sleep(10)
            except Exception as e:
                sys.stdout.write(f"Batch {i} attempt {attempt + 1} failed: {e}\n")
                sys.stdout.flush()
                time.sleep(10)
        if success:
            sys.stdout.write(f"Downloaded batch {i} of {total} for mitochondrial files.\n")
        else:
            sys.stdout.write(f"FAILED batch {i} of {total} for mitochondrial files after 3 attempts.\n")
        sys.stdout.flush()
        time.sleep(0.11)
    cache.set(mito_query, total)
    return mito_query

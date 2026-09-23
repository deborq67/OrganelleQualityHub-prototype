import re
import sys
from pathlib import Path

from Bio import SeqIO

"""
Gets accessions like "AB1234C","AB1234.1" and "AB1234.10
but will NOT get "AB1234.1."
"""

identical_accession = re.compile(
    r"identical to ([A-Za-z0-9_]+(?:\.[0-9]+)?)", re.IGNORECASE
)


def find_duplicate_reference(gb_path):
    """
    Parse a single GenBank file and check whether its COMMENT annotation
    says it's identical to another accession.

    Returns (accession, referenced_accession_or_None).
    """

    record = SeqIO.read(gb_path, "genbank")
    comment = record.annotations.get("comment", "")
    comment = " ".join(comment.split())

    match = identical_accession.search(comment)
    if not match:
        return record.id, None

    return record.id, match.group(1)


def scan_directory(directory, pattern="*.gb"):
    """
    Check every GenBank file matching `pattern` in `directory`.

    Yields (accession, duplicate, duplicate_accession) for each file that
    parses successfully:
      - duplicate: Either "yes" or "no"
      - duplicate_accession: Referenced accession if
      duplicate is "yes", else None

    """

    for gb_path in sorted(Path(directory).glob(pattern)):
        try:
            accession, referenced = find_duplicate_reference(gb_path)
        except Exception as exc:
            print(f"skipping {gb_path}: {exc}", file=sys.stderr)
            continue

        duplicate = referenced is not None
        yield accession, duplicate, referenced

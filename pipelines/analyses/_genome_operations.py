import os
from datetime import datetime, timezone

from Bio import SeqIO


class GenomeOperations:
    """Parse a single GenBank file into organelle metadata and
    get its taxon id."""

    # Our constructor turns a GB file into a SeqRecord.

    def __init__(self, filepath: str):
        self._filepath = filepath
        self.record = SeqIO.read(filepath, "genbank")

    def taxid(self) -> str | None:

        # Get the first property labeled 'source'.

        source = next((f for f in self.record.features if f.type == "source"), None)

        # Find db cross reference for taxon, split it, and only get ID.

        for ref in (source.qualifiers.get("db_xref", []) if source else []):
            if ref.startswith("taxon:"):
                return ref.split(":")[1]
        return None

    def _parse_date(self) -> datetime | None:

        # Get the date each record was updated for and format it.

        raw = self.record.annotations.get("date", "")

        # Turns 01-FEB-2020 to 2020-02-01

        for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
            # Make it timezone compatible.
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            # If it can't convert, move on.
            except ValueError:
                pass
        return None

    # Get time file itself was actually updated.

    def _file_date(self) -> datetime | None:
        try:
            return datetime.fromtimestamp(
                os.path.getmtime(self._filepath), tz=timezone.utc
            )
        except OSError:
            return None

    # Similar to taxid except it gets organelle qualifier.

    def organelle_type(self) -> str | None:
        source = next((f for f in self.record.features if f.type == "source"), None)
        organelle = source.qualifiers.get("organelle", [None])[0] if source else None
        if organelle:
            return organelle
        # Fallback: guesses the organelle type from the folder name.
        if "mitochondrial_files" in self._filepath:
            return "mitochondrion"
        if "plastid_files" in self._filepath:
            return "plastid"
        return None

    def gene_list(self) -> dict:
        """
        Duplicate gene names get a number suffix so
        nothing is overwritten. Stores start end and strand
        instead of the full sequence to save space.
        """
        seen = {}
        genes = {}
        for f in self.record.features:
            if f.type != "gene":
                continue

            # Get name of gene.

            name = f.qualifiers.get("gene", [None])[0]
            if not name:
                continue

            # Keep a gene count.

            seen[name] = seen.get(name, 0) + 1

            # Add it to counter.

            key = name if seen[name] == 1 else f"{name}_{seen[name]}"

            # Get parts and if not there, default to location.

            parts = getattr(f.location, "parts", [f.location])

            # Get beginning, end, and total length of each strand.

            genes[key] = [[int(p.start), int(p.end), p.strand] for p in parts]

        return genes

    # Produces the full metadata dictionary for the table.

    def stats(self) -> dict:

        # Make entire FASTA sequence all caps.

        seq = str(self.record.seq).upper()

        # Get sequence length.

        length = len(seq)

        # Get name of gene or put in blanks.

        genes = {
            f.qualifiers.get("gene", [None])[0]
            for f in self.record.features
            if f.type == "gene"
        } - {None}

        return {
            "accession": self.record.id,
            "title": self.record.description,
            "gene_count": len(genes),
            "gene_list": self.gene_list(),
            "r_rnas_reported": sum(f.type == "rRNA" for f in self.record.features),
            "t_rnas_reported": sum(f.type == "tRNA" for f in self.record.features),
            "gc_content": (
                round(sum(seq.count(b) for b in "GC") / length * 100, 2)
                if length
                else None
            ),
            "ambiguity_content": (
                round((length - sum(seq.count(b) for b in "ACGT")) / length * 100, 2)
                if length
                else None
            ),
            "longest_ambiguity_stretch": self._longest_ambiguity_stretch(seq),
            "base_pair_length": length,
            "updated": self._parse_date() or self._file_date(),
            "organelle_type": self.organelle_type(),
        }

    @staticmethod
    def _longest_ambiguity_stretch(seq: str) -> int:
        """Length of the longest run of consecutive non-ACGT (IUPAC ambiguity code) bases."""
        longest = current = 0
        for base in seq:
            current = current + 1 if base not in "ACGT" else 0
            longest = max(longest, current)
        return longest

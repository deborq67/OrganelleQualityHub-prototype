import os
from datetime import datetime, timezone

from Bio import SeqIO


class GenomeOperations:
    """Parse a single GenBank file into organelle stats + its taxon id."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        # SeqIO.read closes the file right away.
        self.record = SeqIO.read(filepath, 'genbank')

    def taxid(self) -> str | None:
        source = next((f for f in self.record.features if f.type == 'source'), None)
        for ref in (source.qualifiers.get('db_xref', []) if source else []):
            if ref.startswith('taxon:'):
                return ref.split(':')[1]
        return None

    def _parse_date(self) -> datetime | None:
        raw = self.record.annotations.get('date', '')
        for fmt in ('%d-%b-%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return None

    def _file_date(self) -> datetime | None:
        try:
            return datetime.fromtimestamp(os.path.getmtime(self._filepath), tz=timezone.utc)
        except OSError:
            return None

    def organelle_type(self) -> str | None:
        source = next((f for f in self.record.features if f.type == 'source'), None)
        organelle = source.qualifiers.get('organelle', [None])[0] if source else None
        if organelle:
            return organelle
        # Fallback: guesses the organelle type from the folder name.
        if 'mitochondrial_files' in self._filepath:
            return 'mitochondrion'
        if 'plastid_files' in self._filepath:
            return 'plastid'
        return None

    def gene_list(self) -> dict:
        '''Duplicate gene names get a number suffix so nothing is overwritten.

        Stores start end and strand instead of the full sequence to save space.'''
        seen = {}
        genes = {}
        for f in self.record.features:
            if f.type != 'gene':
                continue
            name = f.qualifiers.get('gene', [None])[0]
            if not name:
                continue
            seen[name] = seen.get(name, 0) + 1
            key = name if seen[name] == 1 else f'{name}_{seen[name]}'
            parts = getattr(f.location, 'parts', [f.location])
            genes[key] = [[int(p.start), int(p.end), p.strand] for p in parts]
        return genes

    def stats(self) -> dict:
        seq = str(self.record.seq).upper()
        length = len(seq)
        genes = {f.qualifiers.get('gene', [None])[0]
                 for f in self.record.features if f.type == 'gene'} - {None}
        return {
            'accession': self.record.id,
            'title': self.record.description,
            'gene_count': len(genes),
            'gene_list': self.gene_list(),
            'r_rnas_reported': sum(f.type == 'rRNA' for f in self.record.features),
            't_rnas_reported': sum(f.type == 'tRNA' for f in self.record.features),
            'gc_content': round(sum(seq.count(b) for b in 'GC') / length * 100, 2) if length else None,
            'ambiguity_content': round((length - sum(seq.count(b) for b in 'ACGT')) / length * 100, 2) if length else None,
            'longest_ambiguity_stretch': self._longest_ambiguity_stretch(seq),
            'base_pair_length': length,
            'updated': self._parse_date() or self._file_date(),
            'organelle_type': self.organelle_type(),
        }

    @staticmethod
    def _longest_ambiguity_stretch(seq: str) -> int:
        """Length of the longest run of consecutive non-ACGT (IUPAC ambiguity code) bases."""
        longest = current = 0
        for base in seq:
            current = current + 1 if base not in 'ACGT' else 0
            longest = max(longest, current)
        return longest

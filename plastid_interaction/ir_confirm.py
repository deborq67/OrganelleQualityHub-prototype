"""
OBJECTIVE:
    This script takes a complete plastid genome sequence (in FASTA format) and re-calculates (re-infers) the
    position (and, thus, the length) of the IRs. The input is the output of script 02. The output is a table of
    plastid genome records (one record per row) that lists the originally inferred IR length and the
    BLAST-inferred IR length so that a comparison is possible.

DESIGN:
    * Like in the other scripts, the evaluation of the genome records is conducted one by one, not all
      simultaneously.

    * The script re-infers IRs by self-BLASTing the complete sequence and filtering hits by expected IR length.

TO DO (FUTURE VERSIONS OF AIRPG):
    * Start positions for IRa and IRb are sometimes switched around (probably because they were improperly
      recorded in previous scripts due to missing unique identification)

    * Once the IRs are re-calculated, the originally inferred IR length and the newly calculated IR length shall
      be compared to see if previous studies have - on average - overestimated or underestimated the IR length.

    * If differences between the originally inferred IR length and the newly calculated IR length are
      discovered, it will be interesting to see on which side of the IRs (the side that faces the LSC or the
      side that faces the SSC) the original inference was incorrect (i.e., on which side a bias in the
      original inference happened).

    * Also do the inference of the IR via MUMMER (specifically, a self-comparison via dnadiff) so that the IR
      boundaries as inferred via self-BLASTing are confirmed (i.e., similar to the internal confirmation check
      of the total number of sequence differences via CMP).
"""

import os
import argparse
from Bio import SeqIO
import polars as pl
import glob
import shutil
import subprocess

_GENBANK_EXTENSIONS = ('.gb', '.gbk', '.genbank')
_COL_LENGTH = 0
_COL_QSTART = 1
_COL_QEND   = 2


def _check_blast_tools():
    """Raise RuntimeError if blastn or makeblastdb are not on PATH."""
    for tool in ('blastn', 'makeblastdb'):
        if not shutil.which(tool):
            raise RuntimeError(f"Required tool '{tool}' not found on PATH.")


class SelfBlasting:
    def __init__(self, seq_FASTA, accession):
        self.seq_FASTA = seq_FASTA
        self.accession = accession
        self.filestem_db = os.path.join(
            os.path.dirname(self.seq_FASTA) or '.',
            self.accession + '_completeSeq_blastdb',
        )

    def setup_blast_db(self):
        subprocess.run([
            'makeblastdb',
            '-dbtype', 'nucl',
            '-in',     self.seq_FASTA,
            '-out',    self.filestem_db,
            '-title',  self.accession,
            '-parse_seqids',
            '-logfile', self.filestem_db + '.log',
        ], stderr=subprocess.DEVNULL)

    def cleanup_db(self):
        for f in glob.glob(self.filestem_db + '*'):
            try:
                os.remove(f)
            except OSError:
                pass

    def infer_irs(self, minlength=10000, maxlength=50000):
        outfn = self.filestem_db + '_completeSeq.fasta'
        result = subprocess.run([
            'blastn',
            '-query',  self.seq_FASTA,
            '-db',     self.filestem_db,
            '-outfmt', '6 length qstart qend sstart send',
            '-strand', 'both',
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        hits = []
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            length = int(parts[_COL_LENGTH])
            if minlength <= length <= maxlength:
                hits.append([int(p) for p in parts])
        if os.path.isfile(outfn):
            os.remove(outfn)
        return hits


def resolve_sequence_file(accession, datadir):
    """Return the absolute path to the FASTA or GenBank file for *accession*."""
    base = os.path.abspath(os.path.join(datadir, accession))
    fasta = base + '_completeSeq_from_gb.fasta'
    if os.path.isfile(fasta):
        return fasta
    for ext in _GENBANK_EXTENSIONS:
        infn = base + ext
        if os.path.isfile(infn):
            outfn = base + '_completeSeq_from_gb.fasta'
            rec = next(SeqIO.parse(infn, 'genbank'))
            SeqIO.write(rec, outfn, 'fasta')
            return outfn
    return None


__author__    = 'Michael Gruenstaeudl <m_gruenstaeudl@fhsu.edu>, Tilman Mehl <tilmanmehl@zedat.fu-berlin.de>'
__copyright__ = 'Copyright (C) 2019-2021 Michael Gruenstaeudl and Tilman Mehl'
__info__      = 'Retrieve the plastid genomes identified by the first script and evaluate their inverted repeats'
__version__   = '2024.05.08.1700'


def main(accession, datadir, minlength=10000, maxlength=50000):
    def _unconfirmed(notes):
        return {
            'accession': accession,
            'ira_blastinferred': 'no', 'ira_blastinferred_start': None,
            'ira_blastinferred_end': None, 'ira_blastinferred_length': None,
            'irb_blastinferred': 'no', 'irb_blastinferred_start': None,
            'irb_blastinferred_end': None, 'irb_blastinferred_length': None,
            'notes': notes,
        }

    seq_file = resolve_sequence_file(accession, datadir)
    if not seq_file:
        return _unconfirmed(f'No file found for {accession} in datadir.')

    _check_blast_tools()
    blaster = SelfBlasting(seq_file, accession)
    print(f'Creating local BLAST database for accession `{accession}`')
    try:
        blaster.setup_blast_db()
    except Exception as e:
        return _unconfirmed(f'BLAST database setup failed: {e}')

    print(f'Self-BLASTing FASTA file of accession `{accession}` to identify the IRs.')
    hits = blaster.infer_irs(minlength=minlength, maxlength=maxlength)
    blaster.cleanup_db()

    fasta_created = os.path.join(datadir, accession + '_completeSeq_from_gb.fasta')
    if os.path.isfile(fasta_created):
        try:
            os.remove(fasta_created)
        except OSError:
            pass

    if not hits:
        return _unconfirmed('No BLAST hits found within the length range.')

    # Use the two longest hits as IRa/IRb
    hits_sorted = sorted(hits, key=lambda h: h[_COL_LENGTH], reverse=True)[:2]
    hits_sorted = sorted(hits_sorted, key=lambda h: h[_COL_QSTART])
    if len(hits_sorted) < 2:
        return _unconfirmed(f'Only {len(hits_sorted)} hit found within length range {minlength}-{maxlength}bp; '
                            f'need at least 2 to identify IRa/IRb.')

    ira = hits_sorted[0]
    irb = hits_sorted[1]
    return {
        'accession':              accession,
        'ira_blastinferred':      'yes',
        'ira_blastinferred_start': ira[_COL_QSTART],
        'ira_blastinferred_end':   ira[_COL_QEND],
        'ira_blastinferred_length': ira[_COL_LENGTH],
        'irb_blastinferred':      'yes',
        'irb_blastinferred_start': irb[_COL_QSTART],
        'irb_blastinferred_end':   irb[_COL_QEND],
        'irb_blastinferred_length': irb[_COL_LENGTH],
        'notes': None,
    }


def cli():
    parser = argparse.ArgumentParser(description=__info__)
    parser.add_argument('accession', help='Plastid accession to process')
    parser.add_argument('datadir',   help='Directory containing GenBank/FASTA files')
    parser.add_argument('--minlength', type=int, default=10000)
    parser.add_argument('--maxlength', type=int, default=50000)
    args = parser.parse_args()
    result = main(args.accession, args.datadir, args.minlength, args.maxlength)
    if result:
        print(result)


if __name__ == '__main__':
    cli()

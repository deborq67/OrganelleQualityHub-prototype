import tempfile
import unittest
import random
from pathlib import Path

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO

from pipelines.analyses.ir_operations import IROperations


class IROperationsTests(unittest.TestCase):
    def test_identifies_reported_ir_lengths_from_synthetic_genbank(self):
        record = SeqRecord(
            Seq(
                "".join(random.choices("AGTC", k=80_000))
                + "A" * 15_000
                + "".join(random.choices("AGTC", k=20_000))
                + "A" * 15_000
            ),
            id="TEST_IR",
            name="TEST_IR",
            description="Synthetic IR regression record",
        )
        features = [
            SeqFeature(
                FeatureLocation(80_001, 95_001),
                type="repeat_region",
                qualifiers={"rpt_type": ["inverted"], "note": ["IRa"]},
            ),
            SeqFeature(
                FeatureLocation(115_001, 130_001),
                type="repeat_region",
                qualifiers={"rpt_type": ["inverted"], "note": ["IRb"]},
            ),
        ]
        record.annotations["molecule_type"] = "DNA"
        record.annotations["date"] = "01-JAN-2024"
        record.features = features

        temporary_directory = tempfile.TemporaryDirectory()
        filepath = Path(temporary_directory.name) / "TEST_IR.gb"
        SeqIO.write(record, filepath, "genbank")

        info = IROperations(filepath).info.to_dicts()[0]
        print(f"Record: {record.id}, length: {len(record.seq):,} bp")
        print(
            f"IRa: {info['IRa_REPORTED']} | "
            f"length: {info['IRa_REPORTED_LENGTH']:,} bp "
            f"(expected 15,000 bp)"
        )
        print(
            f"IRb: {info['IRb_REPORTED']} | "
            f"length: {info['IRb_REPORTED_LENGTH']:,} bp "
            f"(expected 15,000 bp)"
        )
        self.assertEqual(info["IRa_REPORTED"], "yes")
        self.assertEqual(info["IRb_REPORTED"], "yes")
        self.assertEqual(info["IRa_REPORTED_LENGTH"], 15_000)
        self.assertEqual(info["IRb_REPORTED_LENGTH"], 15_000)
        self.assertEqual(info["IR_EQUAL"], "yes")

if __name__ == "__main__":
    unittest.main()

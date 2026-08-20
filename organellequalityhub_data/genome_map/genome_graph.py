import os
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from pycirclize import Circos
from pycirclize.parser import Genbank
from matplotlib.patches import Patch

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "genome_graphs")

# Track radii (inner, outer)
TRACK_CDS_F = (90, 97)
TRACK_CDS_R = (83, 90)
TRACK_RRNA = (74, 81)
TRACK_TRNA = (67, 74)
TRACK_REGION = (58, 65)
TRACK_BLAST_IR = (49, 56)

# Feature colours
COL_CDS_F = "salmon"
COL_CDS_R = "cornflowerblue"
COL_RRNA = "limegreen"
COL_TRNA = "orchid"

# Region colours
COL_LSC = "#8695F9"
COL_SSC = "#A0FAAD"
COL_IR = "#F8FB6B"
COL_BLAST_IRA = "#FF6B35"
COL_BLAST_IRB = "#C94040"

REGION_COLOURS = {"LSC": COL_LSC, "SSC": COL_SSC, "IR": COL_IR}


def classify_regions(ir_features, genome_size):
    """
    Given repeat_region features and genome size, return a list of
    (start, end, label) tuples covering LSC, SSC, and IR regions.
    """
    candidates = [
        f
        for f in ir_features
        if abs(int(f.location.end) - int(f.location.start)) >= 1000
    ]
    if len(candidates) < 2:
        return []

    irs = sorted(
        sorted(
            candidates,
            key=lambda f: abs(int(f.location.end) - int(f.location.start)),
            reverse=True,
        )[:2],
        key=lambda f: int(f.location.start),
    )

    ir1_s = int(irs[0].location.start)
    ir1_e = int(irs[0].location.end)
    ir2_s = int(irs[1].location.start)
    ir2_e = int(irs[1].location.end)

    gap1 = ir2_s - ir1_e
    gap2 = genome_size - ir2_e + ir1_s

    regions = [(ir1_s, ir1_e, "IR"), (ir2_s, ir2_e, "IR")]

    if gap1 >= gap2:
        regions.append((ir1_e, ir2_s, "LSC"))
        if ir1_s > 0:
            regions += [(ir2_e, genome_size, "SSC"), (0, ir1_s, "SSC")]
        else:
            regions.append((ir2_e, genome_size, "SSC"))
    else:
        regions.append((ir1_e, ir2_s, "SSC"))
        if ir1_s > 0:
            regions += [(ir2_e, genome_size, "LSC"), (0, ir1_s, "LSC")]
        else:
            regions.append((ir2_e, genome_size, "LSC"))

    return regions


def generate_map(gb_path, ir_data=None):
    """Generate a circular genome map PNG for a single GenBank file.

    Parameters
    ----------
    gb_path   : path to the .gb file
    ir_data   : optional dict with keys ira_blastinferred_start/end,
                irb_blastinferred_start/end (from IR_Identification)
    """
    accession = os.path.splitext(os.path.basename(gb_path))[0]
    out_path = os.path.join(OUTPUT_DIR, accession + ".svg")

    gbk = Genbank(gb_path)
    genome_size = sum(gbk.get_seqid2size().values())

    circos = Circos(sectors={accession: genome_size})
    sector = circos.sectors[0]

    # --- Region track (LSC / SSC / IR) ---
    features_all = gbk.get_seqid2features(feature_type=None)
    region_features = [
        f for flist in features_all.values() for f in flist if f.type == "repeat_region"
    ]
    regions = classify_regions(region_features, genome_size)

    region_track = sector.add_track(TRACK_REGION)
    for start, end, label in regions:
        colour = REGION_COLOURS.get(label, "lightgrey")
        region_track.rect(start, end, fc=colour, ec="none")
    region_track.axis(fc="none")

    # --- BLAST IR track ---
    if ir_data and ir_data.get("ira_blastinferred") == "yes":
        blast_track = sector.add_track(TRACK_BLAST_IR)
        ira_s = ir_data.get("ira_blastinferred_start", 0)
        ira_e = ir_data.get("ira_blastinferred_end", 0)
        irb_s = ir_data.get("irb_blastinferred_start", 0)
        irb_e = ir_data.get("irb_blastinferred_end", 0)
        blast_track.rect(ira_s, ira_e, fc=COL_BLAST_IRA, ec="none")
        blast_track.rect(irb_s, irb_e, fc=COL_BLAST_IRB, ec="none")
        blast_track.axis(fc="none")

    # --- Gene feature tracks ---
    features = gbk.get_seqid2features(feature_type="CDS")
    cds_f_track = sector.add_track(TRACK_CDS_F)
    cds_r_track = sector.add_track(TRACK_CDS_R)
    for flist in features.values():
        for f in flist:
            if f.location.strand is None:
                continue
            name = (
                f.qualifiers.get("gene", [""])[0]
                or f.qualifiers.get("product", [""])[0]
            )
            s, e = int(f.location.start), int(f.location.end)
            if f.location.strand >= 0:
                cds_f_track.arrow(s, e, fc=COL_CDS_F, ec="none")
            else:
                cds_r_track.arrow(s, e, fc=COL_CDS_R, ec="none")
            if name:
                mid = (s + e) / 2
                (
                    cds_f_track.text(f"{name}", mid, size=4)
                    if f.location.strand >= 0
                    else cds_r_track.text(f"{name}", mid, size=4)
                )

    rrna_track = sector.add_track(TRACK_RRNA)
    for flist in gbk.get_seqid2features(feature_type="rRNA").values():
        for f in flist:
            rrna_track.rect(
                int(f.location.start), int(f.location.end), fc=COL_RRNA, ec="none"
            )
    rrna_track.axis(fc="none")

    trna_track = sector.add_track(TRACK_TRNA)
    for flist in gbk.get_seqid2features(feature_type="tRNA").values():
        for f in flist:
            trna_track.rect(
                int(f.location.start), int(f.location.end), fc=COL_TRNA, ec="none"
            )
    trna_track.axis(fc="none")

    # --- Genome size label ---
    sector.text(accession, r=48, size=8)
    sector.text(f"{genome_size:,.0f} bp", r=40, size=8)

    fig = circos.plotfig()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig.savefig(out_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {accession}")
    return out_path


def save_legend(out_dir=None):
    """Save a legend SVG to out_dir (defaults to OUTPUT_DIR)."""
    if out_dir is None:
        out_dir = OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    handles = [
        Patch(facecolor=COL_CDS_F, label="CDS (+)"),
        Patch(facecolor=COL_CDS_R, label="CDS (−)"),
        Patch(facecolor=COL_RRNA, label="rRNA"),
        Patch(facecolor=COL_TRNA, label="tRNA"),
        Patch(facecolor=COL_LSC, label="LSC"),
        Patch(facecolor=COL_SSC, label="SSC"),
        Patch(facecolor=COL_IR, label="IR"),
        Patch(facecolor=COL_BLAST_IRA, label="BLAST IRa"),
        Patch(facecolor=COL_BLAST_IRB, label="BLAST IRb"),
    ]
    fig, ax = plt.subplots(figsize=(3, 3))
    ax.legend(handles=handles, loc="center", frameon=False)
    ax.axis("off")
    path = os.path.join(out_dir, "Legend.svg")
    fig.savefig(path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return path

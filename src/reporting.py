"""
Report generation for PS3/BS3 analysis results.
"""

from typing import List, Dict

from .utils import VariantInfo, CandidatePaper, FunctionalPaper, FunctionalExperiment, IntegratedAssessment


def print_report(
    vi: VariantInfo,
    candidate_papers: List[CandidatePaper],
    functional_papers: List[FunctionalPaper],
    experiments: List[FunctionalExperiment],
    assessment: IntegratedAssessment,
):
    """Print a formatted report of PS3/BS3 analysis results."""
    print("\n" + "="*80)
    print("VARIANT FUNCTIONAL EVIDENCE REPORT (PS3/BS3)")
    print("="*80 + "\n")

    print("1. Variant identifiers\n")
    print(f"   Genomic coordinates: {vi.chrom}:{vi.pos} {vi.ref}>{vi.alt}")
    if vi.gene_symbol:
        print(f"   Gene: {vi.gene_symbol}")
    if vi.rsid:
        print(f"   rsID: {vi.rsid}")
    if vi.hgvsc:
        print(f"   HGVSc: {vi.hgvsc}")
    if vi.hgvsp:
        print(f"   HGVSp: {vi.hgvsp}")
    if vi.mane_transcript:
        print(f"   MANE transcript: {vi.mane_transcript}")
    if vi.ensembl_transcript:
        print(f"   Ensembl transcript: {vi.ensembl_transcript}")

    print("\n   Identifiers used for search:")
    for s in vi.search_strings():
        print(f"   - {s}")
    print()

    print("2. Literature retrieval summary\n")
    if not candidate_papers:
        print("   No candidate papers identified from LitVar2.\n")
    else:
        print(f"   Total papers from LitVar2: {len(candidate_papers)}\n")
        print("   Sample of papers:")
        for p in sorted(candidate_papers,
                        key=lambda x: int(x.pmid) if x.pmid.isdigit() else 0)[:10]:
            print(f"   - PMID {p.pmid}: {p.title[:100]}...")
        if len(candidate_papers) > 10:
            print(f"   ... and {len(candidate_papers) - 10} more papers")
        print()

    print("3. Functionally relevant papers\n")
    if not functional_papers:
        print("   No papers with direct functional experiments identified.\n")
    else:
        print(f"   Found {len(functional_papers)} functionally relevant paper(s):\n")
        for fp in functional_papers:
            print(f"   - PMID {fp.pmid}: {fp.title}")
            print(f"     Justification: {fp.justification}")
            if fp.pdf_path:
                print(f"     PDF path: {fp.pdf_path}")
            print()

    print("4. Functional evidence per paper\n")
    if not experiments:
        print("   No functional experiments extracted.\n")
    else:
        by_pmid: Dict[str, List[FunctionalExperiment]] = {}
        for e in experiments:
            by_pmid.setdefault(e.pmid, []).append(e)
        for pmid, exps in by_pmid.items():
            print(f"   PMID {pmid} ({len(exps)} experiment(s)):")
            for i, e in enumerate(exps, 1):
                print(f"\n     Experiment {i}:")
                print(f"       Assay type: {e.assay_type}")
                print(f"       System: {e.system}")
                print(f"       Readout: {e.readout}")
                print(f"       Effect direction: {e.effect_direction}")
                print(f"       Magnitude & stats: {e.magnitude_stats}")
                print(f"       Controls & quality: {e.controls_validity}")
                print(f"       Authors' conclusion: {e.authors_conclusion}")
                print(f"       Evaluation: {e.evaluation}")
            print()

    print("5. Integrated assessment\n")
    print("   " + assessment.narrative + "\n")

    print("6. ACMG functional criterion call\n")
    if assessment.decision == "PS3":
        print("   ✓ PS3 - Functional evidence supports a damaging effect")
    elif assessment.decision == "BS3":
        print("   ✓ BS3 - Functional evidence supports no damaging effect")
    else:
        print("   ✗ Neither PS3 nor BS3 applies")
        print("     Functional evidence is insufficient or conflicting")

    if assessment.strength:
        print(f"\n   Strength: {assessment.strength.upper()}")
    if assessment.key_pmids:
        print(f"   Key PMIDs: {', '.join(assessment.key_pmids)}")

    print("\n" + "="*80 + "\n")

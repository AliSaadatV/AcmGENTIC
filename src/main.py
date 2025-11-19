"""
Pipeline orchestration and main entry point functions.

Main entry point script is at the project root (main.py).
Use this module for importing the analyze_variant function.
"""

from dataclasses import asdict
from typing import Dict, Any, Optional

from .vep import vep_annotate_variant
from .utils import VariantInfo, build_variant_label, enrich_with_vep
from .litvar2 import query_litvar2, build_candidate_list
from .filtering import llm_filter_functional_papers, llm_extract_experiments
from .assessment import integrate_evidence
from .reporting import print_report


def analyze_variant(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    assembly: str = "GRCh38",
) -> Dict[str, Any]:
    """
    Run the full PS3/BS3 functional evidence pipeline for a single variant,
    starting from CHROM, POS, REF, ALT.

    Parameters
    ----------
    chrom : str
        Chromosome (e.g., "1", "2", "X")
    pos : int
        Genomic position (1-based)
    ref : str
        Reference allele
    alt : str
        Alternate allele
    assembly : str, optional
        Genome assembly version (default: "GRCh38")

    Returns
    -------
    dict
        Dictionary containing variant info, candidate papers, functional papers,
        experiments, and assessment results.
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING VARIANT: {chrom}:{pos} {ref}>{alt}")
    print(f"{'='*80}\n")

    # 1. Build VariantInfo from coordinates and enrich with VEP
    vi = VariantInfo(chrom=chrom, pos=pos, ref=ref, alt=alt)

    print("Step 1: VEP annotation...")
    vep_info: Optional[Dict[str, Any]] = None
    try:
        vep_info = vep_annotate_variant(chrom, pos, ref, alt, assembly=assembly)
        if vep_info:
            print("   VEP annotation obtained.")
            enrich_with_vep(vi, vep_info)
        else:
            print("   VEP returned no annotation.")
    except Exception as e:
        print(f"   Warning: VEP annotation failed: {e}")

    variant_label = build_variant_label(vi)
    print(f"\n   Variant label for LLM prompts: {variant_label}")
    print("   Identifiers to query in LitVar2:")
    for s in vi.search_strings():
        print(f"   - {s}")
    print()

    # 2. Query LitVar2 for PMIDs
    print("Step 2: Querying LitVar2 for publications...")
    pmids = query_litvar2(vi)
    print(f"   Total unique PMIDs from LitVar2: {len(pmids)}")

    # 3. Fetch paper details from PubMed via metapub
    print("\nStep 3: Fetching paper details from PubMed...")
    candidate_papers = build_candidate_list(pmids)
    print(f"   Retrieved details for {len(candidate_papers)} papers")

    # 4. Filter for functional papers
    print("\nStep 4: Filtering for functionally relevant papers...")
    functional_papers = llm_filter_functional_papers(candidate_papers, variant_label)
    print(f"   Identified {len(functional_papers)} functionally relevant papers")

    # 5. Extract experiments
    print("\nStep 5: Extracting functional experiments...")
    experiments = llm_extract_experiments(functional_papers, variant_label)
    print(f"   Extracted {len(experiments)} experiments")

    # 6. Integrate evidence
    print("\nStep 6: Integrating evidence and making PS3/BS3 call...")
    assessment = integrate_evidence(experiments)

    # 7. Output report
    print_report(vi, candidate_papers, functional_papers, experiments, assessment)

    # Return everything as a dict
    return {
        "variant_info": asdict(vi),
        "candidate_papers": [asdict(p) for p in candidate_papers],
        "functional_papers": [asdict(fp) for fp in functional_papers],
        "experiments": [asdict(e) for e in experiments],
        "assessment": asdict(assessment),
    }

from dataclasses import asdict
from typing import Dict, Any, Optional

from .vep import vep_annotate_variant
from .utils import VariantInfo, build_variant_label, enrich_with_vep
from .litvar2 import query_litvar2, build_candidate_list
from .filtering import llm_filter_functional_papers, llm_extract_experiments
from .assessment import integrate_evidence
from .reporting import print_report


def analyze_variant(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    assembly: str = "GRCh38",
) -> Dict[str, Any]:
    """
    Run the full PS3/BS3 functional evidence pipeline for a single variant,
    starting from CHROM, POS, REF, ALT.

    Parameters
    ----------
    chrom : str
        Chromosome (e.g., "1", "2", "X")
    pos : int
        Genomic position (1-based)
    ref : str
        Reference allele
    alt : str
        Alternate allele
    assembly : str, optional
        Genome assembly version (default: "GRCh38")

    Returns
    -------
    dict
        Dictionary containing variant info, candidate papers, functional papers,
        experiments, and assessment results.
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING VARIANT: {chrom}:{pos} {ref}>{alt}")
    print(f"{'='*80}\n")

    # 1. Build VariantInfo from coordinates and enrich with VEP
    vi = VariantInfo(chrom=chrom, pos=pos, ref=ref, alt=alt)

    print("Step 1: VEP annotation...")
    vep_info: Optional[Dict[str, Any]] = None
    try:
        vep_info = vep_annotate_variant(chrom, pos, ref, alt, assembly=assembly)
        if vep_info:
            print("   VEP annotation obtained.")
            enrich_with_vep(vi, vep_info)
        else:
            print("   VEP returned no annotation.")
    except Exception as e:
        print(f"   Warning: VEP annotation failed: {e}")

    variant_label = build_variant_label(vi)
    print(f"\n   Variant label for LLM prompts: {variant_label}")
    print("   Identifiers to query in LitVar2:")
    for s in vi.search_strings():
        print(f"   - {s}")
    print()

    # 2. Query LitVar2 for PMIDs
    print("Step 2: Querying LitVar2 for publications...")
    pmids = query_litvar2(vi)
    print(f"   Total unique PMIDs from LitVar2: {len(pmids)}")

    # 3. Fetch paper details from PubMed via metapub
    print("\nStep 3: Fetching paper details from PubMed...")
    candidate_papers = build_candidate_list(pmids)
    print(f"   Retrieved details for {len(candidate_papers)} papers")

    # 4. Filter for functional papers
    print("\nStep 4: Filtering for functionally relevant papers...")
    functional_papers = llm_filter_functional_papers(candidate_papers, variant_label)
    print(f"   Identified {len(functional_papers)} functionally relevant papers")

    # 5. Extract experiments
    print("\nStep 5: Extracting functional experiments...")
    experiments = llm_extract_experiments(functional_papers, variant_label)
    print(f"   Extracted {len(experiments)} experiments")

    # 6. Integrate evidence
    print("\nStep 6: Integrating evidence and making PS3/BS3 call...")
    assessment = integrate_evidence(experiments)

    # 7. Output report
    print_report(vi, candidate_papers, functional_papers, experiments, assessment)

    # Return everything as a dict
    return {
        "variant_info": asdict(vi),
        "candidate_papers": [asdict(p) for p in candidate_papers],
        "functional_papers": [asdict(fp) for fp in functional_papers],
        "experiments": [asdict(e) for e in experiments],
        "assessment": asdict(assessment),
    }


if __name__ == "__main__":
    # Example usage
    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G",
    )
    print("\nAnalysis complete. Results returned as dictionary.")

"""
Main entry point for PS3/BS3 functional evidence analysis pipeline.

ACMG functional criteria:

- PS3: Well-established in vitro or in vivo functional studies supportive of a
  damaging effect on the gene or gene product.

- BS3: Well-established in vitro or in vivo functional studies show no damaging
  effect on protein function or splicing.

Supports multiple LLM providers:
- OpenAI (default): gpt-4o-mini, gpt-4o, gpt-4-turbo
- Anthropic: claude-3-5-sonnet-20241022, claude-3-opus-20240229
- Google Gemini: gemini-1.5-flash, gemini-1.5-pro

Configuration via .env file:
  LLM_PROVIDER=openai|anthropic|gemini
  OPENAI_API_KEY (for OpenAI)
  ANTHROPIC_API_KEY (for Anthropic)
  GOOGLE_API_KEY (for Gemini)
  NCBI_EMAIL
  NCBI_API_KEY (optional)

Usage:
    python main.py --chrom 2 --pos 162279995 --ref C --alt G [--assembly GRCh38] \\
                   [--model gpt-4o-mini] [--pdf-path func_papers_pdf] \\
                   [--output-format html|dict] [--output-dir output_report]
"""

import sys
import os
import argparse
from pathlib import Path
from dataclasses import asdict
from typing import Dict, Any, Optional

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

from src.vep import vep_annotate_variant
from src.utils import VariantInfo, build_variant_label, enrich_with_vep
from src.litvar2 import (
    query_litvar2,
    build_candidate_list,
    download_pdfs_for_papers,
    fetch_pdf_url,
    get_failed_pdf_pmids,
    prompt_manual_pdf_download,
)
from src.filtering import llm_filter_functional_papers, llm_extract_experiments
from src.assessment import integrate_evidence
from src.reporting import print_report
from src.html_report import generate_html_report, generate_pdf_report, generate_reports


def analyze_variant(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    assembly: str = "GRCh38",
    pdf_path: Optional[str] = None,
    download_pdfs: bool = True,
    max_pdf_downloads: Optional[int] = None,
    interactive: bool = True,
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
    pdf_path : str, optional
        Directory to save functional paper PDFs (default: None)
    download_pdfs : bool, optional
        Whether to attempt downloading PDFs for functional papers (default: True)
    max_pdf_downloads : int, optional
        Maximum number of PDFs to download. If None, download all available.
    interactive : bool, optional
        If True, prompt user to manually download missing PDFs (default: True)

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

    # 4. Filter for functional papers (high-sensitivity screening)
    print("\nStep 4: Filtering for functionally relevant papers...")
    functional_papers = llm_filter_functional_papers(candidate_papers, variant_label)
    print(f"   Identified {len(functional_papers)} functionally relevant papers")

    # 4b. Download PDFs for functional papers (if enabled)
    downloaded_pdfs = {}
    if download_pdfs and pdf_path and functional_papers:
        print("\nStep 4b: Downloading PDFs for functional papers...")
        functional_pmids = [fp.pmid for fp in functional_papers]
        downloaded_pdfs = download_pdfs_for_papers(
            functional_pmids,
            pdf_path,
            max_downloads=max_pdf_downloads,
        )
        print(f"   Downloaded/found {len(downloaded_pdfs)} PDFs")
        
        # Check for missing PDFs and prompt for manual download
        failed_pmids = get_failed_pdf_pmids(functional_pmids, pdf_path)
        if failed_pmids:
            print(f"   {len(failed_pmids)} PDF(s) could not be automatically downloaded")
            
            # Prompt user for manual download (if interactive)
            manually_added = prompt_manual_pdf_download(
                failed_pmids,
                pdf_path,
                interactive=interactive,
            )
            downloaded_pdfs.update(manually_added)
            
            if manually_added:
                print(f"   Total PDFs available: {len(downloaded_pdfs)}")
        
        # Update functional papers with PDF paths
        for fp in functional_papers:
            if fp.pmid in downloaded_pdfs:
                fp.pdf_path = downloaded_pdfs[fp.pmid]

    # 5. Extract experiments (uses PDFs when available)
    print("\nStep 5: Extracting functional experiments...")
    experiments = llm_extract_experiments(
        functional_papers,
        variant_label,
        pdf_dir=pdf_path if download_pdfs else None,
    )
    print(f"   Extracted {len(experiments)} experiments")

    # 6. Integrate evidence using LLM
    print("\nStep 6: Integrating evidence and making PS3/BS3 call...")
    assessment = integrate_evidence(experiments, variant_label)

    # 7. Output report
    print_report(vi, candidate_papers, functional_papers, experiments, assessment)

    # Return everything as a dict
    return {
        "variant_info": asdict(vi),
        "candidate_papers": [asdict(p) for p in candidate_papers],
        "functional_papers": [asdict(fp) for fp in functional_papers],
        "experiments": [asdict(e) for e in experiments],
        "assessment": asdict(assessment),
        "downloaded_pdfs": downloaded_pdfs,
    }


if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Analyze genetic variants for ACMG PS3/BS3 functional evidence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python main.py --chrom 2 --pos 162279995 --ref C --alt G

  # With custom model
  python main.py --chrom 2 --pos 162279995 --ref C --alt G --model claude-3-5-sonnet-20241022

  # Generate HTML report in custom directory
  python main.py --chrom 2 --pos 162279995 --ref C --alt G --output-format html --output-dir reports/

  # Return dictionary output (for programmatic use)
  python main.py --chrom 2 --pos 162279995 --ref C --alt G --output-format dict
        """
    )

    # Required arguments
    parser.add_argument(
        "--chrom",
        type=str,
        required=True,
        help="Chromosome (e.g., 1, 2, X, MT)"
    )
    parser.add_argument(
        "--pos",
        type=int,
        required=True,
        help="Genomic position (1-based)"
    )
    parser.add_argument(
        "--ref",
        type=str,
        required=True,
        help="Reference allele"
    )
    parser.add_argument(
        "--alt",
        type=str,
        required=True,
        help="Alternate allele"
    )

    # Optional arguments
    parser.add_argument(
        "--assembly",
        type=str,
        default="GRCh38",
        choices=["GRCh38", "GRCh37"],
        help="Genome assembly version (default: GRCh38)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model to use (overrides LLM_MODEL from .env). Examples: gpt-4o-mini, claude-3-5-sonnet-20241022, gemini-1.5-flash"
    )
    parser.add_argument(
        "--pdf-path",
        type=str,
        default="func_papers_pdf",
        help="Directory to save functional paper PDFs (default: func_papers_pdf)"
    )
    parser.add_argument(
        "--download-pdfs",
        action="store_true",
        default=True,
        help="Download PDFs for functional papers (default: True)"
    )
    parser.add_argument(
        "--no-download-pdfs",
        action="store_false",
        dest="download_pdfs",
        help="Skip PDF download, use abstract-only extraction"
    )
    parser.add_argument(
        "--max-pdf-downloads",
        type=int,
        default=None,
        help="Maximum number of PDFs to download per analysis (default: unlimited)"
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["html", "pdf", "both", "dict"],
        default="both",
        help="Output format: 'html', 'pdf', 'both' (HTML+PDF), or 'dict' for dictionary (default: both)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output_report",
        help="Directory to save HTML reports (default: output_report)"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        default=False,
        help="Disable interactive prompts (e.g., manual PDF download)"
    )
    parser.add_argument(
        "--agentic",
        action="store_true",
        default=False,
        help="Use agentic document extraction with OCR, layout detection, and VLM tools (requires paddleocr, pdf2image, transformers)"
    )

    args = parser.parse_args()

    # Override model if specified via command line
    if args.model:
        os.environ["LLM_MODEL"] = args.model

    # Enable agentic extraction if requested
    if args.agentic:
        os.environ["USE_AGENTIC_EXTRACTION"] = "true"
        print("Agentic document extraction enabled")

    # Ensure PDF directory exists
    pdf_dir = Path(args.pdf_path)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run analysis
    result = analyze_variant(
        chrom=args.chrom,
        pos=args.pos,
        ref=args.ref,
        alt=args.alt,
        assembly=args.assembly,
        pdf_path=str(pdf_dir),
        download_pdfs=args.download_pdfs,
        max_pdf_downloads=args.max_pdf_downloads,
        interactive=not args.no_interactive,
    )

    # Handle output
    if args.output_format == "dict":
        # Print dictionary result
        print("\n" + "="*80)
        print("RESULT (Dictionary Format)")
        print("="*80)
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        # Generate report(s)
        print("\nGenerating report(s)...")
        variant_label = f"{args.chrom}_{args.pos}_{args.ref}_{args.alt}_{args.assembly}"

        try:
            output_paths = generate_reports(
                result,
                str(output_dir),
                variant_label,
                formats=args.output_format,
            )
            
            if not output_paths:
                raise RuntimeError("No reports were generated")
                
        except Exception as e:
            print(f"Warning: Failed to generate report(s): {e}")
            print("Saving results as JSON instead...")
            import json
            json_path = output_dir / f"{variant_label}.json"
            with open(json_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"✓ Results saved to: {json_path}")

    print("\n✓ Analysis complete.")

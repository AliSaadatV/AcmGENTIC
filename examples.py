#!/usr/bin/env python3
"""
Example usage of the PS3/BS3 analysis pipeline.

This script shows different ways to use the pipeline:
1. Simple variant analysis
2. Using different LLM models (Claude)
3. Batch analysis of multiple variants
4. Custom HTML report generation
5. Extracting specific data from results
6. Analyzing with different genome assemblies
7. Agentic extraction mode
8. Non-interactive batch processing
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from main import analyze_variant
from src.html_report import generate_html_report, generate_pdf_report, generate_reports
import json


def example_1_simple_analysis():
    """Example 1: Simple variant analysis."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Simple Variant Analysis")
    print("="*80)

    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G",
        interactive=False,  # Don't prompt for manual PDF download
    )

    print(f"\nDecision: {result['assessment']['decision']}")
    print(f"Strength: {result['assessment'].get('strength', 'N/A')}")
    print(f"Confidence: {result['assessment'].get('confidence', 'N/A')}")


def example_2_with_custom_model():
    """Example 2: Analysis with a specific LLM model."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Using Claude Model (Requires ANTHROPIC_API_KEY)")
    print("="*80)

    # Save original environment
    original_provider = os.environ.get("LLM_PROVIDER")
    original_model = os.environ.get("LLM_MODEL")

    try:
        os.environ["LLM_PROVIDER"] = "anthropic"
        os.environ["LLM_MODEL"] = "claude-3-5-sonnet-20241022"

        result = analyze_variant(
            chrom="2",
            pos=162279995,
            ref="C",
            alt="G",
            interactive=False,
        )

        print(f"\nUsed Provider: {os.environ.get('LLM_PROVIDER')}")
        print(f"Used Model: {os.environ.get('LLM_MODEL')}")
        print(f"Decision: {result['assessment']['decision']}")
    finally:
        # Restore original environment
        if original_provider:
            os.environ["LLM_PROVIDER"] = original_provider
        if original_model:
            os.environ["LLM_MODEL"] = original_model


def example_3_batch_analysis():
    """Example 3: Batch analysis of multiple variants."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Batch Analysis of Multiple Variants")
    print("="*80)

    variants = [
        {"chrom": "2", "pos": 162279995, "ref": "C", "alt": "G"},
        {"chrom": "17", "pos": 41244694, "ref": "T", "alt": "A"},
    ]

    results = {}
    for variant in variants:
        variant_key = f"{variant['chrom']}:{variant['pos']}_{variant['ref']}>{variant['alt']}"
        print(f"\nAnalyzing {variant_key}...")

        try:
            result = analyze_variant(**variant, interactive=False)
            results[variant_key] = result
            print(f"  → Decision: {result['assessment']['decision']}")
            print(f"  → Strength: {result['assessment'].get('strength', 'N/A')}")
        except Exception as e:
            print(f"  → Error: {e}")

    # Save all results to JSON
    output_file = Path("batch_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Batch results saved to: {output_file}")


def example_4_custom_html_report():
    """Example 4: Generate custom HTML report."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Custom HTML Report Generation")
    print("="*80)

    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G",
        interactive=False,
    )

    # Generate HTML report
    html_path = "custom_report.html"
    generate_html_report(result, html_path)
    print(f"\n✓ Custom HTML report saved to: {html_path}")

    # Generate both HTML and PDF reports
    output_dir = Path("output_report")
    output_dir.mkdir(exist_ok=True)
    output_paths = generate_reports(
        result,
        str(output_dir),
        "2_162279995_C_G_example",
        formats="both"
    )
    print(f"✓ Reports generated: {output_paths}")


def example_5_extract_specific_data():
    """Example 5: Extract specific data from results."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Extract Specific Data")
    print("="*80)

    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G",
        interactive=False,
    )

    # Extract variant info
    var_info = result["variant_info"]
    print(f"\nVariant: {var_info['chrom']}:{var_info['pos']} {var_info['ref']}>{var_info['alt']}")
    print(f"Gene: {var_info.get('gene_symbol', 'N/A')}")
    print(f"rsID: {var_info.get('rsid', 'N/A')}")
    print(f"HGVSc: {var_info.get('hgvsc', 'N/A')}")
    print(f"HGVSp: {var_info.get('hgvsp', 'N/A')}")

    # Extract assessment
    assessment = result["assessment"]
    print(f"\nAssessment:")
    print(f"  Decision: {assessment['decision']}")
    print(f"  Strength: {assessment.get('strength', 'N/A')}")
    print(f"  Confidence: {assessment.get('confidence', 'N/A')}")
    print(f"  Key PMIDs: {assessment.get('key_pmids', [])}")
    print(f"\nNarrative:")
    print(f"  {assessment['narrative']}")

    # Extract experiments
    experiments = result["experiments"]
    print(f"\nNumber of experiments: {len(experiments)}")
    for i, exp in enumerate(experiments[:3], 1):  # Show first 3
        print(f"\n  Experiment {i}:")
        print(f"    PMID: {exp['pmid']}")
        print(f"    Assay: {exp['assay_type']}")
        print(f"    System: {exp['system']}")
        print(f"    Effect: {exp['effect_direction']}")
        print(f"    Evaluation: {exp['evaluation']}")

    # Show downloaded PDFs
    downloaded_pdfs = result.get("downloaded_pdfs", {})
    if downloaded_pdfs:
        print(f"\nDownloaded PDFs: {len(downloaded_pdfs)}")
        for pmid, path in list(downloaded_pdfs.items())[:3]:
            print(f"  PMID {pmid}: {path}")


def example_6_different_assemblies():
    """Example 6: Analyze same variant on different assemblies."""
    print("\n" + "="*80)
    print("EXAMPLE 6: Different Genome Assemblies")
    print("="*80)

    for assembly in ["GRCh38", "GRCh37"]:
        print(f"\nAnalyzing with assembly: {assembly}...")
        result = analyze_variant(
            chrom="2",
            pos=162279995,
            ref="C",
            alt="G",
            assembly=assembly,
            interactive=False,
        )
        print(f"  → Decision: {result['assessment']['decision']}")
        print(f"  → Strength: {result['assessment'].get('strength', 'N/A')}")


def example_7_agentic_extraction():
    """Example 7: Use agentic extraction for complex PDFs."""
    print("\n" + "="*80)
    print("EXAMPLE 7: Agentic Document Extraction")
    print("="*80)
    print("(Requires additional dependencies: easyocr/paddleocr, pdf2image, etc.)")

    # Enable agentic extraction via environment variable
    os.environ["USE_AGENTIC_EXTRACTION"] = "true"
    os.environ["AGENTIC_VLM_MODEL"] = "gpt-4o"  # Better vision model

    try:
        result = analyze_variant(
            chrom="2",
            pos=162279995,
            ref="C",
            alt="G",
            interactive=False,
        )

        print(f"\nAgentic extraction completed!")
        print(f"Decision: {result['assessment']['decision']}")
        print(f"Experiments found: {len(result['experiments'])}")
    except ImportError as e:
        print(f"\n⚠ Agentic extraction not available: {e}")
        print("Install dependencies: pip install easyocr pdf2image transformers torch")
    finally:
        # Disable agentic extraction
        os.environ["USE_AGENTIC_EXTRACTION"] = "false"


def example_8_non_interactive_batch():
    """Example 8: Non-interactive batch processing for automation."""
    print("\n" + "="*80)
    print("EXAMPLE 8: Non-interactive Batch Processing")
    print("="*80)

    # This example shows how to run the pipeline in a fully automated way
    # without any user prompts (useful for CI/CD, scripts, etc.)

    variants = [
        {"chrom": "2", "pos": 162279995, "ref": "C", "alt": "G"},
    ]

    results = []
    for variant in variants:
        result = analyze_variant(
            **variant,
            pdf_path="func_papers_pdf",
            download_pdfs=True,
            max_pdf_downloads=5,  # Limit downloads
            interactive=False,    # No prompts
        )

        results.append({
            "variant": f"{variant['chrom']}:{variant['pos']} {variant['ref']}>{variant['alt']}",
            "decision": result["assessment"]["decision"],
            "strength": result["assessment"].get("strength"),
            "confidence": result["assessment"].get("confidence"),
            "num_experiments": len(result["experiments"]),
            "num_papers": len(result["functional_papers"]),
        })

    # Print summary
    print("\nSummary:")
    print("-" * 60)
    for r in results:
        print(f"  {r['variant']}: {r['decision']} ({r['strength']}) - "
              f"{r['num_experiments']} experiments from {r['num_papers']} papers")


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    print("\n" + "="*80)
    print("PS3/BS3 Analysis Pipeline - Examples")
    print("="*80)

    # Run examples
    try:
        example_1_simple_analysis()
    except Exception as e:
        print(f"Example 1 skipped: {e}")

    # Uncomment to run other examples (they may require specific API keys or setup)
    # try:
    #     example_2_with_custom_model()
    # except Exception as e:
    #     print(f"Example 2 skipped: {e}")

    # try:
    #     example_3_batch_analysis()
    # except Exception as e:
    #     print(f"Example 3 skipped: {e}")

    # try:
    #     example_4_custom_html_report()
    # except Exception as e:
    #     print(f"Example 4 skipped: {e}")

    # try:
    #     example_5_extract_specific_data()
    # except Exception as e:
    #     print(f"Example 5 skipped: {e}")

    # try:
    #     example_6_different_assemblies()
    # except Exception as e:
    #     print(f"Example 6 skipped: {e}")

    # try:
    #     example_7_agentic_extraction()
    # except Exception as e:
    #     print(f"Example 7 skipped: {e}")

    # try:
    #     example_8_non_interactive_batch()
    # except Exception as e:
    #     print(f"Example 8 skipped: {e}")

    print("\n" + "="*80)
    print("Examples complete!")
    print("="*80)

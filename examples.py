#!/usr/bin/env python3
"""
Example usage of the PS3/BS3 analysis pipeline.

This script shows different ways to use the pipeline:
1. Command-line interface
2. Programmatic Python interface
3. Batch analysis
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from main import analyze_variant
from src.html_report import generate_html_report
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
        alt="G"
    )

    print(f"\nDecision: {result['assessment']['decision']}")
    print(f"Strength: {result['assessment'].get('strength', 'N/A')}")


def example_2_with_custom_model():
    """Example 2: Analysis with a specific LLM model."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Using Claude Model (Requires ANTHROPIC_API_KEY)")
    print("="*80)

    import os
    os.environ["LLM_PROVIDER"] = "anthropic"
    os.environ["LLM_MODEL"] = "claude-3-5-sonnet-20241022"

    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G"
    )

    print(f"\nUsed Provider: {os.environ.get('LLM_PROVIDER')}")
    print(f"Used Model: {os.environ.get('LLM_MODEL')}")
    print(f"Decision: {result['assessment']['decision']}")


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
            result = analyze_variant(**variant)
            results[variant_key] = result
            print(f"  → Decision: {result['assessment']['decision']}")
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
        alt="G"
    )

    # Generate report
    output_path = "custom_report.html"
    generate_html_report(result, output_path)
    print(f"\n✓ Custom HTML report saved to: {output_path}")


def example_5_extract_specific_data():
    """Example 5: Extract specific data from results."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Extract Specific Data")
    print("="*80)

    result = analyze_variant(
        chrom="2",
        pos=162279995,
        ref="C",
        alt="G"
    )

    # Extract variant info
    var_info = result["variant_info"]
    print(f"\nVariant: {var_info['chrom']}:{var_info['pos']} {var_info['ref']}>{var_info['alt']}")
    print(f"Gene: {var_info.get('gene_symbol', 'N/A')}")
    print(f"rsID: {var_info.get('rsid', 'N/A')}")

    # Extract assessment
    assessment = result["assessment"]
    print(f"\nAssessment Decision: {assessment['decision']}")
    print(f"Strength: {assessment.get('strength', 'N/A')}")
    print(f"\nNarrative:")
    print(f"  {assessment['narrative']}")

    # Extract experiments
    experiments = result["experiments"]
    print(f"\nNumber of experiments: {len(experiments)}")
    for i, exp in enumerate(experiments[:3], 1):  # Show first 3
        print(f"\n  Experiment {i}:")
        print(f"    PMID: {exp['pmid']}")
        print(f"    Assay: {exp['assay_type']}")
        print(f"    Evaluation: {exp['evaluation']}")


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
            assembly=assembly
        )
        print(f"  → Decision: {result['assessment']['decision']}")


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

    print("\n" + "="*80)
    print("Examples complete!")
    print("="*80)

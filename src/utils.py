"""
Common data classes and utilities for PS3/BS3 analysis pipeline.
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Set


@dataclass
class VariantInfo:
    """Store variant coordinate and annotation information."""
    chrom: str
    pos: int
    ref: str
    alt: str
    rsid: Optional[str] = None
    hgvsc: Optional[str] = None
    hgvsp: Optional[str] = None
    gene_symbol: Optional[str] = None
    ensembl_transcript: Optional[str] = None
    mane_transcript: Optional[str] = None

    def search_strings(self) -> List[str]:
        """
        Return a deduplicated list of variant IDs to search LitVar2.

        Uses:
        - a simple genomic string: CHR:POS REF>ALT
        - rsid, hgvsc, hgvsp
        - gene_symbol + hgvsc / hgvsp combos when available
        """
        genomic_str = f"{self.chrom}:{self.pos}{self.ref}>{self.alt}"

        candidates = [
            genomic_str,
            self.rsid,
            self.hgvsc,
            self.hgvsp,
        ]
        if self.gene_symbol and self.hgvsp:
            candidates.append(f"{self.gene_symbol} {self.hgvsp}")
        if self.gene_symbol and self.hgvsc:
            candidates.append(f"{self.gene_symbol} {self.hgvsc}")
        return sorted({c for c in candidates if c})


@dataclass
class CandidatePaper:
    """Store basic paper information from LitVar2."""
    pmid: str
    title: str
    abstract: str
    source: str = "litvar2"
    why_relevant: str = "LitVar2 variant mention"


@dataclass
class FunctionalPaper:
    """Store paper with confirmed functional experiments."""
    pmid: str
    title: str
    justification: str
    pdf_path: Optional[str] = None  # path to downloaded PDF, if available


@dataclass
class FunctionalExperiment:
    """Store detailed functional experiment information."""
    pmid: str
    assay_type: str
    system: str
    readout: str
    effect_direction: str
    magnitude_stats: str
    controls_validity: str
    authors_conclusion: str
    evaluation: str


@dataclass
class IntegratedAssessment:
    """Store integrated PS3/BS3 assessment result."""
    decision: str
    narrative: str
    strength: Optional[str] = None
    key_pmids: Optional[List[str]] = None


def build_variant_label(vi: VariantInfo) -> str:
    """
    Build a simple, LLM-friendly "variant of interest" string.
    """
    return (
        f"{vi.chrom}:{vi.pos} {vi.ref}>{vi.alt}, "
        f"HGVSp:{vi.hgvsp}, HGVSc:{vi.hgvsc}, rsID:{vi.rsid}, symbol:{vi.gene_symbol}"
    )


def enrich_with_vep(vi: VariantInfo, vep_info: dict) -> None:
    """Update VariantInfo in-place with VEP annotations if present."""
    if not vep_info:
        return

    if vep_info.get("rsid") and not vi.rsid:
        vi.rsid = vep_info["rsid"]

    if vep_info.get("gene_symbol") and not vi.gene_symbol:
        vi.gene_symbol = vep_info["gene_symbol"]

    if vep_info.get("hgvsc"):
        vi.hgvsc = vep_info["hgvsc"]

    if vep_info.get("hgvsp"):
        vi.hgvsp = vep_info["hgvsp"]

    if vep_info.get("ensembl_transcript"):
        vi.ensembl_transcript = vep_info["ensembl_transcript"]

    if vep_info.get("mane_transcript"):
        vi.mane_transcript = vep_info["mane_transcript"]

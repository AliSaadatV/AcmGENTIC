"""
VEP (Variant Effect Predictor) annotation functionality.
"""

import requests
from typing import Dict, Optional, Any

from .utils import VariantInfo


def vep_annotate_variant(chrom: str, pos: int, ref: str, alt: str, assembly: str = "GRCh38") -> Optional[Dict[str, Any]]:
    """
    Query Ensembl VEP REST API for rsID, HGVSc, HGVSp using:
    - hgvs = 1
    - pick = 1   (VEP selects the best transcript consequence)
    - mane = 1
    """

    if assembly == "GRCh37":
        server = "https://grch37.rest.ensembl.org"
    else:
        server = "https://rest.ensembl.org"

    endpoint = "/vep/homo_sapiens/region"

    # VEP expects a whitespace-delimited string like VCF (ID is optional):
    # CHROM  POS  ID  REF  ALT  QUAL FILTER INFO
    variant_str = f"{chrom} {pos} . {ref} {alt} . . ."

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "variants": [variant_str],
        "hgvs": 1,
        "pick": 1,
        "mane": 1
    }

    response = requests.post(server + endpoint, headers=headers, json=payload)
    response.raise_for_status()

    results = response.json()
    if not results:
        return None

    entry = results[0]

    # Extract rsID (most reliable way)
    rsid = None
    for cv in entry.get("colocated_variants", []):
        if "id" in cv and str(cv["id"]).startswith("rs"):
            rsid = cv["id"]
            break
        if "ids" in cv:
            for x in cv["ids"]:
                if str(x).startswith("rs"):
                    rsid = x
                    break
        if rsid:
            break

    # Extract transcript-level HGVS (pick=1 → one consequence)
    hgvsc = None
    hgvsp = None
    gene_symbol = None
    ensembl_transcript = None
    mane_transcript = None

    tx = entry.get("transcript_consequences", [])
    if tx:
        tx = tx[0]   # selected transcript
        hgvsc = tx.get("hgvsc")
        hgvsp = tx.get("hgvsp")
        gene_symbol = tx.get("gene_symbol")
        ensembl_transcript = tx.get("transcript_id")
        mane_transcript = tx.get("mane_select")

    return {
        "rsid": rsid,
        "hgvsc": hgvsc,
        "hgvsp": hgvsp,
        "gene_symbol": gene_symbol,
        "ensembl_transcript": ensembl_transcript,
        "mane_transcript": mane_transcript
    }

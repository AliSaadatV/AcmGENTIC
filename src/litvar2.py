"""
LitVar2 and PubMed literature retrieval functionality.
"""

import time
import requests
from typing import List, Dict, Set
from urllib.parse import quote

from metapub import PubMedFetcher

from .config import LITVAR2_API_BASE, ENTREZ_BASE, NCBI_API_KEY, NCBI_EMAIL
from .utils import VariantInfo, CandidatePaper

# Global metapub fetcher
FETCHER = PubMedFetcher()


def query_litvar2_publications(variant_id: str) -> Set[str]:
    """
    Query LitVar2 API for publications mentioning a variant.
    Returns set of PMIDs.

    Endpoint:
    https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/get/{variantId}/publications
    """
    try:
        encoded_variant = quote(variant_id, safe='')

        url = f"{LITVAR2_API_BASE}/variant/get/litvar@{encoded_variant}%23%23/publications"
        print(f"   Querying LitVar2: {variant_id}...")

        resp = requests.get(url, timeout=30)

        if not resp.ok:
            print(f"   Warning: LitVar2 returned status {resp.status_code} for '{variant_id}'")
            return set()

        data = resp.json()

        pmids = set()

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    pmid = item.get('pmid') or item.get('PMID')
                    if pmid:
                        pmids.add(str(pmid))
                elif isinstance(item, (str, int)):
                    pmids.add(str(item))
        elif isinstance(data, dict):
            for key in ['pmids', 'PMIDs', 'publications', 'results', 'data']:
                if key in data:
                    items = data[key]
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                pmid = item.get('pmid') or item.get('PMID')
                                if pmid:
                                    pmids.add(str(pmid))
                            else:
                                pmids.add(str(item))
                    break

        if pmids:
            print(f"   Found {len(pmids)} publications for '{variant_id}'")
        else:
            print(f"   No publications found for '{variant_id}'")

        return pmids

    except Exception as e:
        print(f"   Warning: LitVar2 query failed for '{variant_id}': {e}")
        return set()


def query_litvar2(vi: VariantInfo) -> Set[str]:
    """
    Query LitVar2 using multiple variant identifiers.
    Returns a set of all unique PMIDs found.
    """
    all_pmids: Set[str] = set()

    for variant_id in vi.search_strings():
        pmids = query_litvar2_publications(variant_id)
        all_pmids.update(pmids)
        time.sleep(0.5)  # Be respectful to the API

    return all_pmids


def entrez_get(endpoint: str, params: Dict) -> requests.Response:
    """Make a request to NCBI Entrez API."""
    base_params = {"email": NCBI_EMAIL}
    if NCBI_API_KEY:
        base_params["api_key"] = NCBI_API_KEY
    base_params.update(params)

    url = f"{ENTREZ_BASE}/{endpoint}"
    resp = requests.get(url, params=base_params, timeout=30)
    resp.raise_for_status()
    return resp


def pubmed_fetch_details(pmids: List[str]) -> Dict[str, CandidatePaper]:
    """
    Fetch full details (title, abstract) for a list of PMIDs using metapub.

    Uses:
        from metapub import PubMedFetcher
        article = FETCHER.article_by_pmid(pmid)
    """
    if not pmids:
        return {}

    result: Dict[str, CandidatePaper] = {}

    print(f"   Fetching details for {len(pmids)} papers from PubMed via metapub...")

    for pmid in pmids:
        pmid_str = str(pmid)
        try:
            article = FETCHER.article_by_pmid(pmid_str)
        except Exception as e:
            print(f"   Warning: metapub failed for PMID {pmid_str}: {e}")
            continue

        if article is None:
            print(f"   Warning: no article object returned for PMID {pmid_str}")
            continue

        title = article.title or ""
        abstract = article.abstract or ""

        result[pmid_str] = CandidatePaper(
            pmid=pmid_str,
            title=title,
            abstract=abstract,
            source="litvar2",
            why_relevant="LitVar2 variant mention",
        )

        # Light throttling to be polite
        time.sleep(0.1)

    return result


def build_candidate_list(pmids: Set[str]) -> List[CandidatePaper]:
    """
    Fetch paper details from PubMed for all PMIDs from LitVar2.
    """
    if not pmids:
        return []

    pmid_list = sorted(list(pmids))
    papers_dict = pubmed_fetch_details(pmid_list)

    return list(papers_dict.values())

"""
LitVar2 and PubMed literature retrieval functionality.

Includes PDF URL discovery and download capabilities using:
- metapub FindIt for open-access PDF discovery
- Unpaywall API for DOI-based open access lookup
"""

import os
import time
import requests
import urllib.request
from typing import List, Dict, Set, Optional
from urllib.parse import quote
from pathlib import Path

from metapub import PubMedFetcher, FindIt

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


# =============================================================================
# PDF URL Discovery and Download Functions
# =============================================================================


def check_open_access_from_doi(doi: str) -> str:
    """
    Check if a DOI is open access using Unpaywall API.
    
    Parameters
    ----------
    doi : str
        The DOI to check
        
    Returns
    -------
    str
        URL to open access PDF if available, empty string otherwise
    """
    if not doi:
        return ""

    url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": NCBI_EMAIL}

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return ""

        data = r.json()
        if data.get("is_oa"):
            # Try to get the best OA location
            best_oa = data.get("best_oa_location", {})
            if best_oa:
                pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")
                if pdf_url:
                    return pdf_url
            return data.get("doi_url", "")
        return ""

    except Exception:
        return ""


def fetch_pdf_url(pmid: str) -> str:
    """
    Fetch PDF URL for a PMID using multiple methods.
    
    Tries:
    1. metapub FindIt for direct PDF discovery
    2. Unpaywall API via DOI for open access
    
    Parameters
    ----------
    pmid : str
        PubMed ID
        
    Returns
    -------
    str
        URL to PDF if found, empty string otherwise
    """
    try:
        # Try metapub FindIt first
        finder = FindIt(pmid)
        if finder.url:
            return finder.url
        
        # Fallback: try Unpaywall via DOI
        article = FETCHER.article_by_pmid(pmid)
        if article and hasattr(article, "doi") and article.doi:
            url = check_open_access_from_doi(article.doi)
            if url:
                return url
        
        return ""
    except Exception as e:
        print(f"   Warning: Failed to find PDF URL for PMID {pmid}: {e}")
        return ""


def download_pdf(pmid: str, pdf_dir: str, url: Optional[str] = None) -> Optional[str]:
    """
    Download PDF for a PMID to specified directory.
    
    Parameters
    ----------
    pmid : str
        PubMed ID
    pdf_dir : str
        Directory to save PDFs
    url : str, optional
        Pre-fetched PDF URL. If None, will attempt to discover URL.
        
    Returns
    -------
    str or None
        Path to downloaded PDF if successful, None otherwise
    """
    pdf_path = Path(pdf_dir) / f"{pmid}.pdf"
    
    # Check if already exists
    if pdf_path.exists():
        print(f"   [→] PDF already exists for PMID {pmid}")
        return str(pdf_path)
    
    # Get URL if not provided
    if url is None:
        url = fetch_pdf_url(pmid)
    
    if not url:
        print(f"   [✗] No PDF URL found for PMID {pmid}")
        return None
    
    try:
        # Ensure directory exists
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(pdf_path, 'wb') as f:
                f.write(response.read())
        
        print(f"   [✓] Downloaded PDF for PMID {pmid}")
        return str(pdf_path)
        
    except Exception as e:
        print(f"   [✗] Failed to download PDF for PMID {pmid}: {e}")
        return None


def download_pdfs_for_papers(
    pmids: List[str],
    pdf_dir: str,
    max_downloads: Optional[int] = None,
) -> Dict[str, str]:
    """
    Download PDFs for multiple PMIDs.
    
    Parameters
    ----------
    pmids : list of str
        List of PubMed IDs
    pdf_dir : str
        Directory to save PDFs
    max_downloads : int, optional
        Maximum number of PDFs to download. If None, download all.
        
    Returns
    -------
    dict
        Mapping from PMID to PDF path for successful downloads
    """
    downloaded = {}
    
    for i, pmid in enumerate(pmids):
        if max_downloads is not None and i >= max_downloads:
            break
            
        pdf_path = download_pdf(pmid, pdf_dir)
        if pdf_path:
            downloaded[pmid] = pdf_path
        
        # Rate limiting
        time.sleep(0.5)
    
    return downloaded

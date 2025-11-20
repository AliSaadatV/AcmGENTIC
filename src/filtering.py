"""
LLM-based filtering and functional experiment extraction.
"""

import re
import json
import time
from typing import List, Dict

from .llm import LLM
from .config import ENTREZ_BASE, NCBI_API_KEY, NCBI_EMAIL
from .utils import CandidatePaper, FunctionalPaper, FunctionalExperiment
from .litvar2 import entrez_get


def llm_filter_functional_papers(
    candidate_papers: List[CandidatePaper],
    variant_label: str,
) -> List[FunctionalPaper]:
    """
    Use an LLM to decide which papers contain experimental functional data.
    """
    functional: List[FunctionalPaper] = []

    print(f"   Filtering {len(candidate_papers)} papers for functional evidence...")

    for i, p in enumerate(candidate_papers, 1):
        if i % 10 == 0:
            print(f"   Processed {i}/{len(candidate_papers)} papers...")

        prompt = f"""You are assisting with ACMG variant curation for PS3/BS3.

Variant of interest: {variant_label}

Paper:
PMID: {p.pmid}
Title: {p.title}
Abstract: {p.abstract}

Question: Does this paper include *experimental functional data* (in vitro or in vivo)
specifically on this variant (or clearly equivalent notation)?

Exclude:
- Purely in silico prediction
- Only genotype/phenotype correlations
- Reviews without new experiments
- Papers that only mention the variant without testing it

Respond in JSON with keys:
- "is_functional": true/false
- "justification": short string (1-3 sentences).
"""

        try:
            resp = LLM.invoke(prompt)

            # resp.content can be a string or a list of content parts
            content = resp.content
            if isinstance(content, list):
                # LangChain sometimes returns a list of dicts with "text"
                content = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )

            parsed = json.loads(content)

            if parsed.get("is_functional"):
                functional.append(
                    FunctionalPaper(
                        pmid=p.pmid,
                        title=p.title,
                        justification=parsed.get("justification", "").strip(),
                    )
                )
        except Exception as e:
            print(f"   Warning: LLM filtering failed for PMID {p.pmid}: {e}")
            continue

    return functional


def fetch_full_text_or_abstract(pmid: str) -> str:
    """
    Retrieve text for a PMID (PubMed XML -> stripped text).

    This gives abstract + some additional metadata. No PMC complexity.
    """
    try:
        resp = entrez_get("efetch.fcgi", {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
        })
        xml_text = resp.text
        text = re.sub(r"<.*?>", " ", xml_text)
        text = re.sub(r"\s+", " ", text)
        return text
    except Exception as e:
        print(f"   Warning: Failed to fetch text for PMID {pmid}: {e}")
        return ""


def llm_extract_experiments(
    functional_papers: List[FunctionalPaper],
    variant_label: str,
) -> List[FunctionalExperiment]:
    """
    Extract experiment details using LLM.
    """
    experiments: List[FunctionalExperiment] = []

    print(f"   Extracting experiments from {len(functional_papers)} functional papers...")

    for i, fp in enumerate(functional_papers, 1):
        print(f"   Processing paper {i}/{len(functional_papers)}: PMID {fp.pmid}")

        full_text = fetch_full_text_or_abstract(fp.pmid)

        prompt = f"""You are helping evaluate ACMG criteria PS3 and BS3 for a genetic variant.

Variant of interest: {variant_label}
Paper PMID: {fp.pmid}
Title: {fp.title}

Below is the text (abstract and possibly more) for this paper:
---
{full_text[:25000]}
---

ACMG functional criteria:
- PS3: Well-established in vitro or in vivo functional studies supportive of a damaging
  effect on the gene or gene product.
- BS3: Well-established in vitro or in vivo functional studies show no damaging effect
  on protein function or splicing.

Task:
Identify all experiments that directly test the functional impact of THIS variant.
For each experiment, extract:

- assay_type (e.g. "enzyme activity", "minigene splicing", "luciferase reporter")
- system (e.g. HEK293 cells, patient fibroblasts, mouse model, yeast)
- readout (e.g. catalytic activity, expression level, localization, splicing pattern)
- effect_direction: one of ["strong_loss_of_function", "partial_loss_of_function",
   "gain_of_function", "dominant_negative", "no_effect_vs_wildtype", "ambiguous"]
- magnitude_stats: brief text summarizing fold-changes, p-values, replicates
- controls_validity: brief text on controls, replication, assay quality
- authors_conclusion: short paraphrase of what authors say about variant effect
- evaluation: one of ["supports_pathogenic", "supports_benign", "ambiguous", "low_quality"]

Return JSON with key "experiments" containing a list of objects with the above keys.
If no relevant experiments found, return {{"experiments": []}}.
"""

        try:
            resp = LLM.invoke(prompt)

            content = resp.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )

            parsed = json.loads(content)

            exp_list = parsed.get("experiments", [])
            if not isinstance(exp_list, list):
                continue

            for e in exp_list:
                experiments.append(
                    FunctionalExperiment(
                        pmid=fp.pmid,
                        assay_type=e.get("assay_type", ""),
                        system=e.get("system", ""),
                        readout=e.get("readout", ""),
                        effect_direction=e.get("effect_direction", ""),
                        magnitude_stats=e.get("magnitude_stats", ""),
                        controls_validity=e.get("controls_validity", ""),
                        authors_conclusion=e.get("authors_conclusion", ""),
                        evaluation=e.get("evaluation", ""),
                    )
                )
        except Exception as e:
            print(f"   Warning: LLM extraction failed for PMID {fp.pmid}: {e}")
            continue

    return experiments

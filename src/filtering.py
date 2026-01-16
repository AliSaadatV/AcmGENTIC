"""
LLM-based filtering and functional experiment extraction.

Implements:
1. High-sensitivity abstract screening for functional evidence (Step 1)
2. Full-text PDF-based experiment extraction with structured schema (Step 2)
"""

import re
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from .llm import LLM
from .config import ENTREZ_BASE, NCBI_API_KEY, NCBI_EMAIL
from .utils import CandidatePaper, FunctionalPaper, FunctionalExperiment
from .litvar2 import entrez_get


# =============================================================================
# PROMPTS
# =============================================================================

# High-sensitivity abstract classification prompt (from notebook 02)
ABSTRACT_CLASSIFICATION_SYSTEM_PROMPT = """
You are a clinical variant interpretation curator performing an abstract-level screen for ACMG/AMP PS3/BS3 relevance.

Goal
Decide ONLY whether the abstract contains ANY experimental (wet-lab) functional evidence about the effect of one or more genetic variants/mutations/alleles/mutants on gene product function (protein or RNA) or a disease-relevant functional pathway/output.

Output
Return ONLY: is_functional = true or false, and a brief justification.

Bias / sensitivity requirement (important)
This screen is intentionally high-sensitivity. If there is reasonable doubt, classify as true so the paper can be reviewed downstream.
Default to true whenever BOTH (i) variant/mutant language and (ii) any wet-lab functional assay signal are present, even if details are sparse.

Classify is_functional = true if the abstract shows BOTH:

A) Variant-or-mutant subject (broad; exact IDs NOT required)
Any of the following counts:
- Specific variant(s) listed (HGVS, rsID, amino-acid change, "c."/"p.", etc.)
- "patient mutations/variants", "disease-causing mutations", "mutant alleles", "allelic series"
- "mutant constructs", "site-directed mutants", "missense mutants", "variant panel", "mutagenesis"
- Engineered or edited variant models (knock-in, CRISPR-introduced variant, engineered mutant protein)
- Patient-derived samples where the abstract links results to the mutation(s) (even broadly)

AND

B) Wet-lab functional assay + outcome statement
There is an experimental functional readout and the abstract states an outcome for the variant(s), including qualitative direction.
Examples of outcome language: reduced/abolished/impaired, increased/gain, altered, disrupted, restored/rescued, mislocalized, unstable, no difference/normal, defective splicing, NMD, truncated protein with loss of activity, etc.

Count as functional evidence (any wet-lab) if the abstract includes one or more of:

1) Protein/biochemical function (in vitro or cellular)
- Enzymatic activity/kinetics, catalytic function, substrate turnover
- Binding/interaction/complex formation
- Protein stability/folding/degradation/half-life
- Localization/trafficking/secretion
- Channel transport, receptor/signaling output, post-translational effects tied to function

2) Cell-based functional consequences
- Reporter assays, pathway activity, electrophysiology, transport flux
- Rescue/complementation (WT vs mutant; mutant fails to rescue or rescue restores)
- Mechanistic cellular phenotypes tied to function (e.g., DNA repair capacity, metabolic function, stress sensitivity) with mutant-vs-WT comparison

3) RNA-level functional assays attributable to a variant
- Splicing assays (patient RNA/cDNA, RT-PCR, minigene) showing aberrant splicing
- mRNA stability / nonsense-mediated decay (NMD) experimentally shown
- Translation/processing efficiency when experimentally measured

4) Model systems with variant-level manipulation
- Knock-in/engineered variant models with functional or disease-relevant phenotypes and a variant-linked readout

5) Patient-derived functional assays (allow, even if confounded)
- Enzyme activity, electrophysiology, pathway output, splicing defects measured in patient cells/tissue, when the abstract links findings to the mutation(s)

Strong "bias-to-1" tie-breakers
Return true if ANY of the following patterns appear:
- ("mutation/variant/mutant/allele") + a wet-lab assay keyword (activity, assay, measured, functional, reporter, localization, stability, splicing, RT-PCR, minigene, NMD, electrophysiology, rescue)
- The abstract claims functional impact for mutations ("mutations impair function", "variants reduce activity", "mutants show defective splicing"), even without numbers.

Return is_functional = false ONLY when it is clearly NOT functional variant testing:
- Purely in silico/computational prediction with no wet-lab experiment
- Pure genetic association/segregation/case reports/phenotype-only with no functional readout
- Gene/pathway biology experiments (KO/overexpression/mechanism) that do NOT test variants/mutant constructs
- Expression/omics profiling alone (RNA-seq, differential expression) without variant-linked functional RNA/protein consequences
  (Exception: explicit variant-driven splicing or experimentally shown NMD/mRNA instability)

Final rule
If you can point to (A) any variant/mutant subject AND (B) any wet-lab functional readout with an outcome claim, output true. Otherwise output false.
"""

# Full-text PDF experiment extraction prompt 
PDF_EXTRACTION_SYSTEM_PROMPT = r"""
You are a clinical variant functional-evidence extractor for ACMG/AMP guidelines PS3/BS3 criteria.

INPUTS
- TARGET_VARIANT: gene + identifiers (any of rsID, HGVSg, chr_pos_ref_alt,
  HGVSc, HGVSp, aliases).
- PAPER: a full PDF (may include many variants).

GOAL
- Find all plausible variant-level functional experiments that might correspond to the TARGET_VARIANT. Read all PDF (text, tables, figure captions, and figure panels/embedded labels)
- Be SENSITIVE: when in doubt, extract and clearly mark uncertainty.
- Do NOT hallucinate data.

OUTPUT
- Return ONLY valid JSON that matches the schema exactly.
- Use double quotes for all keys and strings.
- No commentary outside JSON.

────────────────────────────────────
1. VARIANT MATCHING (SOFT GATE)
────────────────────────────────────
Build an equivalents set for the TARGET_VARIANT (without inventing mappings):
- Same rsID
- Same genomic coordinates (exact chr:pos:ref:alt or HGVSg as given)
- Same cDNA change (c.notation; allow formatting variants)
- Same protein change (same ref AA, same position, same alt AA;
  allow 1-letter ↔ 3-letter and formatting variants)

Do NOT:
- Change genome build
- Renumber across transcripts unless the paper explicitly gives both
- Guess transcript IDs

Match tiers (you can stop when one is clearly satisfied):

1) STRICT MATCH → status = "matched"
   - Exact rsID, genomic, cDNA, or protein match from the equivalents set,
     in the correct gene.
   - match_type = "rsid" / "genomic" / "cdna" / "protein" / "multiple"
   - confidence:
     - "high": rsID or genomic
     - "medium": cDNA or protein + clear gene context
     - "low": identifier match but weak context

2) SINGLE VARIANT STUDY → status = "single_variant_study_matching"
   - Functional experiments in this gene clearly test ONE specific variant only.
   - No other specific variants appear in functional results.
   - confidence:
     - "medium" if gene and clinical context are clear
     - "low" if context is weaker
   - match_type = "single_variant_study"

3) HEURISTIC MATCH → status = "heuristic_matching"
   Use for plausible, non-strict matches in the same gene. Count applicable clues:

   Clues:
    - Same amino-acid substitution (same ref AA, position, alt AA) but written
    in words or non-standard notation (e.g. "R158W mutant", "R158→W").
    - Explicit numbering / isoform / precursor→mature mapping that links positions
    to the same amino acid change.
    - Different cDNA / protein numbering that the paper directly ties together
    (e.g. "c.472C>T (R158W)").
    - Shorthand label ("mut1", "A", etc.) that is expanded elsewhere to a notation
    matching the TARGET_VARIANT equivalents.
    - Table / figure / text cross-reference that explicitly equates two labels
    as the same variant.
    - Multiplex / saturation screen where the authors systematically test single
    substitutions and the tested set clearly includes the TARGET codon / position
    (e.g. "all single-amino-acid substitutions at residue 158").

    Never call heuristic_matching based only on:
    - Same exon / domain / region, "nearby" codon, or vague proximity.
    - Gene-level statements with no specific variant label.

   - match_type = "heuristic"
   - confidence: "low" if 1 clue; "medium" if ≥2 clues

4) NO PLAUSIBLE VARIANT → status = "variant_matching_unsuccessful"
   - Use ONLY when you find no specific variant in this gene that could
     reasonably be the TARGET_VARIANT.
   - In this case: experiments = [] and overall_evidence.evidence_level =
     "not_clear" and evidence_strength = "not_clear".

IMPORTANT SENSITIVITY RULE:
- If you see any specific variant in the SAME GENE that could plausibly be the
  TARGET_VARIANT, you SHOULD:
  - Assign "matched", "single_variant_study_matching", or "heuristic_matching"
    with appropriate (often low) confidence.
  - Extract its experiments.
  - Explain uncertainty in variant_match.notes and overall_evidence.basis.
- Only use "variant_matching_unsuccessful" when there is truly no plausible
  candidate.

────────────────────────────────────
2. EXPERIMENT EXTRACTION
────────────────────────────────────
Extract experiments ONLY for the variant(s) linked to the TARGET_VARIANT by
your chosen status (matched / single_variant_study_matching / heuristic_matching).

INCLUDE:
- Experiments where the specific variant label (e.g. "R158W", "mut1",
  "c.472C>T") has its own row, bar, lane, or result.
- Variant-level results in tables, figures, or text.

EXCLUDE:
- Purely in silico predictions.
- Case reports or association studies with no functional assay.
- Results where variants are pooled and no individual variant result is given.

For each experiment, record:
- What the assay is (assay)
- The system used (system)
- How the variant material was obtained (variant_material)
- The measured endpoint (readout)
- The explicit comparator (normal_comparator: WT/healthy/threshold)
- The functional direction and any numbers (result.direction and
  result.effect_size_and_stats)
- Controls and validation details (controls_and_validation)
- Authors' explicit conclusion about the variant (authors_conclusion)
- Where it appears (where_in_paper)
- Limitations stated in the paper (caveats)
- Exact variant label in the paper (paper_variant_label)
- How strongly you link that label to the TARGET_VARIANT
  (variant_link_confidence).

If you find NO functional assay on the matched variant:
- experiments = []
- overall_evidence.evidence_level = "not_clear"
- overall_evidence.evidence_strength = "not_clear"
- State this in overall_evidence.basis.

────────────────────────────────────
3. PS3 / BS3 / not_clear
────────────────────────────────────
Definitions:
- PS3: Variant shows a functionally abnormal result (for example vs. a normal comparator),
consistent with a damaging effect and disease mechanism.
- BS3: Variant shows functionally normal result (for example vs. a normal comparator).
- not_clear: unclear direction, conflicting or insufficient information.

Strength (very_strong / strong / moderate / supporting / not_clear):
- supporting: comparator present + basic controls described (WT ± positive/null) but limited validation
- moderate: well-established assay with clear controls/replication and/or multiple validation controls described
- strong/very_strong: the paper provides rigorous clinical validation/calibration supporting high confidence
  (e.g., multiple known benign/pathogenic controls with clear thresholds or explicit calibration).

If evidence_level = "not_clear":
- evidence_strength MUST be "not_clear".

────────────────────────────────────
4. SUMMARY
────────────────────────────────────
In summary:
- Be generous in extraction when the variant is plausibly the TARGET_VARIANT.
- Use status, confidence, variant_link_confidence, and notes to mark how sure
  you are.
- Never invent experiments or numbers.
- Output must be valid JSON according to the schema, with no extra keys.
"""

# JSON Schema for structured PDF extraction output
VARIANT_FUNCTIONAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "target_variant_input",
        "variant_match",
        "experiments",
        "overall_evidence",
        "summary"
    ],
    "properties": {
        "target_variant_input": {
            "type": "string",
            "description": "Raw TARGET_VARIANT input string"
        },
        "variant_match": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "status",
                "confidence",
                "match_type",
                "matched_strings_in_paper",
                "equivalents_used",
                "where_in_paper",
                "notes"
            ],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "matched",
                        "single_variant_study_matching",
                        "heuristic_matching",
                        "variant_matching_unsuccessful"
                    ],
                    "description": "Overall matching outcome for the TARGET_VARIANT"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "not_clear"],
                    "description": "Overall confidence that the matched variant(s) correspond to the TARGET_VARIANT"
                },
                "match_type": {
                    "type": "string",
                    "enum": [
                        "rsid",
                        "genomic",
                        "cdna",
                        "protein",
                        "multiple",
                        "single_variant_study",
                        "heuristic",
                        "not_clear"
                    ],
                    "description": "Primary identifier or pattern used to link the paper variant(s) to the TARGET_VARIANT"
                },
                "matched_strings_in_paper": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exact matching strings as they appear in the paper"
                },
                "equivalents_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of equivalent forms of TARGET_VARIANT used in the search"
                },
                "where_in_paper": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Locations of the matched strings"
                },
                "notes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Short notes explaining matching rationale and any ambiguity"
                }
            }
        },
        "experiments": {
            "type": "array",
            "description": "Functional experiments for the variant(s) linked to the TARGET_VARIANT",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "assay",
                    "system",
                    "variant_material",
                    "readout",
                    "normal_comparator",
                    "result",
                    "controls_and_validation",
                    "authors_conclusion",
                    "where_in_paper",
                    "caveats",
                    "paper_variant_label",
                    "variant_link_confidence"
                ],
                "properties": {
                    "assay": {
                        "type": ["string", "null"],
                        "description": "Assay type"
                    },
                    "system": {
                        "type": ["string", "null"],
                        "description": "Experimental system"
                    },
                    "variant_material": {
                        "type": ["string", "null"],
                        "description": "Source of the variant material"
                    },
                    "readout": {
                        "type": ["string", "null"],
                        "description": "Measured endpoint with units"
                    },
                    "normal_comparator": {
                        "type": ["string", "null"],
                        "description": "Explicit comparator defining normal function"
                    },
                    "result": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["direction", "effect_size_and_stats"],
                        "properties": {
                            "direction": {
                                "type": "string",
                                "enum": [
                                    "functionally_abnormal",
                                    "functionally_normal",
                                    "intermediate",
                                    "mixed",
                                    "unclear"
                                ],
                                "description": "Functional impact relative to the comparator"
                            },
                            "effect_size_and_stats": {
                                "type": ["string", "null"],
                                "description": "Quantitative details as reported"
                            }
                        }
                    },
                    "controls_and_validation": {
                        "type": ["string", "null"],
                        "description": "Information on assay controls and validation"
                    },
                    "authors_conclusion": {
                        "type": ["string", "null"],
                        "description": "Authors' interpretation of the variant effect"
                    },
                    "where_in_paper": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific locations of this experiment"
                    },
                    "caveats": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Limitations mentioned in the paper"
                    },
                    "paper_variant_label": {
                        "type": ["string", "null"],
                        "description": "Exact variant label used in the paper"
                    },
                    "variant_link_confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Confidence that paper_variant_label corresponds to TARGET_VARIANT"
                    }
                }
            }
        },
        "overall_evidence": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "evidence_level",
                "evidence_strength",
                "odds_path",
                "validation_basis",
                "basis"
            ],
            "properties": {
                "evidence_level": {
                    "type": "string",
                    "enum": ["PS3", "BS3", "not_clear"],
                    "description": "Overall functional evidence classification"
                },
                "evidence_strength": {
                    "type": "string",
                    "enum": ["very_strong", "strong", "moderate", "supporting", "not_clear"],
                    "description": "Strength of the functional evidence"
                },
                "odds_path": {
                    "type": ["number", "null"],
                    "description": "OddsPath value if explicitly reported"
                },
                "validation_basis": {
                    "type": ["string", "null"],
                    "description": "Justification for the chosen evidence_strength"
                },
                "basis": {
                    "type": "string",
                    "description": "Short rationale summarizing the evidence"
                }
            }
        },
        "summary": {
            "type": "string",
            "description": "2–5 sentence narrative of the PS3/BS3 call"
        }
    }
}


def llm_filter_functional_papers(
    candidate_papers: List[CandidatePaper],
    variant_label: str,
) -> List[FunctionalPaper]:
    """
    Use an LLM to decide which papers contain experimental functional data.
    
    Uses high-sensitivity screening to minimize false negatives.
    Papers passing this filter should be reviewed with full-text extraction.
    """
    functional: List[FunctionalPaper] = []

    print(f"   Filtering {len(candidate_papers)} papers for functional evidence...")

    for i, p in enumerate(candidate_papers, 1):
        if i % 10 == 0:
            print(f"   Processed {i}/{len(candidate_papers)} papers...")

        # Build user prompt with paper details
        user_prompt = f"""Analyze this paper for functional evidence:

Variant of interest: {variant_label}
PMID: {p.pmid}
Title: {p.title}
Abstract: {p.abstract}

Based on the system instructions, respond in JSON with keys:
- "is_functional": true/false
- "justification": short string (1-3 sentences explaining your decision).
"""

        try:
            # Use system prompt + user prompt structure
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=ABSTRACT_CLASSIFICATION_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            resp = LLM.invoke(messages)

            # resp.content can be a string or a list of content parts
            content = resp.content
            if isinstance(content, list):
                # LangChain sometimes returns a list of dicts with "text"
                content = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )

            # Clean up potential markdown code blocks
            content = re.sub(r"```(?:json)?", "", content).strip()
            content = content.replace("```", "")
            
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
    pdf_dir: Optional[str] = None,
) -> List[FunctionalExperiment]:
    """
    Extract experiment details using LLM.
    
    If pdf_dir is provided and PDFs exist, will use full-text PDF extraction.
    Otherwise falls back to abstract-based extraction.
    
    Parameters
    ----------
    functional_papers : list of FunctionalPaper
        Papers identified as containing functional evidence
    variant_label : str
        Variant identifier string for LLM context
    pdf_dir : str, optional
        Directory containing PDFs named {pmid}.pdf
        
    Returns
    -------
    list of FunctionalExperiment
        Extracted experiments
    """
    experiments: List[FunctionalExperiment] = []

    print(f"   Extracting experiments from {len(functional_papers)} functional papers...")

    for i, fp in enumerate(functional_papers, 1):
        print(f"   Processing paper {i}/{len(functional_papers)}: PMID {fp.pmid}")
        
        # Check if PDF exists
        pdf_path = None
        if pdf_dir:
            candidate_pdf = Path(pdf_dir) / f"{fp.pmid}.pdf"
            if candidate_pdf.exists():
                pdf_path = str(candidate_pdf)
                fp.pdf_path = pdf_path
        
        # Try PDF-based extraction first if available
        if pdf_path:
            extracted = _extract_from_pdf(fp.pmid, variant_label, pdf_path, fp.title)
            if extracted:
                experiments.extend(extracted)
                continue
        
        # Fallback to abstract-based extraction
        extracted = _extract_from_abstract(fp.pmid, variant_label, fp.title)
        experiments.extend(extracted)

    return experiments


def _extract_from_abstract(
    pmid: str,
    variant_label: str,
    title: str,
) -> List[FunctionalExperiment]:
    """Extract experiments from abstract text (fallback when no PDF)."""
    from langchain_core.messages import SystemMessage, HumanMessage
    
    full_text = fetch_full_text_or_abstract(pmid)
    
    # Simplified extraction prompt for abstract-only
    system_prompt = """You are helping evaluate ACMG criteria PS3 and BS3 for a genetic variant.

ACMG functional criteria:
- PS3: Well-established in vitro or in vivo functional studies supportive of a damaging
  effect on the gene or gene product.
- BS3: Well-established in vitro or in vivo functional studies show no damaging effect
  on protein function or splicing.

Task: Extract all experiments that directly test the functional impact of the target variant.

Return JSON with key "experiments" containing a list of objects with these keys:
- assay_type: type of assay (e.g. "enzyme activity", "minigene splicing")
- system: experimental system (e.g. "HEK293 cells", "patient fibroblasts")
- readout: what was measured
- effect_direction: one of ["strong_loss_of_function", "partial_loss_of_function",
   "gain_of_function", "dominant_negative", "no_effect_vs_wildtype", "ambiguous"]
- magnitude_stats: quantitative details (fold-changes, p-values)
- controls_validity: information on controls and replication
- authors_conclusion: what authors conclude about the variant
- evaluation: one of ["supports_pathogenic", "supports_benign", "ambiguous", "low_quality"]

If no relevant experiments found, return {"experiments": []}.
"""
    
    user_prompt = f"""Variant of interest: {variant_label}
Paper PMID: {pmid}
Title: {title}

Paper text:
---
{full_text[:25000]}
---

Extract functional experiments for this variant and return as JSON.
"""
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        resp = LLM.invoke(messages)
        
        content = resp.content
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        
        # Clean up potential markdown
        content = re.sub(r"```(?:json)?", "", content).strip()
        content = content.replace("```", "")
        
        parsed = json.loads(content)
        
        exp_list = parsed.get("experiments", [])
        if not isinstance(exp_list, list):
            return []
        
        experiments = []
        for e in exp_list:
            experiments.append(
                FunctionalExperiment(
                    pmid=pmid,
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
        return experiments
        
    except Exception as e:
        print(f"   Warning: Abstract extraction failed for PMID {pmid}: {e}")
        return []


def _extract_from_pdf(
    pmid: str,
    variant_label: str,
    pdf_path: str,
    title: str,
) -> List[FunctionalExperiment]:
    """
    Extract experiments from full-text PDF using the comprehensive schema.
    
    Supports multiple extraction modes:
    - Agentic: Uses OCR, layout detection, and VLM tools (page-by-page)
    - Simple: Uses provider-specific PDF upload APIs
    
    Supports multiple LLM providers for simple mode:
    - OpenAI: Uses file upload with responses API
    - Anthropic/Claude: Uses base64-encoded PDF with messages API
    - Gemini: Uses file upload with generative AI API
    """
    from .config import LLM_PROVIDER, USE_AGENTIC_EXTRACTION
    
    # Check if agentic extraction is enabled
    if USE_AGENTIC_EXTRACTION:
        try:
            from .agentic_extraction import extract_experiments_agentic
            return extract_experiments_agentic(pdf_path, variant_label, pmid)
        except ImportError as e:
            print(f"   Warning: Agentic extraction dependencies not available: {e}")
            print(f"   Falling back to simple extraction...")
        except Exception as e:
            print(f"   Warning: Agentic extraction failed: {e}")
            print(f"   Falling back to simple extraction...")
    
    # Dispatch to provider-specific implementation (simple mode)
    if LLM_PROVIDER == "openai":
        return _extract_from_pdf_openai(pmid, variant_label, pdf_path, title)
    elif LLM_PROVIDER == "anthropic":
        return _extract_from_pdf_anthropic(pmid, variant_label, pdf_path, title)
    elif LLM_PROVIDER == "gemini":
        return _extract_from_pdf_gemini(pmid, variant_label, pdf_path, title)
    else:
        print(f"   Note: PDF extraction not supported for {LLM_PROVIDER}, using abstract")
        return []


def _parse_pdf_extraction_response(
    pmid: str,
    content: str,
) -> List[FunctionalExperiment]:
    """
    Parse JSON response from PDF extraction and convert to FunctionalExperiment objects.
    
    Common helper for all providers.
    """
    # Clean up potential markdown code blocks
    content = re.sub(r"```(?:json)?", "", content).strip()
    content = content.replace("```", "")
    
    parsed = json.loads(content)
    
    experiments = []
    for exp in parsed.get("experiments", []):
        result = exp.get("result", {})
        
        # Map direction to evaluation
        direction = result.get("direction", "unclear")
        if direction == "functionally_abnormal":
            evaluation = "supports_pathogenic"
            effect_dir = "loss_of_function"
        elif direction == "functionally_normal":
            evaluation = "supports_benign"
            effect_dir = "no_effect_vs_wildtype"
        else:
            evaluation = "ambiguous"
            effect_dir = "ambiguous"
        
        experiments.append(
            FunctionalExperiment(
                pmid=pmid,
                assay_type=exp.get("assay", "") or "",
                system=exp.get("system", "") or "",
                readout=exp.get("readout", "") or "",
                effect_direction=effect_dir,
                magnitude_stats=result.get("effect_size_and_stats", "") or "",
                controls_validity=exp.get("controls_and_validation", "") or "",
                authors_conclusion=exp.get("authors_conclusion", "") or "",
                evaluation=evaluation,
            )
        )
    
    return experiments


def _extract_from_pdf_openai(
    pmid: str,
    variant_label: str,
    pdf_path: str,
    title: str,
) -> List[FunctionalExperiment]:
    """Extract experiments from PDF using OpenAI's file upload API."""
    try:
        import os
        from openai import OpenAI
        from .config import LLM_MODEL
        
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Upload PDF
        with open(pdf_path, "rb") as f:
            uploaded_file = client.files.create(file=f, purpose="assistants")
        
        user_prompt = f"""TARGET_VARIANT: {variant_label}

Attached: 1 full-text PDF paper (PMID: {pmid}, Title: {title}).

Follow the system instructions to:
- Match the TARGET_VARIANT to variant labels in the paper,
- Extract all plausible variant-level functional experiments for that variant,
- Summarize PS3/BS3 evidence and strength.

Return ONLY valid JSON that matches the schema exactly.
Do NOT add any text outside the JSON object.
"""
        
        resp = client.responses.create(
            model=LLM_MODEL,
            instructions=PDF_EXTRACTION_SYSTEM_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": uploaded_file.id},
                        {"type": "input_text", "text": user_prompt},
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "variant_functional_summary",
                    "strict": True,
                    "schema": VARIANT_FUNCTIONAL_SCHEMA,
                }
            },
            store=False,
        )
        
        if not getattr(resp, "output_text", None):
            print(f"   Warning: Empty response for PDF extraction PMID {pmid}")
            return []
        
        return _parse_pdf_extraction_response(pmid, resp.output_text)
        
    except Exception as e:
        print(f"   Warning: OpenAI PDF extraction failed for PMID {pmid}: {e}")
        return []


def _extract_from_pdf_anthropic(
    pmid: str,
    variant_label: str,
    pdf_path: str,
    title: str,
) -> List[FunctionalExperiment]:
    """
    Extract experiments from PDF using Anthropic's Claude API with base64 encoding.
    
    Claude supports PDF files via base64-encoded document content type.
    """
    try:
        import os
        import base64
        from anthropic import Anthropic
        from .config import LLM_MODEL
        
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        # Read and encode PDF as base64
        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        user_prompt = f"""TARGET_VARIANT: {variant_label}

Attached: 1 full-text PDF paper (PMID: {pmid}, Title: {title}).

Follow the system instructions to:
- Match the TARGET_VARIANT to variant labels in the paper,
- Extract all plausible variant-level functional experiments for that variant,
- Summarize PS3/BS3 evidence and strength.

Return ONLY valid JSON that matches the schema exactly.
Do NOT add any text outside the JSON object.
"""
        
        resp = client.messages.create(
            model=LLM_MODEL,
            max_tokens=8192,
            system=PDF_EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }
            ],
        )
        
        # Extract text content from response
        content = ""
        for block in resp.content:
            if hasattr(block, "text"):
                content += block.text
        
        if not content:
            print(f"   Warning: Empty response for PDF extraction PMID {pmid}")
            return []
        
        return _parse_pdf_extraction_response(pmid, content)
        
    except Exception as e:
        print(f"   Warning: Anthropic PDF extraction failed for PMID {pmid}: {e}")
        return []


def _extract_from_pdf_gemini(
    pmid: str,
    variant_label: str,
    pdf_path: str,
    title: str,
) -> List[FunctionalExperiment]:
    """
    Extract experiments from PDF using Google's Gemini API with file upload.
    
    Gemini supports PDF files via the upload_file method.
    """
    try:
        import os
        import google.generativeai as genai
        from .config import LLM_MODEL
        
        # Configure the API
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        # Upload the PDF file
        uploaded_file = genai.upload_file(pdf_path, mime_type="application/pdf")
        
        user_prompt = f"""TARGET_VARIANT: {variant_label}

Attached: 1 full-text PDF paper (PMID: {pmid}, Title: {title}).

Follow the system instructions to:
- Match the TARGET_VARIANT to variant labels in the paper,
- Extract all plausible variant-level functional experiments for that variant,
- Summarize PS3/BS3 evidence and strength.

Return ONLY valid JSON that matches the schema exactly.
Do NOT add any text outside the JSON object.
"""
        
        # Create the model and generate content
        model = genai.GenerativeModel(
            model_name=LLM_MODEL,
            system_instruction=PDF_EXTRACTION_SYSTEM_PROMPT,
        )
        
        resp = model.generate_content(
            [uploaded_file, user_prompt],
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        
        content = resp.text
        
        if not content:
            print(f"   Warning: Empty response for PDF extraction PMID {pmid}")
            return []
        
        return _parse_pdf_extraction_response(pmid, content)
        
    except Exception as e:
        print(f"   Warning: Gemini PDF extraction failed for PMID {pmid}: {e}")
        return []



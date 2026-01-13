"""
LLM-based evidence integration and PS3/BS3 assessment.

Uses an LLM to evaluate all extracted functional experiments and determine
the appropriate PS3/BS3 classification with evidence strength levels based on:
- ACMG/AMP 2015 guidelines (Richards et al.)
- ClinGen SVI 2019 recommendations for PS3/BS3 (Brnich et al.)
"""

import re
import json
from typing import List, Optional
from dataclasses import asdict

from .llm import LLM
from .utils import FunctionalExperiment, IntegratedAssessment


# =============================================================================
# LLM INTEGRATION PROMPT
# =============================================================================

EVIDENCE_INTEGRATION_SYSTEM_PROMPT = r"""
You are a clinical variant interpretation curator specializing in ACMG/AMP PS3/BS3 functional evidence criteria.

Your task is to evaluate functional experiment data extracted from scientific literature and determine the appropriate PS3/BS3 classification with evidence strength.

────────────────────────────────────
ACMG/AMP DEFINITIONS (Richards et al., 2015)
────────────────────────────────────

PS3 (Pathogenic Strong): Well-established in vitro or in vivo functional studies supportive of a DAMAGING effect on the gene or gene product.

BS3 (Benign Strong): Well-established in vitro or in vivo functional studies show NO DAMAGING effect on protein function or splicing.

Key considerations from ACMG/AMP:
- Functional studies can be powerful but not all assays are equally effective
- Consider how closely the assay reflects the biological environment
- Patient-derived samples provide stronger evidence than in vitro expression
- Full biological function assays are stronger than partial function assays
- Validation, reproducibility, and robustness are important factors
- Assays that assess mRNA-level impact (splicing, stability) can be informative

────────────────────────────────────
ClinGen SVI STRENGTH FRAMEWORK (Brnich et al., 2019)
────────────────────────────────────

Evidence strength depends on assay validation and quality:

**very_strong**: 
- Rigorous statistical validation with formal odds of pathogenicity (OddsPath) calculation
- Extensive calibration against known pathogenic and benign variants
- Multiple independent, well-validated assays with consistent results
- This level is RARE and requires exceptional evidence

**strong**:
- Well-established assays with rigorous validation
- Multiple independent studies with consistent results
- Clear controls (wild-type, null/positive) and biological replicates
- Well-documented methodology with good reproducibility
- At least 2 high-quality papers with concordant functional data

**moderate**:
- Validated assay with multiple controls (ideally 11+ variant controls)
- Good experimental design with replicates
- Clear comparator (wild-type or healthy control)
- Single well-validated study OR multiple studies with minor inconsistencies
- Assay measures relevant biological function

**supporting**:
- Basic assay with limited validation or controls
- Single study without extensive replication
- Assay that measures only partial protein function
- Results from patient-derived material without variant-specific controls
- Limited documentation of methodology or controls

────────────────────────────────────
DECISION RULES
────────────────────────────────────

1. **PS3 applies when**:
   - Functional studies consistently show ABNORMAL function
   - Effect is consistent with disease mechanism (e.g., loss-of-function for haploinsufficiency)
   - Assay quality supports the claimed strength level

2. **BS3 applies when**:
   - Functional studies consistently show NORMAL function
   - Assay adequately captures relevant protein function
   - No evidence of damaging effect on protein or splicing

3. **not_clear applies when**:
   - Evidence is CONFLICTING (some abnormal, some normal results)
   - Evidence is INSUFFICIENT (too few experiments or poor quality)
   - Evidence is AMBIGUOUS (intermediate effects, unclear interpretation)
   - Assay does not adequately measure relevant function
   - No functional experiments available

────────────────────────────────────
EVALUATION PROCESS
────────────────────────────────────

For each experiment, evaluate:
1. Assay type and biological relevance
2. Quality indicators: controls, replicates, validation
3. Functional outcome: abnormal vs normal vs intermediate
4. Confidence that the tested variant matches the target variant

Then synthesize across all experiments to determine:
- Overall evidence direction (PS3 vs BS3 vs not_clear)
- Appropriate strength level
- Confidence in the assessment

────────────────────────────────────
OUTPUT FORMAT
────────────────────────────────────

Return ONLY valid JSON matching this schema:
{
  "decision": "PS3" | "BS3" | "not_clear",
  "strength": "very_strong" | "strong" | "moderate" | "supporting" | null,
  "confidence": "high" | "medium" | "low",
  "narrative": "2-4 sentence summary explaining the evidence and rationale for the decision",
  "experiment_evaluations": [
    {
      "pmid": "string",
      "assay_type": "string",
      "quality_assessment": "high" | "moderate" | "low",
      "functional_outcome": "abnormal" | "normal" | "intermediate" | "unclear",
      "supports": "PS3" | "BS3" | "neither",
      "notes": "brief note on this experiment"
    }
  ],
  "key_considerations": ["list of key factors that influenced the decision"]
}

IMPORTANT:
- If decision is "not_clear", strength MUST be null
- If no experiments are provided, decision MUST be "not_clear" with strength null
- Be conservative: when in doubt, use lower strength or "not_clear"
- Do not hallucinate or invent experimental details
- Base assessment ONLY on the provided experiment data
"""

# JSON Schema for structured output
EVIDENCE_INTEGRATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "strength",
        "confidence",
        "narrative",
        "experiment_evaluations",
        "key_considerations"
    ],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["PS3", "BS3", "not_clear"],
            "description": "Overall functional evidence classification"
        },
        "strength": {
            "type": ["string", "null"],
            "enum": ["very_strong", "strong", "moderate", "supporting", None],
            "description": "Evidence strength level (null if decision is not_clear)"
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence in the assessment"
        },
        "narrative": {
            "type": "string",
            "description": "2-4 sentence summary of evidence and rationale"
        },
        "experiment_evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pmid", "assay_type", "quality_assessment", "functional_outcome", "supports", "notes"],
                "properties": {
                    "pmid": {"type": "string"},
                    "assay_type": {"type": "string"},
                    "quality_assessment": {
                        "type": "string",
                        "enum": ["high", "moderate", "low"]
                    },
                    "functional_outcome": {
                        "type": "string",
                        "enum": ["abnormal", "normal", "intermediate", "unclear"]
                    },
                    "supports": {
                        "type": "string",
                        "enum": ["PS3", "BS3", "neither"]
                    },
                    "notes": {"type": "string"}
                }
            }
        },
        "key_considerations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key factors that influenced the decision"
        }
    }
}


def integrate_evidence(
    experiments: List[FunctionalExperiment],
    variant_label: str,
) -> IntegratedAssessment:
    """
    Use LLM to integrate functional evidence and make PS3/BS3 call.
    
    Based on ACMG/AMP 2015 guidelines and ClinGen SVI 2019 recommendations.
    
    Parameters
    ----------
    experiments : List[FunctionalExperiment]
        Extracted functional experiments from literature
    variant_label : str
        Variant identifier string for context
        
    Returns
    -------
    IntegratedAssessment
        Integrated assessment with decision, strength, narrative, and confidence
    """
    key_pmids = sorted({e.pmid for e in experiments})
    
    # Handle empty experiments case
    if not experiments:
        return IntegratedAssessment(
            decision="none",
            narrative=(
                "No functional experiments directly testing this variant were identified "
                "in the retrieved literature. Therefore, PS3 and BS3 are not applied."
            ),
            strength=None,
            key_pmids=[],
            confidence=None,
        )
    
    # Try LLM-based integration
    try:
        result = _llm_integrate_evidence(experiments, variant_label)
        result.key_pmids = key_pmids
        return result
    except Exception as e:
        print(f"   Warning: LLM evidence integration failed: {e}")
        print("   Falling back to rule-based integration...")
        return _fallback_integrate_evidence(experiments)


def _llm_integrate_evidence(
    experiments: List[FunctionalExperiment],
    variant_label: str,
) -> IntegratedAssessment:
    """
    LLM-based evidence integration using ACMG/AMP and ClinGen SVI criteria.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    
    # Format experiments for the prompt
    experiments_text = _format_experiments_for_prompt(experiments)
    
    user_prompt = f"""Evaluate the following functional experiments for variant: {variant_label}

────────────────────────────────────
EXTRACTED FUNCTIONAL EXPERIMENTS
────────────────────────────────────

{experiments_text}

────────────────────────────────────
INSTRUCTIONS
────────────────────────────────────

Based on the ACMG/AMP guidelines and ClinGen SVI framework described in the system prompt:

1. Evaluate each experiment for quality, relevance, and functional outcome
2. Synthesize the evidence to determine overall PS3/BS3/not_clear classification
3. Assign appropriate strength level based on validation and quality
4. Provide a clear narrative explaining your reasoning

Return your assessment as JSON following the schema in the system prompt.
"""
    
    messages = [
        SystemMessage(content=EVIDENCE_INTEGRATION_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ]
    
    resp = LLM.invoke(messages)
    
    # Parse response
    content = resp.content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )
    
    # Clean up potential markdown code blocks
    content = re.sub(r"```(?:json)?", "", content).strip()
    content = content.replace("```", "")
    
    parsed = json.loads(content)
    
    # Map decision
    decision = parsed.get("decision", "not_clear")
    if decision == "not_clear":
        decision = "none"  # Internal representation
    
    # Get strength (null becomes None)
    strength = parsed.get("strength")
    if strength == "null" or strength is None:
        strength = None
    
    return IntegratedAssessment(
        decision=decision,
        narrative=parsed.get("narrative", ""),
        strength=strength,
        key_pmids=[],  # Will be filled by caller
        confidence=parsed.get("confidence"),
    )


def _format_experiments_for_prompt(experiments: List[FunctionalExperiment]) -> str:
    """Format experiments into a readable text block for the LLM prompt."""
    lines = []
    
    for i, exp in enumerate(experiments, 1):
        lines.append(f"Experiment {i} (PMID: {exp.pmid})")
        lines.append(f"  Assay Type: {exp.assay_type}")
        lines.append(f"  System: {exp.system}")
        lines.append(f"  Readout: {exp.readout}")
        lines.append(f"  Effect Direction: {exp.effect_direction}")
        lines.append(f"  Magnitude/Stats: {exp.magnitude_stats}")
        lines.append(f"  Controls & Validity: {exp.controls_validity}")
        lines.append(f"  Authors' Conclusion: {exp.authors_conclusion}")
        lines.append(f"  Initial Evaluation: {exp.evaluation}")
        lines.append("")
    
    return "\n".join(lines)


def _fallback_integrate_evidence(
    experiments: List[FunctionalExperiment],
) -> IntegratedAssessment:
    """
    Fallback rule-based evidence integration.
    
    Used when LLM integration fails.
    """
    pathogenic_support = [
        e for e in experiments if e.evaluation == "supports_pathogenic"
    ]
    benign_support = [
        e for e in experiments if e.evaluation == "supports_benign"
    ]

    def high_quality(exps: List[FunctionalExperiment]) -> List[FunctionalExperiment]:
        # crude: longer "controls_validity" text → more detailed assay description
        return [e for e in exps if len(e.controls_validity) > 40]

    high_q_path = high_quality(pathogenic_support)
    high_q_benign = high_quality(benign_support)

    decision = "none"
    strength: Optional[str] = None
    key_pmids: List[str] = sorted({e.pmid for e in experiments})

    if len({e.pmid for e in high_q_path}) >= 2 and not high_q_benign:
        decision = "PS3"
        strength = "strong"
    elif len({e.pmid for e in high_q_benign}) >= 2 and not high_q_path:
        decision = "BS3"
        strength = "strong"
    elif high_q_path and not high_q_benign:
        decision = "PS3"
        strength = "supporting"
    elif high_q_benign and not high_q_path:
        decision = "BS3"
        strength = "supporting"
    else:
        decision = "none"
        strength = None

    # Build narrative
    narrative_parts: List[str] = []
    if pathogenic_support:
        narrative_parts.append(
            f"{len(pathogenic_support)} experiment(s) across "
            f"{len({e.pmid for e in pathogenic_support})} paper(s) "
            "reported impaired or abnormal function consistent with a damaging effect."
        )
    if benign_support:
        narrative_parts.append(
            f"{len(benign_support)} experiment(s) across "
            f"{len({e.pmid for e in benign_support})} paper(s) "
            "reported normal or near-normal function, consistent with a benign effect."
        )
    if not pathogenic_support and not benign_support:
        narrative_parts.append(
            "All experiments were judged ambiguous or low-quality."
        )

    if decision == "PS3":
        narrative_parts.append(
            f"Taken together, these studies provide functional evidence supporting a damaging "
            f"effect on the gene product, compatible with application of PS3 ({strength} strength). "
            f"[Note: This assessment used fallback rule-based integration.]"
        )
    elif decision == "BS3":
        narrative_parts.append(
            f"Taken together, these studies provide functional evidence supporting a "
            f"non-damaging effect on the gene product, compatible with application of BS3 ({strength} strength). "
            f"[Note: This assessment used fallback rule-based integration.]"
        )
    else:
        narrative_parts.append(
            "However, the overall body of functional evidence is insufficient or conflicting "
            "to confidently apply PS3 or BS3. "
            "[Note: This assessment used fallback rule-based integration.]"
        )

    narrative = " ".join(narrative_parts)

    return IntegratedAssessment(
        decision=decision,
        narrative=narrative,
        strength=strength,
        key_pmids=key_pmids,
        confidence="low",  # Lower confidence for fallback
    )

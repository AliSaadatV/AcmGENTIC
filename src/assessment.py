"""
Evidence integration and PS3/BS3 assessment.
"""

from typing import List, Dict, Set

from .utils import FunctionalExperiment, IntegratedAssessment


def integrate_evidence(experiments: List[FunctionalExperiment]) -> IntegratedAssessment:
    """
    Integrate evidence and make PS3/BS3 decision.

    Interpretation:
    - Experiments with evaluation == "supports_pathogenic" map to PS3-like evidence.
    - Experiments with evaluation == "supports_benign"    map to BS3-like evidence.

    PS3: Well-established in vitro or in vivo functional studies supportive of a damaging effect.
    BS3: Well-established in vitro or in vivo functional studies show no damaging effect.
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
    strength: str = None
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

    if not experiments:
        narrative = (
            "No functional experiments directly testing this variant were identified "
            "in the retrieved literature. Therefore, PS3 and BS3 are not applied."
        )
    else:
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
                f"effect on the gene product, compatible with application of PS3 ({strength} strength)."
            )
        elif decision == "BS3":
            narrative_parts.append(
                f"Taken together, these studies provide functional evidence supporting a "
                f"non-damaging effect on the gene product, compatible with application of BS3 ({strength} strength)."
            )
        else:
            narrative_parts.append(
                "However, the overall body of functional evidence is insufficient or conflicting "
                "to confidently apply PS3 or BS3."
            )

        narrative = " ".join(narrative_parts)

    return IntegratedAssessment(
        decision=decision,
        narrative=narrative,
        strength=strength,
        key_pmids=key_pmids,
    )

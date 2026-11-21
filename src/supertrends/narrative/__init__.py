# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Evidence documents, the deterministic template narrative and the numeric guard (S3-T08).

The evidence document is the contract: every surface renders from it and nothing recomputes
scores for display (BUILD_PROMPT, Justification). Narratives never feed back into scoring,
ranking or selection.
"""

from supertrends.narrative.evidence import build_evidence
from supertrends.narrative.guard import GuardResult, check_numbers
from supertrends.narrative.template import NarrativeResult, narrate

__all__ = ["GuardResult", "NarrativeResult", "build_evidence", "check_numbers", "narrate"]

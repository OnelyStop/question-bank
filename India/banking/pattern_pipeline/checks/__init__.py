"""Quality-check skill registry — each check is one skill.

Mirrors `patterns/__init__.py`. Pattern skills say *what* a question is; check
skills say *whether it is serveable*. Pattern-specific completeness rules live
on the pattern itself via `PatternSkill.validate()`, not here — this registry is
only for rules that apply regardless of pattern.
"""

from __future__ import annotations

from .base import TIERS, CheckSkill, CorpusCheckSkill, Defect
from .brand_residue import BrandResidueCheck
from .context_missing import ContextMissingCheck
from .context_unusable import ContextUnusableCheck
from .direction_set_integrity import DirectionSetIntegrityCheck
from .duplicate_content import DuplicateContentCheck, DuplicateQIdCheck
from .fraction_flattened import FractionFlattenedCheck
from .language_script import LanguageScriptCheck
from .option_bleed import OptionBleedCheck
from .option_duplicate import OptionDuplicateCheck
from .option_empty import OptionEmptyCheck
from .option_partial import OptionPartialCheck
from .schema_conformance import SchemaConformanceCheck
from .stem_too_short import StemTooShortCheck
from .stem_truncated import StemTruncatedCheck
from .text_garbled import TextGarbledCheck

# Per-row checks. Order is presentation only — every check always runs.
ROW_CHECKS = [
    SchemaConformanceCheck(),
    StemTooShortCheck(),
    OptionPartialCheck(),
    OptionEmptyCheck(),
    OptionDuplicateCheck(),
    OptionBleedCheck(),
    ContextMissingCheck(),
    ContextUnusableCheck(),
    TextGarbledCheck(),
    LanguageScriptCheck(),
    FractionFlattenedCheck(),
    StemTruncatedCheck(),
    BrandResidueCheck(),
]

# Checks needing the whole corpus at once.
CORPUS_CHECKS = [
    DuplicateQIdCheck(),
    DuplicateContentCheck(),
    DirectionSetIntegrityCheck(),
]

ALL_CHECKS = ROW_CHECKS + CORPUS_CHECKS

__all__ = [
    "ROW_CHECKS",
    "CORPUS_CHECKS",
    "ALL_CHECKS",
    "CheckSkill",
    "CorpusCheckSkill",
    "Defect",
    "TIERS",
]

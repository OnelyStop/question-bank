"""Pattern skill registry — each pattern is one classifier skill."""

from __future__ import annotations

from .bilingual_stem_directions import BilingualStemDirectionsSkill
from .caselet_di_set import CaseletDiSetSkill
from .cloze_passage_set import ClozePassageSetSkill
from .data_sufficiency import DataSufficiencySkill
from .image_figure_based import ImageFigureBasedSkill
from .match_the_columns import MatchTheColumnsSkill
from .partial_or_missing_options import PartialOrMissingOptionsSkill
from .quantity_comparison import QuantityComparisonSkill
from .quadratic_comparison import QuadraticComparisonSkill
from .reading_comprehension_set import ReadingComprehensionSetSkill
from .shared_directions_set import SharedDirectionsSetSkill
from .standalone_mcq import StandaloneMcqSkill
from .table_di_set import TableDiSetSkill
from .visual_chart_graph_di import VisualChartGraphDiSkill

# Primary classifiers only (bilingual is secondary flag skill).
PRIMARY_SKILLS = [
    PartialOrMissingOptionsSkill(),
    ImageFigureBasedSkill(),
    VisualChartGraphDiSkill(),
    TableDiSetSkill(),
    ClozePassageSetSkill(),
    ReadingComprehensionSetSkill(),
    DataSufficiencySkill(),
    QuantityComparisonSkill(),
    QuadraticComparisonSkill(),
    MatchTheColumnsSkill(),
    CaseletDiSetSkill(),
    SharedDirectionsSetSkill(),
    StandaloneMcqSkill(),
]

SECONDARY_SKILLS = [
    BilingualStemDirectionsSkill(),
]

ALL_SKILLS = PRIMARY_SKILLS + SECONDARY_SKILLS

__all__ = [
    "PRIMARY_SKILLS",
    "SECONDARY_SKILLS",
    "ALL_SKILLS",
]

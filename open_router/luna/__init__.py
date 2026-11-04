"""Semantic separation of a bounded section of page evidence."""
from .grouping import group_blocks
from .references import Fact, SourceSpan

__all__ = ["group_blocks", "Fact", "SourceSpan"]

"""
Guards against exactly the kind of drift that turns into a silent
runtime KeyError months later: the taxonomy's label space, the schema's
Literal type, and the ladder's routing table must all agree on the same
set of root causes.
"""
from typing import get_args

from app.agents.taxonomy import ROOT_CAUSES
from app.schemas.contracts import RootCause
from app.ladder.levels import ROOT_CAUSE_TO_ENTRY_LEVEL


def test_taxonomy_matches_schema_literal_exactly():
    assert set(ROOT_CAUSES) == set(get_args(RootCause))


def test_every_root_cause_has_a_ladder_entry_mapping():
    unmapped = set(ROOT_CAUSES) - set(ROOT_CAUSE_TO_ENTRY_LEVEL.keys())
    assert unmapped == set(), f"root causes with no explicit ladder entry: {unmapped}"

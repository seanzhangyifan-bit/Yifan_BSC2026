"""Pure helpers of scripts/validation/junction_tolerance_sweep.py: the
cut-off grid, replicate grouping, and re-sorting already-measured angles."""

from scripts.validation.junction_tolerance_sweep import BASELINE, census, condition_of, sweep_settings
from src.crackgraph.junctions import sector_gaps_deg_from_bearings


def test_baseline_first_and_no_duplicate_settings():
    settings = sweep_settings()
    assert settings[0] == ("baseline", *BASELINE)
    tols = [tuple(round(t, 6) for t in s[1:]) for s in settings]
    assert len(tols) == len(set(tols))


def test_condition_strips_replicate_and_capture_index():
    assert condition_of("T5-PTFE_H95_v2_mm000001.jpg") == "T5-PTFE_H95"
    assert condition_of("T2-A_PTFE_v1_IL70_mm000001.jpg") == "T2-A_PTFE_IL70"
    assert condition_of("23RH_PTFE_v1_mm000003.jpg") == "23RH_PTFE"


def test_census_follows_cut_offs():
    t_like = sector_gaps_deg_from_bearings([0.0, 180.0, 90.0])     # exact T
    y_like = sector_gaps_deg_from_bearings([90.0, 210.0, 330.0])  # exact Y
    between = sector_gaps_deg_from_bearings([0.0, 155.0, 75.0])   # gaps 75/80/205: T only at a loose cut-off
    gaps = [t_like, y_like, between]
    assert census(gaps, *BASELINE) == {"T": 1, "Y": 1, "ambiguous": 1}
    assert census(gaps, 15.0, 30.0, 20.0) == {"T": 2, "Y": 1, "ambiguous": 0}

"""Smoke tests for the new validation-gallery glue code (comparison logic,
ValidationCaseResult building) in validation_cases.py -- not a re-assertion
of the underlying measurement tolerances, which already have their own
dedicated coverage in test_curvature.py/test_anisotropy.py. Runs a representative case per method
end-to-end (real synthetic image -> real pipeline) and checks the wiring
produced a sane, passing result on each one's clean/default parameters.
"""

from src.crackgraph.validation_cases import (
    ALL_CASES,
    case_anisotropy_aligned,
    case_curvature_straight_line,
)


def test_all_case_names_are_unique(tmp_path):
    results = [case_fn(tmp_path) for case_fn in ALL_CASES]
    names = [r.name for r in results]
    assert len(names) == len(set(names))


def test_curvature_straight_line_case_passes(tmp_path):
    result = case_curvature_straight_line(tmp_path)
    assert result.method == "curvature"
    assert result.passed is True
    assert (tmp_path / result.image_relpath).exists()
    assert len(result.rows) > 0


def test_anisotropy_aligned_case_passes(tmp_path):
    result = case_anisotropy_aligned(tmp_path)
    assert result.method == "anisotropy"
    assert result.passed is True
    assert (tmp_path / result.image_relpath).exists()

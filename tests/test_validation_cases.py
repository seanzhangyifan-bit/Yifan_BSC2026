"""Smoke tests for the new validation-gallery glue code (comparison logic,
ValidationCaseResult building) in validation_cases.py -- not a re-assertion
of the underlying measurement tolerances, which already have their own
dedicated coverage in test_junction_angle.py/test_corners.py/
test_curvature.py/test_kinks.py/test_anisotropy.py. Runs a representative
case per method end-to-end (real synthetic image -> real pipeline) and
checks the wiring produced a sane, passing result on each one's clean/
default parameters.
"""

from src.crackgraph.validation_cases import (
    ALL_CASES,
    case_anisotropy_aligned,
    case_curved_t_junction_r30_corner_limitation,
    case_kink_60deg,
    case_t_junction_90,
)


def test_all_case_names_are_unique(tmp_path):
    results = [case_fn(tmp_path) for case_fn in ALL_CASES]
    names = [r.name for r in results]
    assert len(names) == len(set(names))


def test_t_junction_90_case_passes(tmp_path):
    result = case_t_junction_90(tmp_path)
    assert result.method == "junction"
    assert result.passed is True
    assert (tmp_path / result.image_relpath).exists()
    assert len(result.rows) > 0


def test_kink_60deg_case_passes(tmp_path):
    result = case_kink_60deg(tmp_path)
    assert result.method == "kink"
    assert result.passed is True
    assert (tmp_path / result.image_relpath).exists()


def test_anisotropy_aligned_case_passes(tmp_path):
    result = case_anisotropy_aligned(tmp_path)
    assert result.method == "anisotropy"
    assert result.passed is True
    assert (tmp_path / result.image_relpath).exists()


def test_curved_t_junction_r30_limitation_case_is_informational_not_a_hard_failure(tmp_path):
    # This case documents a known corner-cross-check limitation rather than
    # asserting a specific pass/fail threshold -- it should still complete
    # and report the tangent-fit's own correct "T" classification.
    result = case_curved_t_junction_r30_corner_limitation(tmp_path)
    assert result.method == "junction"
    tangent_fit_row = next(r for r in result.rows if r[0] == "tangent-fit label")
    assert tangent_fit_row[3] is True  # tangent fit still recovers T at default params

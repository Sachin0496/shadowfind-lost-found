"""Tests for the shadow pipeline and the matcher."""

import numpy as np
import pytest

import vision


@pytest.mark.parametrize("kind", ["bag", "bottle", "watch", "umbrella", "helmet"])
def test_extracts_a_silhouette(kind):
    sil = vision.extract_shadow(vision.make_sample("blue", kind, seed=3))
    assert sil.descriptor.shape == (vision.BINS,)
    assert np.isfinite(sil.descriptor).all()
    assert sil.mask.shape[:2] == (360, 480)
    assert 0.0 <= sil.iou <= 1.0


def test_descriptor_is_unit_length():
    sil = vision.extract_shadow(vision.make_sample("red", "bag", seed=1))
    assert np.isclose(np.linalg.norm(sil.descriptor), 1.0, atol=1e-5)


def test_similarity_is_bounded():
    a = vision.extract_shadow(vision.make_sample("blue", "bag", seed=1)).descriptor
    b = vision.extract_shadow(vision.make_sample("green", "watch", seed=2)).descriptor
    s = vision.similarity(a, b)
    assert 0.0 <= s <= 1.0
    assert np.isclose(vision.similarity(a, a), 1.0, atol=1e-5)


def test_rank_orders_by_score():
    q = vision.extract_shadow(vision.make_sample("blue", "bag", seed=1)).descriptor
    close = vision.extract_shadow(vision.make_sample("blue", "bag", seed=2)).descriptor
    far = vision.extract_shadow(vision.make_sample("blue", "umbrella", seed=3)).descriptor
    ranked = vision.rank(q, [(1, far), (2, close)])
    assert ranked[0][0] == 2
    assert ranked[0][1] >= ranked[1][1]


def test_empty_image_is_rejected():
    with pytest.raises(ValueError):
        vision.extract_shadow(np.zeros((0, 0, 3), np.uint8))


def test_blank_image_has_no_descriptor_mass():
    sil = vision.extract_shadow(np.full((120, 160, 3), 255, np.uint8))
    assert sil.descriptor.shape == (vision.BINS,)

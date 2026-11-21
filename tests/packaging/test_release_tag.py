"""Tests for validating GitHub release tags against built package versions."""

import pytest

from check_distribution_metadata import verify_release_tag


def test_release_tag_matches_built_distribution_version():
    verify_release_tag("v1.0.0", "1.0.0")


@pytest.mark.parametrize("release_tag", ["1.0.0", "v1.0.1", "v1.0.0-rc.1"])
def test_release_tag_mismatch_is_rejected(release_tag):
    with pytest.raises(ValueError, match="does not match built distribution version"):
        verify_release_tag(release_tag, "1.0.0")

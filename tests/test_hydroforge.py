"""Basic tests for hydroforge package."""

import hydroforge


def test_import():
    """Test that hydroforge can be imported."""
    assert hydroforge is not None


def test_version():
    """Test that hydroforge has a version."""
    assert hasattr(hydroforge, "__version__")

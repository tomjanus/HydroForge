"""Basic tests for hydroforge package."""

import hydroforge


def test_import():
    """Test that hydroforge can be imported."""
    assert hydroforge is not None


def test_version():
    """Test that hydroforge has a version."""
    assert hasattr(hydroforge, "__version__")


def test_generic_packages_do_not_import_wdn_modelling():
    """Layering rule: generic packages must never import hydroforge.wdn_modelling.

    Importing :mod:`hydroforge.auxiliary`, :mod:`hydroforge.uncertainty`,
    :mod:`hydroforge.measurements` and :mod:`hydroforge.sampling` must not pull
    in the WDN / EPANET-specific :mod:`hydroforge.wdn_modelling` package.
    """
    import sys

    # Drop any previously imported wdn_modelling modules so the assertion is
    # not affected by test ordering (e.g. the backend-shim test imports it).
    for module in list(sys.modules):
        if module == "hydroforge.wdn_modelling" or module.startswith(
            "hydroforge.wdn_modelling."
        ):
            del sys.modules[module]

    import hydroforge.auxiliary  # noqa: F401
    import hydroforge.uncertainty  # noqa: F401
    import hydroforge.measurements  # noqa: F401
    import hydroforge.sampling  # noqa: F401

    assert "hydroforge.wdn_modelling" not in sys.modules
    assert not any(name.startswith("hydroforge.wdn_modelling") for name in sys.modules)

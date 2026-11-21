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
    # not affected by test ordering (e.g. backend tests import it).
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


def test_legacy_top_level_packages_are_not_importable():
    """Deprecated WDN package shims must not remain available."""
    import importlib

    import pytest

    legacy_packages = (
        "hydroforge.backends",
        "hydroforge.epanetfile_io",
        "hydroforge.graphs",
        "hydroforge.modifiers",
        "hydroforge.networks",
        "hydroforge.sensors",
    )
    for package in legacy_packages:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(package)


def test_tsnet_config_uses_canonical_name_only():
    """The TSNet config alias is not retained after the module migration."""
    from hydroforge.wdn_modelling.backends.tsnet import config

    assert hasattr(config, "TSNetConfig")
    assert not hasattr(config, "TSNetSimulatorConfig")


def test_backend_name_is_a_string_enum():
    """Backend names retain StrEnum-compatible string behavior."""
    from hydroforge.wdn_modelling.backends import BackendName

    assert isinstance(BackendName.WNTR, str)
    assert BackendName.WNTR == "wntr"
    assert str(BackendName.WNTR) == "wntr"

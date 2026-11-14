"""Tests for optional simulation backend dependency handling."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hydroforge.backends import registry


@pytest.fixture(autouse=True)
def clear_backend_cache():
    registry.get_backend.cache_clear()
    yield
    registry.get_backend.cache_clear()


@pytest.mark.parametrize(
    ("backend_name", "package_name", "install_requirement"),
    [
        ("tsnet", "tsnet", "git+https://github.com/glorialulu/TSNet.git"),
        (
            "tsnetplus",
            "tsnetplus",
            "git+https://github.com/tomjanus/TSNetPlus.git",
        ),
        ("ptsnet", "ptsnet", "ptsnet"),
    ],
)
def test_missing_dependency_declines_install_by_default(
    backend_name, package_name, install_requirement, monkeypatch
):
    prompts = []

    def decline(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(registry, "find_spec", lambda _name: None)
    monkeypatch.setattr("builtins.input", decline)
    run = Mock()
    monkeypatch.setattr(registry.subprocess, "run", run)

    with pytest.raises(ImportError, match=package_name) as error:
        registry._ensure_optional_dependency(backend_name)

    assert package_name in str(error.value)
    assert install_requirement in str(error.value)
    assert prompts == [
        f"The {backend_name} backend requires the '{package_name}' package, "
        "which is not installed. It must be installed before execution. "
        "Install it now? [y/N]: "
    ]
    run.assert_not_called()


def test_missing_dependency_installs_only_after_confirmation(monkeypatch):
    monkeypatch.setattr(registry, "find_spec", lambda _name: None)
    monkeypatch.setattr("builtins.input", lambda _message: "y")
    run = Mock()
    monkeypatch.setattr(registry.subprocess, "run", run)

    registry._ensure_optional_dependency("ptsnet")

    run.assert_called_once_with(
        [registry.sys.executable, "-m", "pip", "install", "ptsnet"],
        check=True,
    )


def test_resolving_backend_checks_dependency_before_import(monkeypatch):
    events = []

    def find_spec(package_name):
        events.append(("check", package_name))
        return None

    def install(*_args, **_kwargs):
        events.append(("install", "ptsnet"))

    monkeypatch.setattr(registry, "find_spec", find_spec)
    monkeypatch.setattr("builtins.input", lambda _message: "yes")
    monkeypatch.setattr(registry.subprocess, "run", install)

    class PTSNetBackend:
        pass

    def import_module(module_name):
        events.append(("import", module_name))
        return SimpleNamespace(PTSNetBackend=PTSNetBackend)

    monkeypatch.setattr(registry.importlib, "import_module", import_module)

    assert registry._resolve_backend_class("ptsnet") is PTSNetBackend
    assert events == [
        ("check", "ptsnet"),
        ("install", "ptsnet"),
        ("import", "hydroforge.backends.ptsnet_backend"),
    ]

"""Behavior tests for the built distribution artifact checker."""

from io import BytesIO
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from check_distribution_metadata import verify_distribution_artifacts


def _write_distribution_artifacts(
    distribution_dir: Path,
    *,
    wheel_name: str = "hydroforge-tools",
    sdist_name: str = "hydroforge-tools",
    wheel_version: str = "1.0.0",
    sdist_version: str = "1.0.0",
    include_wheel_metadata: bool = True,
    include_sdist_metadata: bool = True,
    include_package: bool = True,
    cli_entry_point: str = "hydroforge.cli:main",
) -> None:
    distribution_dir.mkdir()
    wheel_path = distribution_dir / "hydroforge_tools-1.0.0-py3-none-any.whl"
    with ZipFile(wheel_path, mode="w") as wheel:
        if include_wheel_metadata:
            wheel.writestr(
                "hydroforge_tools-1.0.0.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {wheel_name}\nVersion: {wheel_version}\n",
            )
            wheel.writestr(
                "hydroforge_tools-1.0.0.dist-info/entry_points.txt",
                f"[console_scripts]\nhydroforge = {cli_entry_point}\n",
            )
        if include_package:
            wheel.writestr("hydroforge/__init__.py", "__version__ = '1.0.0'\n")

    sdist_path = distribution_dir / "hydroforge_tools-1.0.0.tar.gz"
    with tarfile.open(sdist_path, mode="w:gz") as sdist:
        if include_sdist_metadata:
            metadata = (
                f"Metadata-Version: 2.1\nName: {sdist_name}\n"
                f"Version: {sdist_version}\n"
            ).encode()
            for member_name in (
                "hydroforge_tools-1.0.0/PKG-INFO",
                "hydroforge_tools-1.0.0/src/hydroforge_tools.egg-info/PKG-INFO",
            ):
                member = tarfile.TarInfo(member_name)
                member.size = len(metadata)
                sdist.addfile(member, BytesIO(metadata))


def test_artifact_checker_accepts_expected_distribution_and_import_names(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir)

    verify_distribution_artifacts(distribution_dir, release_tag="v1.0.0")


@pytest.mark.parametrize(
    ("wheel_name", "sdist_name"),
    [
        ("hydroforge", "hydroforge-tools"),
        ("hydroforge-tools", "hydroforge"),
    ],
)
def test_artifact_checker_rejects_old_distribution_name(
    tmp_path,
    wheel_name,
    sdist_name,
):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(
        distribution_dir,
        wheel_name=wheel_name,
        sdist_name=sdist_name,
    )

    with pytest.raises(AssertionError, match="expected 'hydroforge-tools'"):
        verify_distribution_artifacts(distribution_dir)


def test_artifact_checker_rejects_different_wheel_and_sdist_versions(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir, wheel_version="1.0.1")

    with pytest.raises(AssertionError, match="does not match sdist version"):
        verify_distribution_artifacts(distribution_dir)


def test_artifact_checker_rejects_missing_wheel_metadata(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir, include_wheel_metadata=False)

    with pytest.raises(AssertionError, match="metadata.*wheel"):
        verify_distribution_artifacts(distribution_dir)


def test_artifact_checker_rejects_missing_sdist_metadata(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir, include_sdist_metadata=False)

    with pytest.raises(AssertionError, match="metadata.*sdist"):
        verify_distribution_artifacts(distribution_dir)


def test_artifact_checker_rejects_a_changed_cli_name(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir, cli_entry_point="other.cli:main")

    with pytest.raises(AssertionError, match="`hydroforge` CLI command"):
        verify_distribution_artifacts(distribution_dir)


def test_artifact_checker_rejects_a_missing_import_package(tmp_path):
    distribution_dir = tmp_path / "dist"
    _write_distribution_artifacts(distribution_dir, include_package=False)

    with pytest.raises(AssertionError, match="hydroforge package"):
        verify_distribution_artifacts(distribution_dir)

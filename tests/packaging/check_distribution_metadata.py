"""Validate the built HydroForge distribution artifacts used by CI."""

from __future__ import annotations

import argparse
import configparser
import re
import tarfile
from email.message import Message
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

EXPECTED_DISTRIBUTION_NAME = "hydroforge-tools"
EXPECTED_CLI_ENTRY_POINT = "hydroforge.cli:main"
EXPECTED_DESCRIPTION_CONTENT_TYPE = "text/markdown"
_DIRECT_URL_REQUIREMENT = re.compile(
    r"\s@\s*(?:git\+|hg\+|svn\+|bzr\+|file:|https?://)",
    re.IGNORECASE,
)


def _require_one_path(paths: list[str], description: str) -> str:
    """Return the sole matching path or report an invalid distribution artifact."""
    if len(paths) != 1:
        raise AssertionError(f"Expected exactly one {description}; found {len(paths)}.")
    return paths[0]


def _metadata_from_wheel(wheel_path: Path) -> tuple[Message, set[str]]:
    """Read wheel metadata and member names."""
    with ZipFile(wheel_path) as wheel:
        members = set(wheel.namelist())
        metadata_path = _require_one_path(
            sorted(name for name in members if name.endswith(".dist-info/METADATA")),
            f"metadata file in wheel {wheel_path.name}",
        )
        metadata = BytesParser().parsebytes(wheel.read(metadata_path))
    return metadata, members


def _metadata_from_sdist(sdist_path: Path) -> Message:
    """Read the package metadata from a source distribution."""
    with tarfile.open(sdist_path, mode="r:gz") as sdist:
        metadata_members = sorted(
            (
                member
                for member in sdist.getmembers()
                if (
                    member.isfile()
                    and member.name.count("/") == 1
                    and member.name.endswith("/PKG-INFO")
                )
            ),
            key=lambda member: member.name,
        )
        if len(metadata_members) != 1:
            raise AssertionError(
                f"Expected exactly one top-level metadata file in sdist "
                f"{sdist_path.name}; "
                f"found {len(metadata_members)}."
            )
        metadata_file = sdist.extractfile(metadata_members[0])
        if metadata_file is None:
            raise AssertionError(
                f"Could not read metadata file {metadata_members[0].name}."
            )
        return BytesParser().parsebytes(metadata_file.read())


def _verify_no_direct_url_requirements(metadata: Message, artifact: str) -> None:
    """Reject direct URL requirements that PyPI refuses at upload time."""
    requirements = metadata.get_all("Requires-Dist", [])
    direct_urls = [
        requirement
        for requirement in requirements
        if _DIRECT_URL_REQUIREMENT.search(requirement)
    ]
    if direct_urls:
        raise AssertionError(
            f"{artifact} contains direct URL requirements rejected by PyPI: "
            + ", ".join(direct_urls)
        )


def _verify_markdown_description(metadata: Message, artifact: str) -> None:
    """Ensure PyPI receives a rendered project description."""
    content_type = metadata.get("Description-Content-Type", "")
    if content_type.lower() != EXPECTED_DESCRIPTION_CONTENT_TYPE:
        raise AssertionError(
            f"{artifact} must declare a {EXPECTED_DESCRIPTION_CONTENT_TYPE} "
            "description for PyPI."
        )
    payload = metadata.get_payload()
    if not isinstance(payload, str) or not payload.strip():
        raise AssertionError(f"{artifact} has an empty PyPI description.")


def verify_release_tag(release_tag: str, version: str) -> None:
    """Reject a GitHub release tag that does not match package metadata."""
    expected_tag = f"v{version}"
    if release_tag != expected_tag:
        raise ValueError(
            f"Release tag {release_tag!r} does not match built distribution "
            f"version {version!r}; expected {expected_tag!r}."
        )


def verify_distribution_artifacts(
    distribution_dir: Path,
    *,
    release_tag: str | None = None,
) -> None:
    """Check distribution identity and preserved import/CLI names."""
    wheels = list(distribution_dir.glob("*.whl"))
    sdists = list(distribution_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise AssertionError(
            "Expected exactly one wheel and one sdist in "
            f"{distribution_dir}; found {len(wheels)} wheel(s) and "
            f"{len(sdists)} sdist(s)."
        )

    wheel_metadata, wheel_members = _metadata_from_wheel(wheels[0])
    sdist_metadata = _metadata_from_sdist(sdists[0])
    wheel_version = wheel_metadata["Version"]
    sdist_version = sdist_metadata["Version"]
    if wheel_version != sdist_version:
        raise AssertionError(
            f"Wheel version {wheel_version!r} does not match sdist version "
            f"{sdist_version!r}."
        )

    if release_tag is not None:
        verify_release_tag(release_tag, wheel_version)

    for artifact, metadata in (
        (wheels[0].name, wheel_metadata),
        (sdists[0].name, sdist_metadata),
    ):
        if metadata["Name"] != EXPECTED_DISTRIBUTION_NAME:
            raise AssertionError(
                f"{artifact} identifies the distribution as "
                f"{metadata['Name']!r}, expected {EXPECTED_DISTRIBUTION_NAME!r}."
            )
        _verify_no_direct_url_requirements(metadata, artifact)
        _verify_markdown_description(metadata, artifact)

    if "hydroforge/__init__.py" not in wheel_members:
        raise AssertionError(
            "The wheel must continue to provide the hydroforge package."
        )

    entry_points_paths = sorted(
        name for name in wheel_members if name.endswith(".dist-info/entry_points.txt")
    )
    entry_points_path = _require_one_path(
        entry_points_paths,
        f"console-script entry points in wheel {wheels[0].name}",
    )

    with ZipFile(wheels[0]) as wheel:
        entry_points = configparser.ConfigParser()
        entry_points.read_string(wheel.read(entry_points_path).decode("utf-8"))
    if entry_points.get("console_scripts", "hydroforge", fallback=None) != (
        EXPECTED_CLI_ENTRY_POINT
    ):
        raise AssertionError(
            "The wheel must continue to provide the `hydroforge` CLI command."
        )


def main() -> None:
    """Run the distribution artifact check."""
    parser = argparse.ArgumentParser()
    parser.add_argument("distribution_dir", type=Path)
    parser.add_argument(
        "--release-tag",
        help="GitHub Release tag to verify against the built package version.",
    )
    args = parser.parse_args()
    try:
        verify_distribution_artifacts(
            args.distribution_dir,
            release_tag=args.release_tag,
        )
    except (AssertionError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

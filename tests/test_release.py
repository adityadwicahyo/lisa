import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("release", Path(__file__).parent.parent / "scripts" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("headers, version", [
    (["feat(listener): add a keep answer", "fix(hook): read the reply"], "0.3.0"),
    (["fix(hook): read the reply", "docs(readme): explain the status"], "0.2.1"),
    (["perf(listener): load the model earlier"], "0.2.1"),
    (["docs(readme): explain the status", "chore(ci): run tests on develop", "test(status): cover memory"], None),
    ([], None),
])
def test_next_version_uses_only_the_header_type(headers, version):
    assert release.next_version("0.2.0", headers) == version


def test_changelog_section_lists_features_and_fixes():
    section = release.changelog_section("0.3.0", "2026-09-27", [
        "feat(listener): capitalize the first letter of voice prompts",
        "docs(readme): explain the status",
        "fix(hook): read the reply after a tool call",
    ])
    assert section == ("## [0.3.0] - 2026-09-27\n\n### Added\n- Capitalize the first letter of voice prompts.\n\n"
                       "### Fixed\n- Read the reply after a tool call.\n")


def test_new_section_goes_above_older_ones_with_a_compare_link():
    changelog = ("# Changelog\n\nIntro.\n\n## [0.2.0] - 2026-09-26\n\n### Added\n- Old.\n\n"
                 "[0.2.0]: https://example/compare/v0.1.0...v0.2.0\n")
    updated = release.with_section(changelog, "## [0.3.0] - 2026-09-27\n\n### Added\n- New.\n", "0.3.0", "0.2.0")
    assert updated.index("## [0.3.0]") < updated.index("## [0.2.0]")
    assert updated.index("[0.3.0]: ") < updated.index("[0.2.0]: ")
    assert f"[0.3.0]: {release.REPOSITORY}/compare/v0.2.0...v0.3.0" in updated
    assert release.section_notes(updated, "0.3.0") == "### Added\n- New.\n"


def test_release_notes_come_from_the_real_changelog():
    changelog = (Path(__file__).parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    assert release.section_notes(changelog, "0.2.0").startswith("### Added")

"""Decides and prepares a release after a merge into main (run by .github/workflows/release.yml).

The commit headers since the last v* tag decide the version: any `feat` raises the middle number (0.2.0 -> 0.3.0),
otherwise any `fix` or `perf` raises the last one (0.2.0 -> 0.2.1), and anything else releases nothing. Only headers
count, because this project's commit bodies start with "BREAKING CHANGES:", which standard release tools read as
a major version bump. For a bigger jump (e.g. 1.0.0), set `__version__` yourself: a higher version in the file wins.

Writes the new version to lisa/__init__.py, adds a CHANGELOG.md section (unless you wrote one already), saves the
release notes to release-notes.md and reports `version=<x.y.z>` to GitHub Actions. `--dry-run` only prints.
"""

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "lisa" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
NOTES_FILE = ROOT / "release-notes.md"
REPOSITORY = "https://github.com/adityadwicahyo/lisa"
RELEASE_COMMIT = "chore(release): release "

HEADER = re.compile(r"^(?P<type>\w+)(?:\([^)]*\))?!?: (?P<summary>.+)$")
SECTIONS = {"Added": {"feat"}, "Fixed": {"fix", "perf"}}


def parse(version):
    return tuple(int(part) for part in version.split("."))


def next_version(current, headers):
    """The version the commits call for, or None when they contain no feature or fix.

    :param current: Version of the last release, e.g. "0.2.0"
    :param headers: Commit headers since that release
    """
    major, minor, patch = parse(current)
    types = {match["type"] for header in headers if (match := HEADER.match(header))}
    if "feat" in types:
        return f"{major}.{minor + 1}.0"
    if types & SECTIONS["Fixed"]:
        return f"{major}.{minor}.{patch + 1}"
    return None


def changelog_section(version, date, headers):
    """A CHANGELOG.md section listing the features and fixes, one line per commit header.

    :param version: New version
    :param date: Release date, e.g. "2026-09-27"
    :param headers: Commit headers since the last release
    """
    lines = [f"## [{version}] - {date}"]
    for title, types in SECTIONS.items():
        items = [match["summary"] for header in headers
                 if (match := HEADER.match(header)) and match["type"] in types]
        if items:
            lines += ["", f"### {title}", *[f"- {item[0].upper()}{item[1:]}." for item in items]]
    return "\n".join(lines) + "\n"


def with_section(changelog, section, version, previous):
    """The changelog with the new section above the older ones and a compare link for it.

    :param changelog: Current CHANGELOG.md text
    :param section: New section from `changelog_section`
    :param version: New version
    :param previous: Last released version
    """
    first_section = changelog.index("\n## [") + 1
    changelog = changelog[:first_section] + section + "\n" + changelog[first_section:]
    link = f"[{version}]: {REPOSITORY}/compare/v{previous}...v{version}\n"
    first_link = re.search(r"^\[\d", changelog, re.M)
    return changelog[:first_link.start()] + link + changelog[first_link.start():] if first_link else changelog + link


def section_notes(changelog, version):
    """The body of a version's section, used as the GitHub Release notes."""
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |^\[|\Z)", changelog, re.M | re.S)
    return match.group(1).strip() + "\n" if match else ""


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main():
    dry_run = "--dry-run" in sys.argv
    last_tag = git("describe", "--tags", "--abbrev=0", "--match", "v*")
    previous = last_tag.removeprefix("v")
    headers = [header for header in git("log", f"{last_tag}..HEAD", "--format=%s").splitlines()
               if not header.startswith(RELEASE_COMMIT)]

    version = next_version(previous, headers)
    file_version = re.search(r'__version__ = "([^"]+)"', VERSION_FILE.read_text(encoding="utf-8")).group(1)
    if parse(file_version) > parse(previous) and (version is None or parse(file_version) > parse(version)):
        version = file_version  # Set by hand, e.g. for 1.0.0.
    if version is None:
        print(f"Nothing to release: no feat or fix commits since {last_tag}.")
        return

    changelog = CHANGELOG.read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:  # Otherwise you wrote the notes yourself.
        changelog = with_section(changelog, changelog_section(version, datetime.date.today().isoformat(), headers),
                                 version, previous)
    print(f"Releasing {version} (previous {previous}):\n\n{section_notes(changelog, version)}")
    if dry_run:
        return

    VERSION_FILE.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"',
                                   VERSION_FILE.read_text(encoding="utf-8")), encoding="utf-8")
    CHANGELOG.write_text(changelog, encoding="utf-8")
    NOTES_FILE.write_text(section_notes(changelog, version), encoding="utf-8")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"version={version}\n")


if __name__ == "__main__":
    main()

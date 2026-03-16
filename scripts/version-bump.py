#!/usr/bin/env python3
"""
version-bump.py — per-project semantic versioning for kibase monorepo.

Reads git history since the last tag for each project, parses commit messages
for change(<project>): (minor bump) or redesign(<project>): (major bump),
increments the version, updates CHANGELOG.md, writes VERSION file, and
creates an annotated git tag.

Usage:
  python3 scripts/version-bump.py <project-name> [<project-name> ...]
  python3 scripts/version-bump.py --all       # auto-detect all projects/

Commit message format:
  change(board-a): add decoupling caps to 3V3 rail      → minor bump
  redesign(board-a): switch from STM32F4 to RP2040      → major bump
  fix: typo in README                                   → no bump
  chore(board-a): update CI image                       → no bump

Tags:
  <project>/v<major>.<minor>.<patch>   e.g. example/v1.2.0

Exit codes:
  0  — at least one project was bumped (or --dry-run completed)
  1  — no projects had version-bump commits
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def run(cmd: list[str], check: bool = True, capture: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def git(*args, check: bool = True) -> str:
    return run(["git", *args], check=check)


def last_tag_for(project: str) -> str | None:
    """Return the most recent tag matching <project>/v*, or None."""
    tags = git("tag", "--list", f"{project}/v*", "--sort=-version:refname", check=False)
    lines = [t.strip() for t in tags.splitlines() if t.strip()]
    return lines[0] if lines else None


def parse_version(tag: str) -> tuple[int, int, int]:
    """Parse 'project/v1.2.3' or 'v1.2.3' into (major, minor, patch)."""
    m = re.search(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        raise ValueError(f"Cannot parse version from tag: {tag}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def commits_since(ref: str, project: str) -> list[dict]:
    """Return commits touching projects/<project>/ since <ref>."""
    log_range = f"{ref}..HEAD" if ref else "HEAD"
    raw = git(
        "log", log_range,
        "--pretty=format:%H%x00%s%x00%b%x00",
        "--", f"projects/{project}/",
        check=False,
    )
    commits = []
    for entry in raw.split("\x00\x00\x00"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x00", 2)
        sha = parts[0].strip()
        subject = parts[1].strip() if len(parts) > 1 else ""
        body = parts[2].strip() if len(parts) > 2 else ""
        if sha:
            commits.append({"sha": sha, "subject": subject, "body": body})
    return commits


def classify_commits(commits: list[dict], project: str) -> tuple[str | None, list[str]]:
    """
    Return (bump_type, messages).
    bump_type: 'major' | 'minor' | None
    messages: list of relevant commit subjects for the changelog
    """
    bump = None
    messages = []
    for c in commits:
        subject = c["subject"]
        if re.match(rf"^redesign\({re.escape(project)}\)\s*:", subject, re.IGNORECASE):
            bump = "major"
            messages.append(subject)
        elif re.match(rf"^change\({re.escape(project)}\)\s*:", subject, re.IGNORECASE):
            if bump != "major":
                bump = "minor"
            messages.append(subject)
    return bump, messages


def bump_version(major: int, minor: int, patch: int, bump: str) -> tuple[int, int, int]:
    if bump == "major":
        return major + 1, 0, 0
    if bump == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def update_changelog(project: str, version: str, messages: list[str], dry_run: bool) -> None:
    changelog_path = Path(f"projects/{project}/CHANGELOG.md")
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    section = f"## [{version}] — {today}\n\n"
    for msg in messages:
        section += f"- {msg}\n"
    section += "\n"

    if changelog_path.exists():
        content = changelog_path.read_text()
    else:
        content = f"# Changelog — {project}\n\n## [Unreleased]\n"

    # Insert after the first line (title) or after ## [Unreleased]
    unreleased_marker = "## [Unreleased]"
    if unreleased_marker in content:
        content = content.replace(unreleased_marker, f"{unreleased_marker}\n\n{section}", 1)
    else:
        # Prepend after the first heading
        lines = content.splitlines(keepends=True)
        insert_at = 1
        for i, line in enumerate(lines):
            if line.startswith("## "):
                insert_at = i
                break
        lines.insert(insert_at, section)
        content = "".join(lines)

    if not dry_run:
        changelog_path.write_text(content)
        print(f"  Updated {changelog_path}")
    else:
        print(f"  [dry-run] Would update {changelog_path}")


def write_version_file(project: str, version: str, dry_run: bool) -> None:
    version_path = Path(f"projects/{project}/VERSION")
    if not dry_run:
        version_path.write_text(version + "\n")
        print(f"  Wrote {version_path}")
    else:
        print(f"  [dry-run] Would write {version_path} = {version}")


def create_tag(project: str, version: str, messages: list[str], dry_run: bool) -> None:
    tag = f"{project}/v{version}"
    annotation = f"Release {project} v{version}\n\n" + "\n".join(f"- {m}" for m in messages)
    if not dry_run:
        git("tag", "-a", tag, "-m", annotation)
        print(f"  Created tag: {tag}")
    else:
        print(f"  [dry-run] Would create tag: {tag}")


# ── main ─────────────────────────────────────────────────────────────────────

def process_project(project: str, dry_run: bool) -> bool:
    """Return True if a version bump occurred."""
    print(f"\n── {project} ──")

    last_tag = last_tag_for(project)
    if last_tag:
        print(f"  Last tag  : {last_tag}")
        major, minor, patch = parse_version(last_tag)
    else:
        print("  No previous tag — starting at v0.1.0")
        major, minor, patch = 0, 0, 0

    commits = commits_since(last_tag, project)
    print(f"  Commits   : {len(commits)} touching projects/{project}/ since last tag")

    bump, messages = classify_commits(commits, project)
    if not bump:
        print("  No change/redesign commits — skipping.")
        return False

    new_major, new_minor, new_patch = bump_version(major, minor, patch, bump)
    new_version = f"{new_major}.{new_minor}.{new_patch}"
    print(f"  Bump type : {bump}")
    print(f"  New version: v{new_version}")
    print(f"  Commits included:")
    for m in messages:
        print(f"    • {m}")

    update_changelog(project, new_version, messages, dry_run)
    write_version_file(project, new_version, dry_run)
    create_tag(project, new_version, messages, dry_run)
    return True


def discover_projects() -> list[str]:
    projects_dir = Path("projects")
    if not projects_dir.exists():
        return []
    return [
        p.name for p in sorted(projects_dir.iterdir())
        if p.is_dir() and any(p.glob("*.kicad_pro"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projects", nargs="*", metavar="PROJECT", help="Project name(s) under projects/")
    parser.add_argument("--all", action="store_true", help="Process all projects/ subdirectories")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without making changes")
    args = parser.parse_args()

    if args.all:
        projects = discover_projects()
        if not projects:
            print("No projects found under projects/", file=sys.stderr)
            sys.exit(1)
        print(f"Discovered projects: {', '.join(projects)}")
    elif args.projects:
        projects = args.projects
    else:
        parser.print_help()
        sys.exit(1)

    # Must run from repo root
    repo_root = run(["git", "rev-parse", "--show-toplevel"])
    os.chdir(repo_root)

    bumped_any = False
    for project in projects:
        if not Path(f"projects/{project}").is_dir():
            print(f"Warning: projects/{project} not found — skipping.", file=sys.stderr)
            continue
        bumped = process_project(project, dry_run=args.dry_run)
        if bumped:
            bumped_any = True

    if not bumped_any:
        print("\nNo projects bumped.")
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()

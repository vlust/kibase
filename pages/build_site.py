#!/usr/bin/env python3
"""Build a static GitLab Pages site from kibase project outputs.

Usage:
    python3 pages/build_site.py [--projects-dir DIR] [--out-dir DIR]

Defaults:
    --projects-dir  $KIBASE_PROJECTS_DIR or "projects"
    --out-dir       public

Templates are loaded from pages/templates/ and use {{placeholder}} syntax.
"""

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


def load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text()


def render(template: str, **kwargs: str) -> str:
    """Replace {{key}} placeholders in template with values."""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ICON_MAP = {
    ".pdf": "&#x1F4C4;",
    ".zip": "&#x1F4E6;",
    ".csv": "&#x1F4CA;",
    ".html": "&#x1F310;",
    ".png": "&#x1F5BC;",
    ".jpg": "&#x1F5BC;",
    ".jpeg": "&#x1F5BC;",
    ".svg": "&#x1F5BC;",
    ".rpt": "&#x1F4CB;",
}

TAG_RULES = [
    ("schematic", "schematic"),
    ("layout", "layout"),
    ("bom", "BOM"),
    ("fab", "fabrication"),
    ("gerber", "fabrication"),
    ("erc", "report"),
    ("drc", "report"),
]


def human_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def icon_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ICON_MAP.get(ext, "&#x1F4CE;")


def tag_for(filename: str) -> str:
    lower = filename.lower()
    for pattern, label in TAG_RULES:
        if pattern in lower:
            return f'<span class="tag">{label}</span>'
    return ""


def discover_projects(projects_dir: str) -> list[str]:
    """Return sorted list of project names (or ['.'] for single-project repos)."""
    if projects_dir == ".":
        return ["."]
    base = Path(projects_dir)
    if not base.is_dir():
        return []
    return sorted(d.name for d in base.iterdir() if d.is_dir())


def collect_project(project_root: Path, dest: Path) -> None:
    """Copy outputs and docs into dest, creating it if needed."""
    dest.mkdir(parents=True, exist_ok=True)

    review_dir = project_root / "output" / "review"
    if review_dir.is_dir():
        shutil.copytree(review_dir, dest, dirs_exist_ok=True)

    docs_dir = project_root / "docs"
    if docs_dir.is_dir():
        shutil.copytree(docs_dir, dest, dirs_exist_ok=True)


def list_files(dest: Path) -> list[Path]:
    """List all non-template files under dest."""
    skip = {"index.html", "style.css"}
    return sorted(
        f for f in dest.rglob("*") if f.is_file() and f.name not in skip
    )


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------


def build_project_page(slug: str, version: str, dest: Path) -> None:
    """Generate index.html for a single project."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    files = list_files(dest)

    file_entry_tpl = load_template("file_entry.html")
    entries = ""
    for f in files:
        rel = f.relative_to(dest)
        entries += render(
            file_entry_tpl,
            rel=str(rel),
            icon=icon_for(f.name),
            filename=f.name,
            tag=tag_for(f.name),
            size=human_size(f),
        )

    project_tpl = load_template("project.html")
    html = render(
        project_tpl,
        slug=slug,
        version=version,
        timestamp=timestamp,
        files=entries,
    )
    (dest / "index.html").write_text(html)


def build_root_page(out_dir: Path, projects: list[dict]) -> None:
    """Generate the root index.html."""
    card_tpl = load_template("card.html")
    cards = ""
    for p in projects:
        cards += render(card_tpl, **p)

    index_tpl = load_template("index.html")
    html = render(index_tpl, cards=cards)
    (out_dir / "index.html").write_text(html)


def copy_stylesheet(out_dir: Path) -> None:
    """Copy style.css into the output directory."""
    src = TEMPLATES_DIR / "style.css"
    if src.exists():
        shutil.copy2(src, out_dir / "style.css")
    else:
        print("Warning: pages/templates/style.css not found")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kibase Pages site")
    parser.add_argument(
        "--projects-dir",
        default=os.environ.get("KIBASE_PROJECTS_DIR", "projects"),
    )
    parser.add_argument("--out-dir", default="public")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    projects_dir = args.projects_dir
    names = discover_projects(projects_dir)
    if not names:
        print("No projects found.")
        return

    print(f"Building site for projects: {', '.join(names)}")

    copy_stylesheet(out_dir)

    project_cards = []
    for name in names:
        if projects_dir == ".":
            project_root = Path(".")
            slug = "main"
        else:
            project_root = Path(projects_dir) / name
            slug = name

        dest = out_dir / slug
        collect_project(project_root, dest)

        version_file = project_root / "VERSION"
        version = version_file.read_text().strip() if version_file.exists() else "-"

        build_project_page(slug, version, dest)

        file_count = len(list_files(dest))
        project_cards.append(
            {"slug": slug, "version": version, "file_count": str(file_count)}
        )
        print(f"  {slug}: {file_count} files")

    build_root_page(out_dir, project_cards)
    print(f"Site built in {out_dir}/")


if __name__ == "__main__":
    main()

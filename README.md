# kibase

A GitLab-hosted monorepo template for managing KiCad PCB projects with
automated asset generation, per-project semantic versioning, and a structured
Draft → Review → Released workflow.

---

## Quickstart

### Add a new project

```bash
# 1. Create the project directory
mkdir -p projects/my-board

# 2. Open KiCad and create a new project inside projects/my-board/kicad/
#    Name the .kicad_pro file to match the board: my-board.kicad_pro

# 3. Set text variables in the .kicad_pro file:
#    REVISION, PROJECT_NAME, COMPANY

# 4. Add a CHANGELOG.md
cp projects/example/CHANGELOG.md projects/my-board/CHANGELOG.md
sed -i 's/example/my-board/g' projects/my-board/CHANGELOG.md

# 5. Generate locally to verify
./scripts/generate.sh projects/my-board draft
```

### Generate outputs locally

```bash
# Draft: schematic PDF only (fast, for WIP sharing)
./scripts/generate.sh projects/example draft

# Review: schematic + layout PDFs, ERC/DRC reports, interactive BOM
./scripts/generate.sh projects/example review

# Release: all of the above + gerbers, drill, JLCPCB BOM + CPL
./scripts/generate.sh projects/example release
```

Outputs appear in `projects/example/output/`. This directory is git-ignored.

---

## Directory structure

```
kibase/
├── projects/
│   └── example/
│       ├── kicad/                   # KiCad project files
│       │   ├── example.kicad_pro    # Text variables: REVISION, PROJECT_NAME, COMPANY
│       │   ├── example.kicad_sch
│       │   └── example.kicad_pcb
│       ├── docs/                    # Optional static docs (copied to Pages site)
│       ├── design/                  # Design documents (requirements, block diagrams, notes)
│       ├── datasheets/              # Component datasheets
│       ├── simulation/              # SPICE / LTspice simulation files
│       ├── mechanical/              # Mechanical drawings, DXF, enclosure files
│       ├── CHANGELOG.md             # Per-project changelog (auto-managed)
│       └── VERSION                  # Current version string (auto-managed by CI)
├── libraries/                       # Git submodule — shared KiCad symbol/footprint libraries
├── kibot/
│   ├── globals.yaml                 # Shared global settings and JLCPCB format config
│   ├── filters.yaml                 # DNP exclusion, testpoint exclusion, LCSC field rename
│   ├── draft.yaml                   # Draft stage: schematic PDF only
│   ├── review.yaml                  # Review stage: PDFs + ERC/DRC + iBOM + KiRI diff
│   └── release.yaml                 # Released stage: review + gerbers + BOM + CPL + zip
├── pages/
│   ├── build_site.py                # Generates the GitLab Pages static site
│   └── templates/
│       ├── style.css                # Shared stylesheet for all pages
│       ├── index.html               # Root page template (project cards)
│       ├── card.html                # Single project card fragment
│       ├── project.html             # Per-project page template (file list)
│       └── file_entry.html          # Single file row fragment
├── scripts/
│   ├── generate.sh                  # Local Docker-based generation
│   ├── detect-changed-projects.sh   # CI helper: list changed projects
│   ├── build-asset-links.py         # CI helper: build release asset link JSON
│   └── version-bump.py              # Per-project semver bump + changelog + tag
├── .gitlab-ci.yml
├── .gitmodules
├── .gitignore
└── README.md
```

### Single-project repos

To use kibase for a single board (no `projects/` subdirectory), set
`KIBASE_PROJECTS_DIR=.` in your CI variables and structure the repo like:

```
my-board-repo/
├── kicad/
│   ├── my-board.kicad_pro
│   ├── my-board.kicad_sch
│   └── my-board.kicad_pcb
├── docs/
├── design/
├── datasheets/
├── simulation/
├── mechanical/
├── CHANGELOG.md
└── VERSION
```

Commit prefixes work the same way. Bare form is also accepted in single-project mode:
```
change: add bulk decoupling caps     ← minor bump (no project name needed)
redesign: reroute power tree         ← major bump
```

---

## Workflow

```
   feature branch                        main
        │                                  │
        │  push / update                   │
        ▼                                  │
   [validate]                             │
   ERC + DRC on changed projects          │
        │                                  │
        ▼                                  │
   [review:generate]                      │
   Review PDFs + KiRI diff artifacts      │
        │                                  │
        │  Merge MR                        │
        └──────────────────────────────────▶
                                           │
                                      [review:generate]
                                      Review PDFs generated
                                           │
                                      [release]
                                      Version bumped (if change/redesign commits)
                                      Fab files uploaded to package registry
                                      GitLab release created
                                           │
                                      [pages]
                                      Static docs site published to GitLab Pages
```

---

## Commit message conventions

Version bumps are triggered by commit messages with specific prefixes
**on the main branch only**. Using these prefixes on a feature branch
has no effect — they are evaluated by `version-bump.py` during the
`release` CI stage, which only runs after merging to main.

The project name in parentheses must match the directory name under `projects/`.

| Prefix | Effect (on main) |
|---|---|
| `change(my-board): description` | Minor version bump (`0.1.0` → `0.2.0`) |
| `redesign(my-board): description` | Major version bump (`0.1.0` → `1.0.0`) |
| anything else | No version bump |

Examples:

```
change(my-board): add bulk decoupling to 3V3 rail
change(my-board): route USB differential pair as diff pair
redesign(my-board): replace STM32F4 with RP2040
chore: update CI image version              ← no bump, ever
docs: fix README typo                       ← no bump, ever
fix: correct schematic net label            ← no bump, ever
```

On a feature branch you can use any commit message style you like — only
the commits that land on main (after merge) are scanned for bump prefixes.

---

## Design stages

| Stage | When to use | What's generated |
|---|---|---|
| **Draft** | WIP, internal sharing | Schematic PDF |
| **Review** | MR, design review | Schematic PDF, layout PDF, ERC/DRC reports, interactive BOM, KiRI diff |
| **Released** | Merged to main, fab-ready | All review outputs + gerbers, drill, JLCPCB BOM CSV, CPL CSV, fab ZIP |

---

## JLCPCB workflow

### Component LCSC numbers

Add an `LCSC` field to each component in KiCad with the JLCPCB part number
(e.g. `C1525`). This field is:

- Shown in the interactive BOM for easy cross-reference
- Exported as `LCSC Part #` in the JLCPCB BOM CSV
- Used by the CPL file generation

### Rotation corrections

KiBot applies JLCPCB rotation offsets automatically via the `_rot_footprint`
transform in `release.yaml`. If you find rotation issues with a specific
footprint, you can add an override — see the
[KiBot rotation database](https://github.com/INTI-CERN/KiBot/blob/master/kibot/resources/rotation_db.yaml).

### Board stackup

The default stackup is 2-layer, 1.6mm FR4. To specify a different stackup,
edit `Board Setup → Board Stackup` in KiCad PCB editor. KiBot will read
it automatically.

---

## Libraries (submodule)

The `libraries/` directory is a git submodule pointing to a shared KiCad
symbol and footprint library repository.

```bash
# Initialize the submodule after cloning
git submodule update --init --recursive

# Update to the latest library version
git submodule update --remote libraries
git add libraries
git commit -m "chore: update shared libraries"
```

To point to your own library repo, edit `.gitmodules`:

```ini
[submodule "libraries"]
    path = libraries
    url = https://gitlab.com/your-org/kicad-libraries.git
```

---

## KiRI visual diff

KiRI generates an interactive HTML diff showing schematic and PCB changes
between commits. On merge requests:

- A `KiRI Diff` artifact link appears in the pipeline tab (always available)
- If `GITLAB_BOT_TOKEN` is configured, KiRI output is also hosted on
  GitLab Pages and linked in an MR comment

### Setup (optional, for Pages hosting)

1. Create a project access token with `write_repository` + `api` scopes
2. Add it as a CI variable named `GITLAB_BOT_TOKEN`
3. Enable GitLab Pages for the project

---

## GitLab Pages

On every push to main, the `pages` job builds a static documentation site
and publishes it to GitLab Pages. The site includes:

- A root index page with a card per project
- Per-project pages listing all review outputs (PDFs, reports, images)
  and anything in the project's `docs/` directory

### Customizing the site

Templates live in `pages/templates/` and use `{{placeholder}}` syntax.
Edit them directly — no build tooling or dependencies required.

| File | Purpose |
|---|---|
| `style.css` | Shared stylesheet for all pages |
| `index.html` | Root page layout (renders `{{cards}}`) |
| `card.html` | Project card fragment (`{{slug}}`, `{{version}}`, `{{file_count}}`) |
| `project.html` | Per-project page layout (`{{slug}}`, `{{version}}`, `{{timestamp}}`, `{{files}}`) |
| `file_entry.html` | File list row (`{{rel}}`, `{{icon}}`, `{{filename}}`, `{{tag}}`, `{{size}}`) |

To test locally:

```bash
python3 pages/build_site.py --projects-dir projects --out-dir public
# open public/index.html in a browser
```

### Release artifacts

Release artifacts (fab ZIP, schematic PDF, layout PDF) are uploaded to the
GitLab Generic Package Registry and linked from the GitLab Release page —
they are no longer committed into the repository.

---

## CI/CD setup

### Required CI variables

| Variable | Description |
|---|---|
| `GITLAB_BOT_TOKEN` | Project access token (write_repository + api). Optional but needed for releases, package registry uploads, and KiRI Pages. |

### Pipeline image

The pipeline uses `ghcr.io/inti-cern/kibot:dev`. Pin to a specific digest
in `.gitlab-ci.yml` for reproducible builds.

### MR cleanup webhook

To automatically remove KiRI Pages content when an MR is closed/merged,
set up a GitLab webhook that triggers the `kiri:cleanup` job with the
`CLEANUP_MR_IID` variable set to the MR IID.

---

## Reference projects

The `KDT_Hierarchical_KiBot/` and `kicad-ci-cd-pipeline/` directories contain
the reference projects this template was derived from. They are not part of the
template — you can delete them once you have adapted the configuration to your
needs.

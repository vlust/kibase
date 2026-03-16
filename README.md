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

# 2. Open KiCad and create a new project inside projects/my-board/
#    Name the .kicad_pro file to match the directory: my-board.kicad_pro

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
│       ├── example.kicad_pro        # KiCad project (text variables: REVISION, PROJECT_NAME, COMPANY)
│       ├── example.kicad_sch        # Schematic
│       ├── example.kicad_pcb        # Layout
│       ├── docs/                    # Committed PDFs (auto-updated by CI on main)
│       │   ├── schematic.pdf
│       │   └── layout.pdf
│       ├── CHANGELOG.md             # Per-project changelog (auto-managed)
│       └── VERSION                  # Current version string (auto-managed by CI)
├── libraries/                       # Git submodule — shared KiCad symbol/footprint libraries
├── kibot/
│   ├── globals.yaml                 # Shared global settings and JLCPCB format config
│   ├── filters.yaml                 # DNP exclusion, testpoint exclusion, LCSC field rename
│   ├── draft.yaml                   # Draft stage: schematic PDF only
│   ├── review.yaml                  # Review stage: PDFs + ERC/DRC + iBOM + KiRI diff
│   └── release.yaml                 # Released stage: review + gerbers + BOM + CPL + zip
├── scripts/
│   ├── generate.sh                  # Local Docker-based generation
│   ├── detect-changed-projects.sh   # CI helper: list changed projects
│   └── version-bump.py              # Per-project semver bump + changelog + tag
├── .gitlab-ci.yml
├── .gitmodules
├── .gitignore
└── README.md
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
                                      [review:commit-docs]
                                      PDFs committed to docs/
                                           │
                                      [release]
                                      Version bumped (if change/redesign commits)
                                      Fab files generated
                                      GitLab release created
```

---

## Commit message conventions

Version bumps are triggered by commit messages with specific prefixes.
The project name in parentheses must match the directory name under `projects/`.

| Prefix | Effect |
|---|---|
| `change(my-board): description` | Minor version bump (`0.1.0` → `0.2.0`) |
| `redesign(my-board): description` | Major version bump (`0.1.0` → `1.0.0`) |
| anything else | No version bump |

Examples:

```
change(my-board): add bulk decoupling to 3V3 rail
change(my-board): route USB differential pair as diff pair
redesign(my-board): replace STM32F4 with RP2040
chore: update CI image version              ← no bump
docs: fix README typo                       ← no bump
fix: correct schematic net label            ← no bump
```

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

## CI/CD setup

### Required CI variables

| Variable | Description |
|---|---|
| `GITLAB_BOT_TOKEN` | Project access token (write_repository + api). Optional but needed for doc commits, releases, and KiRI Pages. |

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

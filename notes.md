# kibase

a setup for kicad projects with nice automated and collaberative workflows

## my prios

- use gitlab
- clear branch and MR workflow
  - when a change on a design is requested work on the mr branch, reviews are then done, can be assisted with diff tools
  - merging means automated version bump, changelog from ggt history of that projects main branch commits, aka merge commits
  - multiple stages of the design for different outputs like in one of the examples, having draft prelimenary etc
- would be nice if automated output can be generated both locally and in a pipeline
- support multiple projects in one repo
- works nicely with jlcpcb, aka rotation offsets and lcsc part numbers
- asset generation
  - most importantly are production file generations
  - pdfs for layout and schematic to easily review them
  - diff viewer
  - bom and positions
  - changelog
- how are custom libraries handled?
# Whole-project review and corrections

**17 October 2026. Correction release: v2.0.1. Reviewed baseline: v2.0.0,
commit `68bf839e94e4789f8fa994473618cb1bb31eb8d5`.**

This review checks the delivered project against Pratham's original brief and
corrects specific defects. It is a bounded engineering review, not a guarantee
that every possible error has been excluded. Video and website revision remain
parked, as requested.

## The original goal remains the project

Project SCCI RH gives an ambitious invasive spinal cord-computer interface a
defensible mechanism, illustrated research account, electronic architecture,
compiled software and physical identity in editable CAD. AstroSam's Mind-Link
inspired that progression from future vision to inspectable engineering.
SCCI_RH's contribution is its own spinal architecture, application arguments,
models and implementation, with substantial AI assistance disclosed.

Both application ambitions remain central. Expert performance informs a
task-conditioned reference; learner calibration determines a reachable
intervention during practice. Later stimulation-OFF evaluation distinguishes
retained learning from temporary assistance. Physiological feedback selects a
specific function and accessible pathway; the worked pressure example uses an
external sensor, positive pressor authority and bounded stimulation requests.
Neither skill downloading nor universal body automation is assumed.

The future consumer mechanism is recording and calibration, interpretation of
relevant state, selection of a learner- or function-specific programme, guarded
stimulation, observation of response, and feedback to the next decision. The
completed digital reference demonstrates selected software/model parts of that
mechanism. Useful chronic recording, selective recruitment and favorable retained
learning remain explicit, testable premises. Those premises can be explored
without falsely claiming they have already been demonstrated by SCCI_RH.

## Concrete corrections

| Finding | Correction | Evidence |
|---|---|---|
| UART callback could insert normal telemetry inside a partially sent raw frame | Current application owns the chosen queue until the entire frame has been transmitted; priority changes only between frames | [Corrected application, regression and rebuilt image](../../firmware/nrf5340/uart-revision/README.md) |
| R17 repeated one author in full and abbreviated metadata | Removed the duplicate, checked the publisher roster, rebuilt and visually reviewed the manuscript | [Scientific review](science-review.md) |
| Most historical CAD launchers depended on this laptop's executable location | New current launcher resolves an explicit setting, PATH or installed FreeCAD and opens the existing native files | [Portable CAD entry](../../cad/CURRENT_CAD.md), [mechanical review](mechanics-review.md) |
| Current release entries retained private-repository wording and superseded directions | Updated current entries for public visibility, the corrected application, portable CAD and v2.0.1 reproduction | [Current status](../../CURRENT_STATUS.md), [release plan](../stage6/release-plan.md) |
| Generated HEX/map/configuration/device-tree text had raw Windows line-ending hashes in the new release receipt | Use explicit LF-normalized text hashes, consistent with Git and the independent firmware audit; ELF/BIN bytes remain exact | [Current release verifier](../../scripts/verify_stage6_release.py) |

## Review coverage and retained evidence

- [Science and goal alignment](science-review.md): original paper, both mechanisms,
  assumptions, citations, learning equations and displayed numerical results.
- [Electronics and firmware](electronics-review.md): code inspection, actual
  callback regression, target linkage, current native ERC/DRC and declared limits.
- [Mechanical CAD and usability](mechanics-review.md): native source inspection,
  physical-object validity, package boundaries and portable opening.
- [Release verification](../../provenance/stage6-release-verification.json): exact
  current manuscript/source bindings and all 2,733 protected Stage 1-5 files.

The original production core, eight board designs, mechanical solids, studies
and receipts remain unchanged. The UART application revision is additive and
uses the same reviewed core, main application, pins and carrier configuration.
The old image and buggy callback remain a clearly identified historical
checkpoint used by the regression test; they are not the current recommended
application. The v2.0.0 tag is never moved or overwritten.

The integrated replay still reports 114,426 finite software assertions, 5,184
modeled motor events and 1,200 pressure events. Existing conservative negative
results and neutral/adverse teaching alternatives are preserved. Native fit,
rule checks, target linkage and host tests retain their distinct meanings.

The full existing Python suite also ran in this review: **224 tests passed**.
Fresh production-core execution passed 713 assertions across 75 scenarios.
All eight saved boards and the 80-sheet master received fresh native KiCad
DRC/ERC checks. The full and future FreeCAD assemblies were reopened and their
physical shapes inspected. These current operations supplement, rather than
rename, the retained portable checkpoints.

The repository became public at the owner's request on 17 October. Existing
all-rights-reserved and third-party terms remain in force; public visibility is
not a new license grant. Old checkpoint wording is retained for provenance and
is superseded by these current entries.

## Accepted future dependencies

No new defect was found in the project's separation of the large, real eight-board
reference from its proposed compact implanted package. Miniaturization, energy,
thermal closure, anatomical fit and chronic interfaces require later engineering.
The current target records in OBSERVE and inhibits recording while armed; it has
no radio image or implemented live spinal decoder during MOTOR. The UART fix
does not change those boundaries.

The paper does not establish healthy expert-to-novice transfer, a human learning
multiplier, universal physiological control, or physical/biological execution.
These are documented research conditions, not reasons to keep the completed
digital concept indefinitely unfinished.

## Reproduce the current release

Use a full clone at `v2.0.1`, pinned Python dependencies and a C11 compiler:

```text
python scripts/verify_manifest.py
python scripts/verify_stage6_release.py
python scripts/stage6/verify_digital_path.py
python firmware/nrf5340/uart-revision/verify_revision.py
python scripts/verify_integrated_pcb.py
python scripts/verify_stage5_mechanics.py
```

The release's GitHub workflow conclusions, tag/branch identities, exact archive
members and asset digests are verified after publication. Those external checks
cannot be truthfully embedded as completed outcomes in the commit they identify.

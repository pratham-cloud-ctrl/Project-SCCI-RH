# Project SCCI RH integrated digital release plan

**Release target: v2.1.0, 28 October 2026.** This is the full-system digital
research and engineering release. The existing `v1.0.0` remains a historical
single-channel desktop subsystem and is not silently replaced or retagged.

## What this release completes

The release joins the proposed spinal recording, interpretation, individualized
stimulation, independent delivery monitoring and bodily feedback mechanism to
two application arguments, reproducible studies, native circuits, target-linked
firmware and editable mechanical assemblies. It includes an integrated
illustrated manuscript and an inspectable public repository. AstroSam's
[Mind-Link](https://github.com/sam-astro/Mind-link) inspired the progression from
future concept to tangible engineering; its source and geometry are not copied
into SCCI_RH.

Completion is the stated **digital research and engineering scope**. Useful
chronic spinal recording, selective biological recruitment, retained consumer
learning benefit, implant miniaturization and physical qualification remain
explicit assumptions or future evidence requirements. A release can be complete
while those scientific questions remain open.

## Current and historical entry points

| Purpose | Authoritative entry |
|---|---|
| Integrated account | [Final manuscript](../../output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) and its editable source under `manuscript/stage6/` |
| Current project navigation | [Root README](../../README.md) and [current status](../../CURRENT_STATUS.md) |
| Both conditional consumer mechanisms | [Conditional concept](../stage3/conditional-concept.md) and its [assumption ledger](../stage3/conditional-concept/assumption-ledger.csv) |
| Preserved conservative conclusion | [Historical qualification verdict](../stage3/stage3-verdict.md) |
| Current electrical engineering | [Eight-board index](../../electronics/stage4/integrated-pcb/BOARD_INDEX.md) and [Stage 4 exit review](../stage4/exit-review.md) |
| Current mechanical engineering | [Stage 5 CAD index](../../cad/stage5/README.md), [drawing sheets](../../cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf) and [exit review](../stage5/exit-review.md) |
| Ownership and defence | [Contributions](contributions.md) and [defence guide](defence-guide.md) |
| Historical v1 material | [v1 release notes](../release-notes.md), [v1 learning guide](../learning-guide.md), `docs/scci_rh-paper.md`, `output/pdf/SCCI_RH_engineering_paper.pdf`, `site/` and `media/` |

Older stage documents are dated development snapshots. Statements such as
"CAD remains unfinished" in an early handoff describe that checkpoint; the
current status and final exit reviews supersede them. Prior data, code,
receipts, adverse results, website and video are retained for provenance. Website
and video revision are outside this release task.

## Finite release checks

1. Verify the Stage 6 manuscript, figure inputs, references, release contract and
   documented limitations. Render the final PDF and inspect every page for
   readable tables, equations, captions, source attribution and unclipped layout.
   Text extraction alone does not establish visual quality.
2. Run the Stage 6 release verifier. It checks current required artifacts,
   current local entry links, the PDF's structure, bound source/evidence hashes,
   release version and preservation of the completed Stage 1–5 source/evidence
   paths against commit `7360158`.
3. Replay the existing portable populated-PCB and mechanical checkpoints.
   Those checks bind earlier application-backed native inspection to exact saved
   source and exchange bytes. They do not emulate FreeCAD/KiCad or establish
   physical performance. Retain the historical study reproduction workflow and
   report its actual conclusion rather than inferring success from a new audit.
4. Stage the final intended files, refresh the committed Git-blob manifest,
   verify it against the index, and check the staged diff. The manifest excludes
   itself. Do not put an archive inside its own source tree or include a
   receipt's own hash in the receipt.
5. Commit and push the review working branch, update its draft review,
   then independently fetch/check out the exact pushed commit. Run the manifest,
   Stage 6 and preserved electrical/mechanical checks from that clean copy.
   Verify remote branch identity and GitHub workflow conclusions.
6. Create the new `v2.1.0` tag at the reviewed commit and a public GitHub digital
   engineering release. Upload the manuscript, mechanical drawing set, a full
   source archive, and an external SHA-256 checksum list. Verify that the remote
   tag resolves to the intended commit and that downloaded asset bytes or GitHub
   asset digests match the local artifacts. Never claim these steps happened
   before their actual results are available.

No new neuroscience qualification programme, fabrication or clinical trial is
a prerequisite for this digital release. A newly discovered broken artifact,
source mismatch or false claim is a release defect and must be corrected.

## Artifact and checksum policy

The full source archive is generated from the release commit into an ignored
build/output directory. It contains the Git-tracked project, including historical
studies and editable native files. It excludes credentials, installed applications,
virtual environments, temporary files and ignored raw STEP extractions. The two
large populated reference STEP files are retained as deterministic lossless ZIPs;
their supplied extraction tool verifies the original uncompressed hashes.
Use a full Git clone at the release tag to run history/source-preservation and
Git-blob checks; the convenient source ZIP does not contain the `.git` history.

The external checksum list covers the uploaded source archive and reader-facing
PDFs. It does not hash itself. The tracked manifest identifies committed Git blobs,
so Windows line-ending normalization does not cause a false mismatch. The release
tag identifies the commit; embedding the eventual commit hash into a file that
helps determine that same commit is deliberately avoided.

GitHub currently blocks ordinary tracked files larger than 100 MiB; this is why
the full populated STEP files travel in lossless archives. This packaging policy
follows [GitHub's file-size guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github),
checked on 16 October 2026.

## After release

Pratham's next work is to learn, reproduce, explain and revise selected parts of
the project using the defence guide. Any later physical prototype, new biological
evidence, miniaturized board or thermal/field study becomes a separately scoped
revision. Release of the digital project does not imply that Pratham has already
personally completed that learning or obtained independent expert review.

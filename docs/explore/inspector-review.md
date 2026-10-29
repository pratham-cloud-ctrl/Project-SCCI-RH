# Browser inspector review · 21 October 2026

[Open the build inspector](https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/) · [Explore the project](README.md) · [Tool choices and critique](../../inspector/credits.html)

The inspector combines browser inspection with standard STEP solids and complete
native FreeCAD/KiCad packages. The browser is the easiest entry point; the saved
engineering files remain available for detailed editing and investigation.

## Actual desktop browser checks

The in-app browser loaded the future interface, complete reference assembly and
controller carrier in WebGL. Named-part search and selection, cover visibility,
optional internal allocations, the explode slider and model fitting responded.
The controller's embedded PCB viewer filtered and selected U80001. Its In1.Cu
drawing loaded, and schematic search found U80001 on integrated sheet 72; opening
and zooming that sheet worked. No console warnings or errors were reported in
the checked model-loading session.



The original dated browser captures remain available in Git history. They were retired from the active release during the name change because they display the previous branding; no revised capture is claimed here.

## Independent file and transport checks

- The actual bundled Three.js loader decoded all ten GLBs and their 1,800 named
  object identities. Independently decoded bounds agree with source bounds;
  the maximum loader discrepancy was below 0.004 mm. This measures mesh/export
  agreement, not manufacturing tolerance.
- The electrical audit compares the eight saved native boards, 1,298 electrical
  positions, 1,296 fitted parts, two DNP positions, 4,813 pads, all 80 current
  schematic sheets and all 32 copper drawings.
- The complete reference STEP contains 260 physical objects and 1,920 solids.
  Native FreeCAD reopening, object identities, geometry bounds and package
  checksums are recorded separately from browser tests.
- All 225 distributed inspector files answered HTTP requests at the local project
  prefix. Downloading all 14 design/PDF packages through HTTP reproduced their
  recorded SHA-256 hashes.
- The preserved engineering baseline, original paper, native designs and firmware
  are checked against their prior Git identities.

The deterministic verification is in
[the independent inspection report](../../provenance/browser-inspector-verification.json).
Native export settings and source/output hashes are available in
[the inspection manifest](../../inspector/assets/inspection-manifest.json).

## Review limits and remaining browser coverage

The app reported browser access disabled again during the final test pass.
Actual narrow-screen/mobile layout, download-link clicking, schematic
parent/child button clicking and the newly added 3D-part **Find circuit** shortcut
therefore remain unverified in a browser. Their markup, source logic, hierarchy,
asset links and download bytes were inspected. The final source-link and default
reference-cover changes also received source review rather than a repeated
browser interaction test. This is a bounded desktop review, not a claim of
compatibility with every device or browser.

InteractiveHtmlBom highlights components and nets on outer copper. The two
internal copper layers are supplied as separate native vector drawings. Schematic
SVGs provide native KiCad rendering, search and hierarchy navigation; they do not
simulate circuits or replace native connectivity. Browser meshes are tessellated
display copies. STEP and native downloads preserve solid geometry and design
structure. A static index, vector drawings and PDFs remain available when 3D
cannot run.

These checks improve access to this digital research reference. They do not add
physical, implanted or biological validation to the project.

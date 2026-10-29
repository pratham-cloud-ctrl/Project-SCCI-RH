# Project SCCI RH build inspector

**Public viewer:** <https://pratham-cloud-ctrl.github.io/Project-SCCI-RH/>

This inspection layer accompanies the preserved v2.1.0 engineering sources.
It provides two mechanical assemblies, eight populated boards, interactive
component/outer-copper lookup, four copper layers per board, all 80 current
schematic sheets, and standard/native downloads. No visitor account, CAD
installation, external viewer service or runtime CDN is required.

## Read the design in a browser

- **3D:** rotate, select a named part, hide it, isolate it, fit it, or open the
  assembly using the explode slider. Nonphysical allocation boxes default off.
- **PCB & components:** choose a board, search a reference/value or click a
  footprint. The viewer highlights components and nets on outer copper.
- **All copper layers:** inspect F.Cu, In1.Cu, In2.Cu and B.Cu as native vector
  exports. These drawings use the front-side coordinate view, including B.Cu.
- **Schematics:** search current integrated text/references and select a sheet.
  Use the zoom buttons, wheel or keyboard `+`/`-`/`0`; drag or use arrow keys
  to pan. The original sheet opens separately as SVG.
- **Download design:** STEP solids for compatible CAD, a complete current
  FreeCAD ZIP, and the complete current KiCad ZIP. Extract before opening.

The [static index](fallback.html) works without JavaScript or WebGL. It lists
the same sheets, layers and downloads. A native source link on GitHub opens a
source/download page; the public inspector opens the browser experience.

## Why this combination

The [review and credits](credits.html) explains the choices and limitations.
The [dated inspection review](https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/blob/main/docs/explore/inspector-review.md)
records actual desktop browser checks and the limits of that coverage.

| Choice | Reason | Deliberate limit |
|---|---|---|
| Pinned, locally hosted Three.js + named GLBs | Part selection and visibility; no external service/account; lazy loading | Triangulated visualization, not editable solid CAD; exact STEP/native files accompany it |
| InteractiveHtmlBom | Browser component/value lookup and real footprint/net correlation | Outer tracks/zones only; four native copper drawings supply the omitted inner-layer view |
| Native KiCad schematic SVGs and complete PDF | Actual KiCad 10 rendering of every current integrated sheet | Searchable drawings rather than simulated electrical behavior; connectivity remains in native source |
| Complete native ZIPs plus STEP | Support both direct inspection and engineering editing | Stock KiCad 10 models remain an explicit installation dependency; source scripts need the full repo for regeneration |
| GitHub Pages | Public static files kept with the repository; free public-repo hosting | GitHub README does not execute the custom viewer scripts |

KiCanvas remains a possible later enhancement after a successful compatibility
trial. Its alpha embedding implementation is not the sole reading path here.

## Source-derived assets

- [CAD manifest](assets/cad-manifest.json): native engine, tessellation settings,
  metre/Y-up transform, source hashes, part identities, bounds and output hashes.
- [Electrical manifest](assets/electronics-manifest.json): all sheet paths,
  actual KiCad text records, counts, copper views and source/output hashes.
- [Native export evidence](assets/electronics-native-export-evidence.json):
  actual MCP exports and the correction to fit large board layers without clipping.
- [Download manifest](assets/downloads-manifest.json): package identities and members.
- [Combined provenance](assets/inspection-manifest.json) and
  [download checksums](downloads/SHA256SUMS.txt).

Original engineering sources and the paper are not rewritten. New files are
inspection derivatives. The complete reference STEP contains 260 objects;
older chassis-only STEP exports remain preserved in their original location.

## Reproduce and inspect

```text
# Installed native application Pythons are required for the two export steps.
<FreeCAD>/bin/python.exe scripts/inspector/build_cad_assets.py --complete-reference-step
<KiCad>/bin/python.exe scripts/inspector/build_electronics_assets.py --help

# Repository Python, after those native exports:
python scripts/inspector/build_catalog.py
python scripts/inspector/build_electronics_assets.py --verify
python scripts/inspector/verify_inspector.py
python scripts/inspector/serve_inspector.py --port 8801
```

The local inspector is served at `http://127.0.0.1:8801/Project-SCCI-RH/`, exercising
the same project prefix as Pages. Re-export commands and exact native/tool
versions are recorded by each builder/manifest. No export command saves the
original CAD or circuit files. The vendored MIT licenses must accompany the
browser runtime and exported interactive BOMs.

This is an entirely digital research/engineering reference. Reference boards
do not fit the future can. Browser access adds inspectability and does not
establish physical, implanted or biological performance.

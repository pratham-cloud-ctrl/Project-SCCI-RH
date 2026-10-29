"""Build lightweight reader previews without changing any engineering image.

Run from the repository root with the pinned Pillow reproduction environment::

    python scripts/build_reader_previews.py
    python scripts/build_reader_previews.py --check

The first command writes only docs/explore/assets/. The second regenerates in
memory and checks the saved JPEG bytes and manifest without writing anything.
No CAD application, geometry generator, image synthesis or source edit is used.
JPEG bytes are deterministic within the recorded Pillow/JPEG codec environment.
Untagged PNG inputs are interpreted as sRGB; ICC-tagged inputs are converted to
sRGB before alpha is composited onto white. Output has no EXIF or creation time.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageCms, features


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/explore/assets"
MAX_WIDTH = 1000
QUALITY = 86
CAD_NAMES = ("reference_assembled", "reference_exploded", "future_assembled", "future_exploded")
BOARD_NAMES = (
    "recording-front-end", "controller-carrier", "current-driver", "contact-router",
    "monitoring-cell", "supervision", "monitoring-transport", "power",
)
SOURCES = tuple(
    (f"cad/stage5/renders/{name}.png", "cad-" + name.replace("_", "-") + ".jpg")
    for name in CAD_NAMES
) + tuple(
    (f"electronics/stage4/integrated-pcb/exports/{name}/isometric.png", f"pcb-{name}.jpg")
    for name in BOARD_NAMES
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def preview(source_bytes: bytes) -> tuple[bytes, list[int], list[int]]:
    with Image.open(BytesIO(source_bytes)) as source:
        source.load()
        original_size = list(source.size)
        rgba = source.convert("RGBA")
        alpha = rgba.getchannel("A")
        rgb = rgba.convert("RGB")
        if source.info.get("icc_profile"):
            rgb = ImageCms.profileToProfile(
                rgb,
                ImageCms.ImageCmsProfile(BytesIO(source.info["icc_profile"])),
                ImageCms.createProfile("sRGB"),
                outputMode="RGB",
            )
        flattened = Image.new("RGB", rgb.size, "white")
        flattened.paste(rgb, mask=alpha)
        if flattened.width > MAX_WIDTH:
            size = (MAX_WIDTH, max(1, round(flattened.height * MAX_WIDTH / flattened.width)))
            flattened = flattened.resize(size, Image.Resampling.LANCZOS)
        encoded = BytesIO()
        # Explicit metadata removal prevents upstream Blender EXIF/timestamps
        # from leaking into, or changing, these static preview derivatives.
        flattened.save(
            encoded, format="JPEG", quality=QUALITY, optimize=True, progressive=True,
            subsampling=2, exif=b"", icc_profile=None,
        )
        return encoded.getvalue(), original_size, list(flattened.size)


def build() -> tuple[dict, dict[str, bytes]]:
    images = []
    outputs = {}
    for relative_source, filename in SOURCES:
        source_bytes = (ROOT / relative_source).read_bytes()
        jpeg, source_size, output_size = preview(source_bytes)
        outputs[filename] = jpeg
        images.append({
            "source": relative_source,
            "source_sha256": sha256(source_bytes),
            "source_dimensions": source_size,
            "source_bytes": len(source_bytes),
            "output": (OUTPUT / filename).relative_to(ROOT).as_posix(),
            "output_sha256": sha256(jpeg),
            "output_dimensions": output_size,
            "output_bytes": len(jpeg),
        })
    source_bytes = sum(item["source_bytes"] for item in images)
    output_bytes = sum(item["output_bytes"] for item in images)
    manifest = {
        "schema": "scci_rh.reader-previews.v1",
        "purpose": "Lightweight GitHub reader images; original native-render PNGs remain authoritative and unchanged",
        "generator": "scripts/build_reader_previews.py",
        "generator_sha256_lf": sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "image_processing": {
            "maximum_width": MAX_WIDTH,
            "resize": "LANCZOS; preserve aspect ratio with nearest integer output height; no enlargement",
            "color_space": "sRGB; untagged inputs assumed sRGB; embedded ICC inputs converted to sRGB",
            "mode": "RGB",
            "alpha_background": "#ffffff",
            "quality": QUALITY,
            "optimize": True,
            "progressive": True,
            "subsampling": 2,
            "exif_retained": False,
            "icc_profile_embedded": False,
        },
        "build_environment": {
            "Pillow": Image.__version__,
            "JPEG_codec": features.version_codec("jpg"),
            "libjpeg_turbo": features.version_feature("libjpeg_turbo"),
        },
        "totals": {
            "images": len(images),
            "source_bytes": source_bytes,
            "output_bytes": output_bytes,
            "saved_bytes": source_bytes - output_bytes,
        },
        "images": images,
    }
    return manifest, outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify saved derivatives read-only")
    args = parser.parse_args()
    manifest, outputs = build()
    serialized = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.check:
        expected_manifest = (OUTPUT / "manifest.json").read_bytes().replace(b"\r\n", b"\n")
        if serialized != expected_manifest:
            raise AssertionError("Preview manifest differs; use the pinned Pillow environment or review changed inputs")
        for filename, data in outputs.items():
            if (OUTPUT / filename).read_bytes() != data:
                raise AssertionError("Preview differs: " + filename)
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for filename, data in outputs.items():
            (OUTPUT / filename).write_bytes(data)
        (OUTPUT / "manifest.json").write_bytes(serialized)
    totals = manifest["totals"]
    print(json.dumps({"passed": True, "mode": "check" if args.check else "build", **totals}, sort_keys=True))


if __name__ == "__main__":
    main()

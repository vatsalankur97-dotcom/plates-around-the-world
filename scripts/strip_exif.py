#!/usr/bin/env python3
"""Strip EXIF, GPS, XMP, and IPTC from published photos.

Walks the site image folders (assets/img, including assets/img/trip) and
rewrites each offending file in place. The ICC colour profile is kept.
An EXIF orientation tag is baked into the pixels first, then removed, so
viewers do not turn the photo sideways.

Dev dependency. The Netlify production build does not run this script and
stays stdlib-only.

Preferred tools:

    sudo apt-get install -y libimage-exiftool-perl libjpeg-turbo-progs

exiftool removes metadata without recompressing. jpegtran applies JPEG
orientation the same way and keeps the ICC profile (-copy icc). When the
width or height is not a multiple of the JPEG block, libjpeg cannot
transpose the partial edge blocks exactly; the rest of the photo is unchanged.

Fallback, when those are missing (Pillow re-encodes JPEG; quality="keep"
when the pixels are not rotated, quality 95 when they are):

    pip install Pillow

Animated GIFs are stripped with exiftool only, so the frames stay intact.

    python3 scripts/strip_exif.py
    python3 scripts/strip_exif.py --check
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (ROOT / "assets" / "img",)
EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}

# EXIF Orientation 2–8, as jpegtran arguments that bake the tag into pixels.
_JPEGTRAN = {
    2: ("-flip", "horizontal"),
    3: ("-rotate", "180"),
    4: ("-flip", "vertical"),
    5: ("-transpose",),
    6: ("-rotate", "90"),
    7: ("-transverse",),
    8: ("-rotate", "270"),
}

_GROUP_ORDER = ("EXIF", "GPS", "XMP", "IPTC")
_CAMERA_ORDER = (
    "Make",
    "Model",
    "UniqueCameraModel",
    "CameraOwnerName",
    "OwnerName",
    "LensMake",
    "LensModel",
    "Lens",
    "LensSerialNumber",
    "BodySerialNumber",
    "CameraSerialNumber",
    "InternalSerialNumber",
    "SerialNumber",
    "DateTimeOriginal",
    "CreateDate",
    "DateTimeDigitized",
    "OffsetTimeOriginal",
)
_CAMERA_NAMES = set(_CAMERA_ORDER)

_HEAD = re.compile(r"^======== (.+)$")
_TAG = re.compile(r"^\[(?P<group>[^\]]+)\]\s+(?P<name>\S+)\s+:\s(?P<value>.*)$")

_INSTALL = (
    "No EXIF tool found. Install exiftool (and jpegtran for phone JPEGs):\n"
    "  sudo apt-get install -y libimage-exiftool-perl libjpeg-turbo-progs\n"
    "or the Pillow fallback:\n"
    "  pip install Pillow\n"
    "These are dev dependencies. The Netlify build does not install them."
)


@dataclass
class Meta:
    groups: set[str] = field(default_factory=set)
    camera: list[str] = field(default_factory=list)
    orientation: int | None = None

    @property
    def offending(self) -> bool:
        return bool(self.groups)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def image_files(roots: list[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix.lower() in EXTENSIONS:
            found.append(root)
            continue
        if not root.is_dir():
            raise SystemExit(f"not found: {root}")
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in EXTENSIONS:
                found.append(path)
    return sorted(set(found))


def fmt_groups(groups: set[str]) -> str:
    return ", ".join(name for name in _GROUP_ORDER if name in groups)


def _camera_name(tag: str) -> bool:
    return tag in _CAMERA_NAMES or tag.startswith("Lens")


def _order_camera(names: list[str]) -> list[str]:
    rank = {name: index for index, name in enumerate(_CAMERA_ORDER)}
    unique = list(dict.fromkeys(names))
    return sorted(unique, key=lambda name: (rank.get(name, 1000), name))


def _meta_from_tags(tags: list[tuple[str, str, str]]) -> Meta:
    groups: set[str] = set()
    camera: list[str] = []
    orientation: int | None = None
    for group, name, value in tags:
        if name.startswith("GPS"):
            groups.add("GPS")
        if group == "EXIF":
            groups.add("EXIF")
            if name == "Orientation" and orientation is None:
                token = value.split()[0] if value else ""
                try:
                    orientation = int(token.split(".", 1)[0])
                except ValueError:
                    orientation = None
            if _camera_name(name) and value not in ("", "(Binary data)"):
                camera.append(name)
        elif group == "XMP":
            groups.add("XMP")
        elif group == "IPTC":
            groups.add("IPTC")
    return Meta(groups, _order_camera(camera), orientation)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def inspect_exiftool(files: list[Path]) -> dict[Path, Meta]:
    by_resolved = {path.resolve(): path for path in files}
    found: dict[Path, list[tuple[str, str, str]]] = {}
    for start in range(0, len(files), 40):
        chunk = files[start : start + 40]
        proc = _run(
            [
                "exiftool",
                "-a",
                "-G0",
                "-s",
                "-n",
                "-FileName",
                "-EXIF:all",
                "-XMP:all",
                "-IPTC:all",
                *[str(path) for path in chunk],
            ]
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise SystemExit(f"exiftool failed:\n{detail}")
        # One file: exiftool prints tags only. Several files: a ======== header
        # before each file. Tag lines before the first header belong to chunk[0].
        current = chunk[0].resolve() if len(chunk) == 1 else None
        if current is not None:
            found.setdefault(current, [])
        for line in proc.stdout.splitlines():
            head = _HEAD.match(line)
            if head:
                current = Path(head.group(1)).resolve()
                found.setdefault(current, [])
                continue
            parsed = _TAG.match(line)
            if parsed is None or current is None:
                continue
            found[current].append(
                (parsed.group("group"), parsed.group("name"), parsed.group("value"))
            )
    missing = [path for path in by_resolved if path not in found]
    if missing:
        names = ", ".join(rel(path) for path in missing[:5])
        raise SystemExit(f"exiftool returned nothing for: {names}")
    return {by_resolved[key]: _meta_from_tags(tags) for key, tags in found.items()}


def inspect_pillow(files: list[Path]) -> dict[Path, Meta]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(_INSTALL) from exc

    tag_names = {
        271: "Make",
        272: "Model",
        36867: "DateTimeOriginal",
        36868: "CreateDate",
        42036: "LensModel",
        42035: "LensMake",
    }
    out: dict[Path, Meta] = {}
    for path in files:
        with Image.open(path) as image:
            groups: set[str] = set()
            camera: list[str] = []
            orientation: int | None = None
            exif = image.getexif()
            if len(exif):
                groups.add("EXIF")
                raw_orientation = exif.get(274)
                if raw_orientation is not None:
                    try:
                        orientation = int(raw_orientation)
                    except (TypeError, ValueError):
                        orientation = None
                if exif.get_ifd(0x8825):
                    groups.add("GPS")
                for tag, name in tag_names.items():
                    if exif.get(tag):
                        camera.append(name)
            info = image.info
            if info.get("xmp") or info.get("XML:com.adobe.xmp"):
                groups.add("XMP")
            if info.get("photoshop") or info.get("iptc"):
                groups.add("IPTC")
        raw = path.read_bytes()
        if b"Exif\x00\x00" in raw:
            groups.add("EXIF")
        if b"http://ns.adobe.com/xap/1.0/\x00" in raw or b"<x:xmpmeta" in raw:
            groups.add("XMP")
        if b"Photoshop 3.0\x00" in raw:
            groups.add("IPTC")
        out[path] = Meta(groups, _order_camera(camera), orientation)
    return out


def inspect(files: list[Path]) -> dict[Path, Meta]:
    if not files:
        return {}
    if shutil.which("exiftool"):
        return inspect_exiftool(files)
    return inspect_pillow(files)


def _temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.strip-tmp")


def jpegtran_bake(path: Path, orientation: int) -> None:
    jpegtran = shutil.which("jpegtran")
    if not jpegtran:
        raise SystemExit("jpegtran is not installed")
    dest = _temp_path(path)
    proc = _run(
        [
            jpegtran,
            "-copy",
            "icc",
            *_JPEGTRAN[orientation],
            "-outfile",
            str(dest),
            str(path),
        ]
    )
    try:
        if proc.returncode != 0 or not dest.is_file():
            detail = (proc.stderr or proc.stdout).strip()
            raise SystemExit(f"jpegtran could not orient {rel(path)}:\n{detail}")
        dest.replace(path)
    finally:
        dest.unlink(missing_ok=True)


def _animated_gif(path: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    with Image.open(path) as image:
        return image.format == "GIF" and getattr(image, "n_frames", 1) > 1


def pillow_rewrite(path: Path, transpose: bool) -> None:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise SystemExit(_INSTALL) from exc
    if path.suffix.lower() == ".gif" and _animated_gif(path):
        raise SystemExit(
            f"{rel(path)}: animated GIF metadata has to be stripped with "
            "exiftool. Pillow would flatten the frames.\n"
            "  sudo apt-get install -y libimage-exiftool-perl"
        )
    dest = _temp_path(path)
    try:
        with Image.open(path) as image:
            fmt = image.format
            icc = image.info.get("icc_profile")
            if transpose:
                image = ImageOps.exif_transpose(image)
            save_kwargs: dict[str, object] = {}
            if icc:
                save_kwargs["icc_profile"] = icc
            if fmt == "JPEG":
                # quality="keep" still re-encodes. It only works on the
                # original JPEG object, which exif_transpose replaces.
                if transpose:
                    save_kwargs["quality"] = 95
                else:
                    save_kwargs["quality"] = "keep"
                    save_kwargs["subsampling"] = "keep"
                save_kwargs["exif"] = b""
            elif fmt in {"PNG", "WEBP"}:
                save_kwargs["exif"] = b""
            image.save(dest, format=fmt, **save_kwargs)
        dest.replace(path)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        dest.unlink(missing_ok=True)


def exiftool_delete(path: Path) -> None:
    proc = _run(
        [
            "exiftool",
            "-overwrite_original",
            "-EXIF:all=",
            "-XMP:all=",
            "-IPTC:all=",
            "-GPS:all=",
            str(path),
        ]
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise SystemExit(f"exiftool could not strip {rel(path)}:\n{detail}")


def strip_one(path: Path, meta: Meta) -> str:
    orient = meta.orientation if meta.orientation in _JPEGTRAN else None
    ext = path.suffix.lower()
    if orient and ext in {".jpg", ".jpeg"} and shutil.which("jpegtran"):
        jpegtran_bake(path, orient)
        method = "jpegtran"
    elif orient or not shutil.which("exiftool"):
        pillow_rewrite(path, transpose=bool(orient))
        method = "pillow"
    else:
        exiftool_delete(path)
        method = "exiftool"
    remaining = inspect([path])[path]
    if remaining.groups:
        left = fmt_groups(remaining.groups)
        raise SystemExit(f"{rel(path)}: still has {left} after {method}")
    return method


def _describe(meta: Meta, method: str) -> str:
    detail = fmt_groups(meta.groups)
    if meta.camera:
        detail += "; camera: " + ", ".join(meta.camera)
    return f"stripped ({detail}) via {method}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip EXIF, GPS, XMP, and IPTC from published photos.",
        epilog=(
            "Dev dependency: exiftool and jpegtran, or Pillow. "
            "Not used by the Netlify production build."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="list images that still have EXIF, GPS, XMP, or IPTC and exit 1",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="image files or directories (default: assets/img)",
    )
    args = parser.parse_args(argv)
    roots = [Path(raw) for raw in args.paths] if args.paths else list(DEFAULT_ROOTS)
    files = image_files(roots)
    if not files:
        print("no images found")
        return 0
    found = inspect(files)
    offenders = [path for path in files if found[path].offending]
    if args.check:
        for path in offenders:
            print(f"{rel(path)}: {fmt_groups(found[path].groups)}")
        if offenders:
            return 1
        noun = "image" if len(files) == 1 else "images"
        print(f"ok: {len(files)} {noun}, no EXIF, GPS, XMP, or IPTC")
        return 0

    gps_or_camera: list[str] = []
    for path in offenders:
        meta = found[path]
        method = strip_one(path, meta)
        print(f"{rel(path)}: {_describe(meta, method)}")
        notes: list[str] = []
        if "GPS" in meta.groups:
            notes.append("GPS")
        if meta.camera:
            notes.append("camera: " + ", ".join(meta.camera))
        if notes:
            gps_or_camera.append(f"{rel(path)}: {'; '.join(notes)}")
    if not offenders:
        noun = "image" if len(files) == 1 else "images"
        print(f"ok: {len(files)} {noun}, no EXIF, GPS, XMP, or IPTC")
    if gps_or_camera:
        print("GPS or camera data:")
        for line in gps_or_camera:
            print(f"  {line}")
    elif offenders:
        print("no GPS or camera metadata found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

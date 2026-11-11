#!/usr/bin/env python3
"""Builds the photography site's galleries from the folders of original photos.

Run from anywhere:   python3 photography-portfolio/build.py

Every folder that directly contains photos becomes one gallery (one menu item).
Web-sized copies are written to images/, with camera metadata (EXIF, GPS, XMP)
removed, and js/data.js is regenerated. Originals are never modified.
Names, order, captions and About text live in content.json.
"""
import json
import re
import struct
import unicodedata
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
SOURCE = SITE.parent / "Photography Potfolio"
OUT = SITE / "images"
SIZES = {"l": 2000, "s": 1000}  # longest edge in pixels
QUALITY = "80"
EXTENSIONS = {".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
VIDEO_OUT = SITE / "videos"
VIDEO_TOOL = SITE / "tools" / ".webvideo"   # compiled from tools/webvideo.swift on first use
VIDEO_KBPS = 5000            # video bitrate, kbit/s
VIDEO_EDGE = 1920            # longest edge in pixels (1080p)
VIDEO_MAX_BYTES = 95_000_000  # GitHub Pages refuses files over 100 MB
SOF_MARKERS = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def segments(data):
    """Yield (marker, start, end) for each JPEG header segment, up to the scan."""
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker == 0xDA:  # start of scan: image data follows
            yield marker, pos, len(data)
            return
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        yield marker, pos, pos + 2 + length
        pos += 2 + length


def orientation(data):
    """EXIF orientation (1-8), or 1 when absent."""
    for marker, start, end in segments(data):
        body = data[start + 4:end]
        if marker != 0xE1 or not body.startswith(b"Exif\x00\x00"):
            continue
        tiff = body[6:]
        if len(tiff) < 8:
            return 1
        order = "<" if tiff[:2] == b"II" else ">"
        ifd = struct.unpack(order + "I", tiff[4:8])[0]
        count = struct.unpack(order + "H", tiff[ifd:ifd + 2])[0]
        for i in range(count):
            entry = tiff[ifd + 2 + i * 12:ifd + 14 + i * 12]
            if len(entry) == 12 and struct.unpack(order + "H", entry[:2])[0] == 0x0112:
                return struct.unpack(order + "H", entry[8:10])[0]
    return 1


def dimensions(data):
    for marker, start, _ in segments(data):
        if marker in SOF_MARKERS:
            height, width = struct.unpack(">HH", data[start + 5:start + 9])
            return width, height
    raise ValueError("no size found")


def strip_metadata(path):
    """Remove EXIF/XMP (APP1), IPTC (APP13) and comments; keep the colour profile."""
    data = path.read_bytes()
    kept = [data[:2]]
    for marker, start, end in segments(data):
        if marker in (0xE1, 0xED, 0xFE):
            continue
        kept.append(data[start:end])
    path.write_bytes(b"".join(kept))


def slug(text):
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def sips(*args):
    subprocess.run(["sips", *args], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


ROTATE = {3: "180", 6: "90", 8: "270"}


def make_copy(src, dest, edge, turn):
    sips("-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
         "-Z", str(edge), str(src), "--out", str(dest))
    if turn in ROTATE:
        sips("-r", ROTATE[turn], str(dest))
    strip_metadata(dest)


def build_videos(folder, title, order=(), hide=()):
    """Web-sized .mp4 and a poster image for every video in the folder.

    order and hide are positions in file-name order: order puts those videos first,
    hide leaves videos off the site."""
    source = VIDEO_TOOL.with_name("webvideo.swift")
    if not VIDEO_TOOL.exists() or VIDEO_TOOL.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(["swiftc", "-O", str(source), "-o", str(VIDEO_TOOL)],
                       check=True, stderr=subprocess.DEVNULL)
    out = VIDEO_OUT / slug(title)
    out.mkdir(parents=True, exist_ok=True)
    videos = {}
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
    for n, src in enumerate(files, 1):
        dest, poster = out / f"{n:02d}.mp4", out / f"{n:02d}.jpg"
        if n in hide:
            dest.unlink(missing_ok=True)
            poster.unlink(missing_ok=True)
            continue
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            print(f"  converting {src.name} ...")
            kbps = VIDEO_KBPS
            for _ in range(3):
                subprocess.run([str(VIDEO_TOOL), str(src), str(dest), str(kbps), str(VIDEO_EDGE)],
                               check=True, stdout=subprocess.DEVNULL)
                size = dest.stat().st_size
                if size <= VIDEO_MAX_BYTES:
                    break
                # Too big to host: try again at a bitrate that fits.
                kbps = int(kbps * VIDEO_MAX_BYTES / size * 0.95)
                print(f"    over the size limit, retrying at {kbps} kbit/s")
            for leftover in out.glob(dest.name + ".sb-*"):  # the converter's temporary copy
                leftover.unlink()
            subprocess.run(["qlmanage", "-t", "-s", "1280", "-o", str(out), str(dest)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            thumb = out / (dest.name + ".png")
            sips("-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
                 str(thumb), "--out", str(poster))
            thumb.unlink()
            strip_metadata(poster)
        width, height = dimensions(poster.read_bytes())
        videos[n] = {"src": str(dest.relative_to(SITE)), "poster": str(poster.relative_to(SITE)),
                     "w": width, "h": height, "caption": title}
    first = [n for n in order if n in videos]
    return [videos[n] for n in first + [n for n in videos if n not in first]]


def main():
    content = json.loads((SITE / "content.json").read_text())
    titles = content.get("titles", {})
    captions = content.get("captions", {})

    # "noPhotos" lists folders whose photos stay off the site (their videos can still be used).
    skipped = set(content.get("noPhotos", []))
    folders = {p.parent.name: p.parent for p in SOURCE.rglob("*")
               if p.suffix.lower() in EXTENSIONS and p.parent.name not in skipped}

    # Web copies for every folder of originals.
    events = {}
    for name in sorted(folders, key=str.lower):
        folder = folders[name]
        title = titles.get(name, name)
        photos = []
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS)
        for n, src in enumerate(files, 1):
            rel = str(src.relative_to(SOURCE))
            turn = orientation(src.read_bytes())
            entry = {"caption": captions.get(rel, title)}
            for key, edge in SIZES.items():
                dest = OUT / slug(title) / f"{n:02d}-{key}.jpg"
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                    make_copy(src, dest, edge, turn)
                entry[key] = str(dest.relative_to(SITE))
                if key == "l":
                    entry["w"], entry["h"] = dimensions(dest.read_bytes())
            photos.append(entry)
        events[name] = photos

    # "order" in content.json sets the sequence inside a folder's gallery, as positions
    # in file-name order (the same numbers highlights use). Unlisted photos follow after.
    def ordered(name):
        photos = events[name]
        first = [i for i in content.get("order", {}).get(name, []) if 1 <= i <= len(photos)]
        rest = [i for i in range(1, len(photos) + 1) if i not in first]
        return [photos[i - 1] for i in first + rest]

    # Menu categories: each one joins the photos of its folders, in the order listed.
    # "folders": "rest" takes every folder no other category names.
    named = {f for c in content["categories"] if isinstance(c["folders"], list)
             for f in c["folders"]}
    galleries = []
    for category in content["categories"]:
        names = category["folders"]
        if names == "rest":
            names = [n for n in events if n not in named]
        missing = [n for n in names if n not in events]
        if missing:
            sys.exit(f"content.json: no photo folder called {missing} (category {category['title']})")
        photos = [photo for n in names for photo in ordered(n)]
        gallery = {"slug": slug(category["title"]), "title": category["title"],
                   "note": category.get("note", ""), "photos": photos}
        # "submenu": true turns the category into a drop-down with one gallery per folder.
        # "videos" lists folders whose videos are shown on this page.
        gallery["videos"] = []
        video_children = []
        for name in category.get("videos", []):
            found = [p for p in SOURCE.rglob(name) if p.is_dir()]
            if not found:
                sys.exit(f"content.json: no folder called {name!r} (category {category['title']})")
            # "videoTitles" names a folder's video gallery when it differs from its photo title.
            title = content.get("videoTitles", {}).get(name, titles.get(name, name))
            clips = build_videos(found[0], title,
                                 content.get("videoOrder", {}).get(name, []),
                                 content.get("videoHide", {}).get(name, []))
            gallery["videos"] += clips
            video_children.append({"slug": slug(title), "title": title, "photos": [],
                                   "videos": [dict(c, caption="") for c in clips]})
        if gallery["videos"]:
            print(f"{category['title']}: {len(gallery['videos'])} videos")
        if category.get("submenu"):
            gallery["photos"] = []
            gallery["children"] = [
                {"slug": slug(titles.get(n, n)), "title": titles.get(n, n),
                 "photos": [dict(p, caption="" if p["caption"] == titles.get(n, n) else p["caption"])
                            for p in ordered(n)]}
                for n in names] + video_children
            gallery["videos"] = []
        galleries.append(gallery)
        print(f"{category['title']}: {len(photos)} photos from {len(names)} folders")

    # Homepage highlights, written as "Folder name#position" (position by file name order).
    highlights = []
    for ref in content.get("highlights", []):
        name, _, position = ref.rpartition("#")
        if name not in events or not 1 <= int(position) <= len(events[name]):
            sys.exit(f"content.json: highlight {ref!r} does not match a photo")
        highlights.append(events[name][int(position) - 1])

    site = {k: content[k] for k in ("name", "brand", "tagline", "email", "instagram", "linkedin", "about")}
    site["highlights"] = highlights
    site["galleries"] = galleries
    site["events"] = [titles.get(n, n) for n in events]
    (SITE / "js").mkdir(exist_ok=True)
    (SITE / "js" / "data.js").write_text(
        "window.SITE = " + json.dumps(site, ensure_ascii=False, indent=1) + ";\n")
    print(f"Done: {sum(len(p) for p in events.values())} photos, {len(highlights)} highlights")


if __name__ == "__main__":
    sys.exit(main())

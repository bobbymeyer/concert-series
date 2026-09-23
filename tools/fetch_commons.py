#!/usr/bin/env python3
"""Fetch performer photos from Wikimedia Commons, and only freely licensed ones.

Commons publishes a licence and an author for every file, so a photo taken from
it can be used and credited properly -- unlike a press or streaming-service
still, which is licensed to the publisher and not to you. This asks Commons for
each flyer's performer, keeps only files under a free licence, downloads one,
and records the attribution those licences require.

    python3 tools/fetch_commons.py                 # look, change nothing
    python3 tools/fetch_commons.py --write         # download and write credits
    python3 tools/fetch_commons.py ennio-morricone --write --index 2

Run it where the network is open; it needs nothing but the standard library.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flyer.config import Flyer, discover, load_yaml   # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "concert-series/0.1 (flyer example content; stdlib urllib)"

# Licences that let you republish with attribution. Anything else is skipped,
# including the "fair use" and "non-free" tags Commons also carries.
FREE = ("cc0", "cc-by", "cc by", "public domain", "pd-", "attribution")
NOT_FREE = ("non-free", "nonfree", "fair use", "-nc", "-nd", "noncommercial",
            "no derivatives", "copyright")


def is_free(license_name):
    """Whether a Commons licence short name permits reuse with credit."""
    name = (license_name or "").strip().lower()
    if not name:
        return False
    if any(bad in name for bad in NOT_FREE):
        return False
    return any(good in name for good in FREE)


def api(**params):
    params.update(format="json", formatversion="2")
    url = f"{API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def strip_markup(value):
    """Commons metadata arrives as small fragments of HTML."""
    import html
    import re
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def candidates(name, width=1400, limit=8):
    """Freely licensed photos of ``name``, best guess first."""
    found = api(action="query", generator="search", gsrsearch=f'"{name}" filetype:bitmap',
                gsrnamespace="6", gsrlimit=limit, prop="imageinfo",
                iiprop="url|extmetadata|size", iiurlwidth=width)
    out = []
    for page in found.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        def field(key):
            return strip_markup((meta.get(key) or {}).get("value", ""))
        licence = field("LicenseShortName")
        if not is_free(licence):
            continue
        out.append({
            "title": page["title"],
            "url": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "licence": licence,
            "licence_url": field("LicenseUrl"),
            "author": field("Artist") or "unknown",
        })
    return out


def download(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        target.write_bytes(response.read())


def write_credits(root, rows):
    """The attribution these licences require, in one file beside the content."""
    lines = ["# Photo credits", "",
             "Performer photos taken from Wikimedia Commons under the licence",
             "named for each. Replace a row if you swap the image.", ""]
    for row in sorted(rows, key=lambda r: r["slug"]):
        lines += [f"## {row['performer']}", "",
                  f"- File: `{row['slug']}/{row['file']}`",
                  f"- Source: {row['descriptionurl']}",
                  f"- Author: {row['author']}",
                  f"- Licence: {row['licence']} {row['licence_url']}".rstrip(), ""]
    (root / "PHOTO-CREDITS.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", help="content folders; omit for all")
    parser.add_argument("--content", default="content")
    parser.add_argument("--write", action="store_true",
                        help="actually download; without it, only report")
    parser.add_argument("--index", type=int, default=1,
                        help="which of the candidates to take (1-based)")
    args = parser.parse_args(argv)

    root = Path(args.content)
    folders = [f for f in discover(root)
               if not args.slugs or f.name in set(args.slugs)]
    if not folders:
        raise SystemExit(f"no flyers found in {root}/")

    rows = []
    for folder in folders:
        data = load_yaml(Flyer._content_file_in(folder))
        performer = data.get("performer")
        if not performer:
            continue
        try:
            found = candidates(str(performer))
        except Exception as error:                      # network, policy, rate limit
            print(f"{folder.name:24} lookup failed: {error}")
            continue
        if not found:
            print(f"{folder.name:24} no freely licensed photo on Commons")
            continue
        print(f"{folder.name:24} {len(found)} free candidate(s) for {performer!r}")
        for i, item in enumerate(found, 1):
            mark = "->" if i == args.index else "  "
            print(f"  {mark} {i}. {item['title']}  [{item['licence']}]  {item['author']}")
        if not args.write:
            continue
        pick = found[min(args.index, len(found)) - 1]
        suffix = Path(urllib.parse.urlparse(pick["url"]).path).suffix or ".jpg"
        target = folder / f"photo{suffix}"
        download(pick["url"], target)
        for old in folder.glob("photo.*"):              # one photo per folder
            if old != target:
                old.unlink()
        rows.append(dict(pick, slug=folder.name, performer=str(performer),
                         file=target.name))
        print(f"  wrote {target}")

    if rows:
        write_credits(root, rows)
        print(f"\nwrote {root / 'PHOTO-CREDITS.md'} for {len(rows)} photo(s)")
    elif args.write:
        print("\nnothing downloaded")
    else:
        print("\nnothing written; pass --write to download")
    return 0


if __name__ == "__main__":
    sys.exit(main())

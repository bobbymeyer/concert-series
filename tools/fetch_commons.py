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
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml                                           # noqa: E402

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


# Wikimedia asks for a modest request rate, and answers 429 when pushed.
PAUSE = 2.0
_last_call = [0.0]

# Only these widths are pre-rendered and cached; asking for any other size
# makes the servers render a thumbnail on demand, which is what gets refused.
THUMB_WIDTHS = (120, 180, 240, 320, 400, 640, 800, 1024, 1280, 2560)


def fetch(url, timeout=30):
    """One paced, retrying request. Returns the raw body."""
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(6):
        wait = PAUSE - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(3 * 2 ** attempt)          # 3, 6, 12, 24, 48 seconds
    raise RuntimeError("unreachable")


def api(**params):
    params.update(format="json", formatversion="2")
    return json.loads(fetch(f"{API}?{urllib.parse.urlencode(params)}"))


PARTICLES = {"de", "di", "da", "del", "della", "van", "von", "the", "and"}


def fold(text):
    """Lowercase, strip accents and anything that is not a letter or digit."""
    plain = unicodedata.normalize("NFKD", str(text))
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", plain.lower())


def name_tokens(name):
    """The parts of a name that a file title has to carry to be about them."""
    words = re.findall(r"[^\W\d_]+", str(name), flags=re.UNICODE)
    return [fold(w) for w in words if len(w) > 2 and fold(w) not in PARTICLES]


def is_about(title, name):
    """Whether a Commons file title plausibly depicts this person.

    A plain search brings back whatever shares a word -- a trolleybus, a NASA
    render -- so a file has to carry every part of the name before it is even
    a candidate. It is a crude check, and it is why the run is reported before
    anything is written.
    """
    folded = fold(title)
    tokens = name_tokens(name)
    return bool(tokens) and all(token in folded for token in tokens)


def strip_markup(value):
    """Commons metadata arrives as small fragments of HTML."""
    import html
    import re
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def candidates(name, query=None, width=1024, limit=12):
    """Freely licensed photos that are plausibly of ``name``, best guess first."""
    search = query or name
    if width not in THUMB_WIDTHS:
        raise ValueError(f"width must be one of {THUMB_WIDTHS}")
    found = api(action="query", generator="search",
                gsrsearch=f'"{search}" filetype:bitmap',
                gsrnamespace="6", gsrlimit=limit, prop="imageinfo",
                iiprop="url|extmetadata|size", iiurlwidth=width)
    out = []
    for page in found.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        def field(key):
            return strip_markup((meta.get(key) or {}).get("value", ""))
        licence = field("LicenseShortName")
        if not is_free(licence) or not is_about(page["title"], search):
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
    target.write_bytes(fetch(url, timeout=60))


CREDIT_FILE = "photo-credit.yaml"


def record_credit(folder, row):
    """Keep each photo's attribution beside the photo itself.

    The credits file is rebuilt from these, so fetching one flyer's photo does
    not drop the credits for the others.
    """
    keep = ("performer", "file", "title", "descriptionurl", "author",
            "licence", "licence_url")
    (folder / CREDIT_FILE).write_text(
        yaml.safe_dump({k: row[k] for k in keep if row.get(k)}, sort_keys=False),
        encoding="utf-8")


def write_credits(root):
    """The attribution these licences require, gathered from every folder."""
    rows = []
    for folder in discover(root):
        credit = folder / CREDIT_FILE
        if credit.exists():
            rows.append((folder.name, load_yaml(credit)))
    if not rows:
        return 0
    lines = ["# Photo credits", "",
             "Performer photos taken from Wikimedia Commons under the licence",
             "named for each. Rebuilt by `tools/fetch_commons.py` from the",
             f"`{CREDIT_FILE}` beside each photo.", ""]
    for slug, row in sorted(rows):
        lines += [f"## {row.get('performer', slug)}", "",
                  f"- File: `{slug}/{row.get('file', '')}`",
                  f"- Source: {row.get('descriptionurl', '')}",
                  f"- Author: {row.get('author', 'unknown')}",
                  f"- Licence: {row.get('licence', '')} "
                  f"{row.get('licence_url', '')}".rstrip(), ""]
    (root / "PHOTO-CREDITS.md").write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", help="content folders; omit for all")
    parser.add_argument("--content", default="content")
    parser.add_argument("--write", action="store_true",
                        help="actually download; without it, only report")
    parser.add_argument("--index", type=int, default=1,
                        help="which of the candidates to take (1-based)")
    parser.add_argument("--query", default=None,
                        help="search Commons for this instead of the performer")
    parser.add_argument("--credits-only", action="store_true",
                        help="re-record attributions for photos already fetched, "
                             "without downloading them again")
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
            found = candidates(str(performer), query=args.query)
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
        if not (args.write or args.credits_only):
            continue
        pick = found[min(args.index, len(found)) - 1]
        suffix = Path(urllib.parse.urlparse(pick["url"]).path).suffix or ".jpg"
        target = folder / f"photo{suffix}"
        if args.credits_only:
            if not target.exists():
                print(f"  no {target.name} to credit; skipped")
                continue
        else:
            download(pick["url"], target)
            for old in folder.glob("photo.*"):          # one photo per folder
                if old != target:
                    old.unlink()
        row = dict(pick, slug=folder.name, performer=str(performer),
                   file=target.name)
        record_credit(folder, row)
        rows.append(row)
        print(f"  {'credited' if args.credits_only else 'wrote'} {target}")

    if rows:
        total = write_credits(root)
        print(f"\nwrote {root / 'PHOTO-CREDITS.md'} "
              f"({len(rows)} fetched, {total} credited in all)")
    elif args.write or args.credits_only:
        print("\nnothing written")
    else:
        print("\nnothing written; pass --write to download")
    return 0


if __name__ == "__main__":
    sys.exit(main())

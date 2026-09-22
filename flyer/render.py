"""SVG emission.

The output is a single self-contained SVG 1.1 file: the photo and the fonts are
embedded as data URIs, and the photo's tone is a filter rather than a blend mode, so
the flyer renders identically in a browser, in Inkscape, in rsvg and at a print
shop. Nothing in the file depends on this tool being installed.
"""

import base64
import mimetypes
from pathlib import Path

from . import fontmetrics
from .color import parse
from .config import Design, deep_merge
from .layout import plan
from .units import fmt

SVG_NS = "http://www.w3.org/2000/svg"


def escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def data_uri(path, mime=None):
    mime = mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    blob = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{blob}"


def font_face_css(design, weights, family):
    """@font-face rules for exactly the weights this flyer uses."""
    rules = []
    for weight in sorted(set(weights)):
        path = design.font_file(weight)
        if not Path(path).exists():
            raise FileNotFoundError(f"font file missing: {path}")
        uri = data_uri(path, "font/ttf")
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{weight};src:url({uri}) format('truetype');}}"
        )
    return "\n".join(rules)


def tone_filter(image, filter_id="tone"):
    """Desaturate, then ramp each channel from the shadow to the highlight.

    For a fully desaturated photo, a ramp from black to the ground is exactly
    that photo multiplied over the ground, and a ramp from the ground to white
    is exactly that photo screened over it -- computed rather than blended, so
    it needs no compositing support from the renderer.
    """
    shadow, highlight = parse(image.shadow), parse(image.highlight)
    funcs = "".join(
        f'<feFunc{ch} type="linear" slope="{fmt(hi - lo, 4)}" intercept="{fmt(lo, 4)}"/>'
        for ch, lo, hi in zip("RGB", shadow, highlight)
    )
    return (
        f'<filter id="{filter_id}" color-interpolation-filters="sRGB">'
        f'<feColorMatrix type="saturate" values="{fmt(image.desaturate, 4)}"/>'
        f'<feComponentTransfer>{funcs}</feComponentTransfer>'
        f'</filter>'
    )


def render(flyer, embed_images=None, embed_fonts=None):
    """Render one flyer to an SVG document string."""
    design = Design(flyer.design.root, deep_merge(flyer.design.data, flyer.overrides))
    image_cfg = design.data.get("image", {})
    type_cfg = design.typography

    if embed_images is None:
        embed_images = bool(image_cfg.get("embed", True))
    if embed_fonts is None:
        embed_fonts = bool(design.data.get("fonts", {}).get("embed", True))

    href = (data_uri(flyer.image_path, flyer.image_mime) if embed_images
            else flyer.image_path.name)
    page = plan(flyer, href)

    family = type_cfg.get("family", "Rethink Sans")
    stack = type_cfg.get("fallback", "sans-serif")
    font_stack = f"'{family}', {stack}"
    use_textlength = bool(type_cfg.get("text_length", True))

    defs = [tone_filter(page.image)]
    if embed_fonts:
        weights = {line.weight for line in page.lines}
        defs.insert(0, f"<style>\n{font_face_css(design, weights, family)}\n</style>")
    defs.append(
        f'<clipPath id="photo"><rect x="{fmt(page.image.rect.x)}" '
        f'y="{fmt(page.image.rect.y)}" width="{fmt(page.image.rect.w)}" '
        f'height="{fmt(page.image.rect.h)}"/></clipPath>'
    )

    body = [
        f'<rect width="{fmt(page.width)}" height="{fmt(page.height)}" '
        f'fill="{page.background}"/>',
        f'<image x="{fmt(page.image.rect.x)}" y="{fmt(page.image.rect.y)}" '
        f'width="{fmt(page.image.rect.w)}" height="{fmt(page.image.rect.h)}" '
        f'preserveAspectRatio="{page.image.preserve_aspect_ratio}" '
        f'clip-path="url(#photo)" filter="url(#tone)" '
        f'href="{escape(page.image.href)}"/>',
    ]

    type_lines = []
    for line in page.lines:
        attrs = [
            f'x="{fmt(line.x)}"', f'y="{fmt(line.baseline)}"',
            f'font-size="{fmt(line.size)}"', f'font-weight="{line.weight}"',
            f'fill="{line.color}"',
        ]
        if line.anchor != "start":
            attrs.append(f'text-anchor="{line.anchor}"')
        if use_textlength and len(line.text) > 1:
            attrs.append(f'textLength="{fmt(line.width)}" lengthAdjust="spacing"')
        attrs.append(f'data-field="{line.field}"')
        type_lines.append(f'<text {" ".join(attrs)}>{escape(line.text)}</text>')
    body.append(
        f'<g font-family="{escape(font_stack)}" xml:space="preserve">\n    '
        + "\n    ".join(type_lines) + "\n  </g>"
    )

    title = " — ".join(str(flyer.data[k]) for k in ("performer", "venue")
                       if flyer.data.get(k))
    notes = ", ".join(f"{k}={v}" for k, v in sorted(page.notes.items()))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="{SVG_NS}" width="{fmt(page.width / 72, 4)}in" '
        f'height="{fmt(page.height / 72, 4)}in" '
        f'viewBox="0 0 {fmt(page.width)} {fmt(page.height)}" '
        'version="1.1">\n'
        f'  <title>{escape(title or flyer.slug)}</title>\n'
        f'  <desc>{escape(notes)}</desc>\n'
        f'  <defs>\n    ' + "\n    ".join(defs) + "\n  </defs>\n  "
        + "\n  ".join(body) + "\n</svg>\n"
    ), page

# The other method

The same six flyers, asked for in words instead of built from the yaml beside
them. One prompt each, one image each, nothing retouched and no second pass.

| | |
| --- | --- |
| Model | `gpt-image-1` |
| Size | 1024x1536, the nearest portrait size on offer. The page is 8.5x11in |
| Quality | `high` |
| Generated | 2026-09-24 |
| Prompt | `tools/diffuse.py`, one template with the fields filled in |

Every prompt carries the same brief and the same ground and ink the procedural
side assigned to that flyer, so the method is the only thing that differs.
Regenerate with `python3 tools/diffuse.py`; `--dry-run` prints the prompts
without spending anything.

These are kept as they came back, mistakes included.

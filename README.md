# Shape Up EPUB builder

Builds an EPUB 3 e-book of [*Shape Up*](https://basecamp.com/shapeup) by Ryan Singer from the free web edition, for reading on an e-reader (made for an Onyx Boox).

This is **not an official edition**. The text and images belong to 37signals LLC. The scripts download them from basecamp.com each time you build. This repository does not include the book itself.

## Quick start

```sh
python3 make_cover.py      # only needed to remake cover.jpg
python3 build_epub.py      # writes shape-up.epub
epubcheck shape-up.epub    # optional: check the file
ebook-viewer shape-up.epub # optional: preview it in Calibre
```

A build takes about 30 seconds. To write the book somewhere else, give a path: `python3 build_epub.py ~/Books/shape-up.epub`.

## Requirements

| Tool | Used by | Needed for |
|---|---|---|
| Python 3.12+ | all scripts | always |
| [Pillow](https://python-pillow.org/) | `images.py`, `make_cover.py` | always |
| Google Chrome | `make_cover.py` | remaking the cover |
| `pdftoppm` (poppler-utils) | `make_cover.py` | remaking the cover |
| [EPUBCheck](https://www.w3.org/publishing/epubcheck/) | you | checking the file (optional) |
| [Calibre](https://calibre-ebook.com/) | you | previewing, sending to a device (optional) |

## Files

| File | What it does |
|---|---|
| `build_epub.py` | Downloads every chapter and image, cleans the HTML, and packs the EPUB. |
| `images.py` | Gives see-through PNGs a white background, and turns animations into one still image. |
| `make_cover.py` | Makes `cover.jpg` from the title graphic on the web edition's home page. |
| `cover.jpg` | The cover used by `build_epub.py`. It is saved in the repository so a normal build doesn't need Chrome. |

## What the build does

1. **Finds the chapters.** It reads the table of contents from the sidebar of the web book, including the four parts.
2. **Cleans each chapter.** It keeps only the book text, and drops menus, icons, and buttons. It rewrites the HTML as strict XHTML, the format EPUB needs.
3. **Fixes links.** Links between chapters point inside the book. Each term marked in the text links to its Glossary entry.
4. **Fixes images.** All images stay at full quality. Images with see-through backgrounds get a white background, so they don't disappear in dark mode. The animated Hill Chart becomes its final still image, with a "Watch the animation online" link.
5. **Adds structure.** Each file is tagged as a foreword, chapter, part, appendix, or glossary, for readers and screen readers. The book also has landmarks, a nested table of contents, and an older-style table of contents (NCX) for older readers.
6. **Adds front pages and metadata.** It adds a title page and a copyright page that says where the book came from and what was changed. It also fills in the author, date, description, and accessibility information.

## Putting it on an e-reader

- **Boox:** copy `shape-up.epub` into the `Books` folder over USB, or upload it with BooxDrop. NeoReader opens EPUB directly.
- **Kobo:** for better page counts and reading stats, convert it first: `ebook-convert shape-up.epub shape-up.kepub`.
- **Kindle:** upload the EPUB with Send to Kindle.

## Known limits

- **Built from the live site.** If Basecamp changes its page layout, the build may break. Look at `extract_content` and `parse_toc` in `build_epub.py` first.
- **No accessibility conformance claim.** The book has accessibility metadata, but it says nothing about meeting a standard such as WCAG AA, because it hasn't been audited with [DAISY Ace](https://daisy.github.io/ace/).
- **No print page numbers.** Page numbers aren't matched to the printed book.

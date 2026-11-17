# Shape Up EPUB builder

Builds an EPUB 3 e-book of [_Shape Up_](https://basecamp.com/shapeup) by Ryan Singer from the free web edition, for reading on an e-reader (made for an Onyx Boox).

This is **not an official edition**. The text, images, and cover artwork belong to 37signals LLC. The scripts download them from basecamp.com each time you build. This repository does not include the book or the cover image. See [Credits and licenses](#credits-and-licenses).

## Quick start

```sh
uv sync                    # once: makes .venv and installs Pillow and the developer tools
uv run make_cover.py       # once: makes cover.jpg (needs Chrome, see below)
uv run build_epub.py       # writes shape-up.epub
epubcheck shape-up.epub    # optional: check the file
ebook-viewer shape-up.epub # optional: preview it in Calibre
```

A build takes about 30 seconds. To write the book somewhere else, give a path: `uv run build_epub.py ~/Books/shape-up.epub`.

## Requirements

| Tool | Used by | Needed for |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | you | installing Python, Pillow, and the developer tools |
| Google Chrome | `make_cover.py` | making the cover |
| `pdftoppm` (poppler-utils) | `make_cover.py` | making the cover |
| [EPUBCheck](https://www.w3.org/publishing/epubcheck/) | you | checking the file (optional) |
| [Calibre](https://calibre-ebook.com/) | you | previewing, sending to a device (optional) |

uv reads `pyproject.toml` and installs the exact versions in `uv.lock`: Python 3.12 or newer and [Pillow](https://python-pillow.org/). If you'd rather not use uv, install Pillow yourself and run the scripts with `python3`.

## Checking the code

Before you commit, run:

```sh
uv run black .         # format the code
uv run ruff check .    # find mistakes and old-style code (add --fix to repair most of them)
uv run pyright         # check the types
```

Settings for all three are in `pyproject.toml`. To format the Markdown files, run `bunx prettier --write --prose-wrap never "**/*.md"`.

## Files

| File | What it does |
| --- | --- |
| `build_epub.py` | Downloads every chapter and image, cleans the HTML, and packs the EPUB. |
| `images.py` | Gives see-through PNGs a white background, and turns animations into one still image. |
| `make_cover.py` | Makes `cover.jpg` from the title graphic on the web edition's home page. |
| `cover.jpg` | The cover used by `build_epub.py`. Not in the repository: you make it with `make_cover.py`. |
| `docs/considerations-for-great-epubs.md` | A checklist of what makes a good EPUB, and what this project does for each item. |
| `LICENSE` | The MIT license for the scripts and docs in this repository. |
| `pyproject.toml`, `uv.lock` | The project's dependencies, exact versions, and tool settings. |

## Making the cover

The cover is built from Basecamp's own artwork, so it isn't stored here. Make it once before your first build:

```sh
uv run make_cover.py       # writes cover.jpg next to the scripts
```

The script:

1. Opens [basecamp.com/shapeup](https://basecamp.com/shapeup) in headless Google Chrome and takes a sharp screenshot, so the site's own fonts are used.
2. Crops out the sketch, the title, the subtitle, and "by Ryan Singer".
3. Downloads the [official PDF](https://basecamp.com/shapeup/shape-up.pdf) and takes the Basecamp logo from its title page with `pdftoppm`.
4. Places both on a white 1600 × 2400 page and saves `cover.jpg`.

If Chrome isn't installed, `build_epub.py` stops with a message. You can also use any other tall image as `cover.jpg`. About 1600 × 2400 pixels works well.

`google-chrome` must be on your `PATH`. On Debian or Ubuntu, install poppler with `sudo apt install poppler-utils`.

## What the build does

1. **Finds the chapters.** It reads the table of contents from the sidebar of the web book, including the four parts.
2. **Cleans each chapter.** It keeps only the book text, and drops menus, icons, and buttons. It rewrites the HTML as strict XHTML, the format EPUB needs.
3. **Fixes links.** Links between chapters point inside the book. Each term marked in the text links to its Glossary entry.
4. **Fixes images.** All images stay at full quality. Images with see-through backgrounds get a white background, so they don't disappear in dark mode. The animated Hill Chart becomes its final still image, with a "Watch the animation online" link.
5. **Adds structure.** Each file is tagged as a foreword, chapter, part, appendix, or glossary, for readers and screen readers. The book also has landmarks, a nested table of contents, and an older-style table of contents (NCX) for older readers.
6. **Adds front pages and metadata.** It adds a title page and a copyright page that says where the book came from and what was changed. It also fills in the author, date, description, and accessibility information.
7. **Lays out pages.** The stylesheet keeps headings with their text, images with their captions, and glossary terms with their definitions. Body text is left-aligned (not justified) and hyphenated. Fonts and spacing are left to the reader.

For the full checklist behind these steps, with what was done and what was left out, see [Considerations for great EPUBs](docs/considerations-for-great-epubs.md).

## Putting it on an e-reader

- **Boox:** copy `shape-up.epub` into the `Books` folder over USB, or upload it with BooxDrop. NeoReader opens EPUB directly.
- **Kobo:** for better page counts and reading stats, convert it first: `ebook-convert shape-up.epub shape-up.kepub`.
- **Kindle:** upload the EPUB with Send to Kindle.
- **Readwise:** sign in at [readwise.io/books/upload](https://readwise.io/books/upload/) and upload the EPUB to your library, then read it in the Readwise app.

## Known limits

- **Built from the live site.** If Basecamp changes its page layout, the build may break. Look at `extract_content` and `parse_toc` in `build_epub.py` first.
- **No accessibility conformance claim.** The book has accessibility metadata, but it says nothing about meeting a standard such as WCAG AA, because it hasn't been audited with [DAISY Ace](https://daisy.github.io/ace/).
- **No print page numbers.** Page numbers aren't matched to the printed book.

## Credits and licenses

### The book

[_Shape Up: Stop Running in Circles and Ship Work that Matters_](https://basecamp.com/shapeup) is by **Ryan Singer**, with a foreword by **Jason Fried**. It is published free online by **[Basecamp](https://basecamp.com/)**. Copyright © 37signals LLC. All rights reserved.

The text, illustrations, diagrams, and image descriptions all come from the web edition. The cover is made from the web edition's title artwork and the Basecamp logo from the official PDF. None of these are in this repository, and none are covered by this repository's license. If you build the EPUB, it is for your own reading. Please don't share it. Point people to [basecamp.com/shapeup](https://basecamp.com/shapeup) instead.

This project isn't connected to, or approved by, Basecamp or 37signals.

### This repository

The scripts and docs are by Graham McGregor, under the [MIT license](LICENSE).

### Tools

The build relies on these projects. They aren't included here; you install them yourself.

- [Pillow](https://python-pillow.org/) for image processing ([MIT-CMU license](https://github.com/python-pillow/Pillow/blob/main/LICENSE))
- [Google Chrome](https://www.google.com/chrome/) and [Poppler](https://poppler.freedesktop.org/) for making the cover
- [EPUBCheck](https://www.w3.org/publishing/epubcheck/) from the W3C for checking the file
- [Calibre](https://calibre-ebook.com/) for previewing and converting

The accessibility metadata follows the W3C's [EPUB Accessibility 1.1](https://www.w3.org/TR/epub-a11y-11/) and the [DPUB-ARIA](https://www.w3.org/TR/dpub-aria-1.1/) roles.

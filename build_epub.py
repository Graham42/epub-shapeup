#!/usr/bin/env python3
"""Build an EPUB 3 of Shape Up (https://basecamp.com/shapeup) from the free web edition.

Usage: python3 build_epub.py [output.epub]
Requires Pillow; image processing lives in images.py next to this script (PNGs are flattened onto white for
dark-mode readers, animations become a still frame plus a link to the web page).
Run make_cover.py first to create cover.jpg next to this script.
"""
import html
from datetime import datetime, timezone
import re
import sys
import urllib.request
import uuid
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from images import flatten, is_animated, still_frame

BASE = "https://basecamp.com"
BOOK = BASE + "/shapeup"
COVER = Path(__file__).with_name("cover.jpg")  # made by make_cover.py
VOID = {"img", "br", "hr", "wbr", "source", "col"}
DROP = {"template", "svg", "button", "script", "style", "noscript"}
KEEP_ATTRS = {"id", "href", "src", "alt", "colspan", "rowspan", "start"}

CSS = """\
body { font-family: serif; line-height: 1.45; margin: 0 4%; }
h1 { font-size: 1.6em; margin: 1.5em 0 0.2em; }
h2 { font-size: 1.25em; margin: 1.6em 0 0.4em; }
h3 { font-size: 1.1em; }
.masthead { font-variant: small-caps; letter-spacing: 0.05em; margin-top: 2em; }
.part { text-align: center; margin-top: 30%; }
.cover { text-align: center; margin: 0; padding: 0; }
.cover img { max-height: 100%; }
img { max-width: 100%; height: auto; }
p > img:only-child { display: block; margin: 1em auto; }
blockquote { margin: 1em 1.5em; font-style: italic; }
.term { font-style: italic; }
a.term { color: inherit; text-decoration: underline dotted; }
.titlepage { text-align: center; margin-top: 25%; }
.titlepage h1 { font-size: 2.4em; margin-bottom: 0.2em; }
.titlepage .subtitle { font-size: 1.3em; margin-top: 0; }
.titlepage .author { margin-top: 2em; font-size: 1.2em; }
.titlepage .publisher { margin-top: 4em; font-variant: small-caps; letter-spacing: 0.05em; }
.copyright { font-size: 0.9em; margin-top: 2em; }
.copyright p { margin: 0 0 0.8em; }
figure { margin: 1em 0; text-align: center; }
figcaption { font-size: 0.9em; }
table { border-collapse: collapse; }
td, th { border: 1px solid #888; padding: 0.2em 0.4em; }
img.animation { display: block; margin: 1em auto 0.3em; }
.web-link { display: block; text-align: center; font-size: 0.9em; }
"""


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (epub-builder)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def slug_of(path: str) -> str:
    return path.rstrip("/").rsplit("/", 1)[-1]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", html.unescape(re.sub("<[^>]+>", "", text)).lower()).strip("-")


def semantics(slug: str, title: str) -> tuple[str, str]:
    """Return (matter, section type) for a content file, derived from its TOC slug and title."""
    if title == "Glossary":
        return "backmatter", "glossary"
    if "appendix" in slug:
        return "backmatter", "appendix"
    if title.startswith("Foreword"):
        return "frontmatter", "foreword"
    if title == "Acknowledgements":
        return "frontmatter", "acknowledgments"
    if "conclusion" in slug:
        return "bodymatter", "conclusion"
    if "chapter" in slug:
        return "bodymatter", "chapter"
    raise ValueError(f"no semantic type for {slug!r} ({title!r})")


def section(kind: str, body: str) -> str:
    """Wrap a file's content in a section labelled by its h1 (id="title")."""
    return f'<section epub:type="{kind}" role="doc-{kind}" aria-labelledby="title">\n{body}\n</section>'


def mark_glossary(body: str) -> str:
    """Tag glossary terms and definitions, giving each term a stable id."""
    body = re.sub(r"<dt>(.*?)</dt>", lambda m: f'<dt epub:type="glossterm" id="term-{slugify(m[1])}">{m[1]}</dt>',
                  body, flags=re.S)
    return body.replace("<dd>", '<dd epub:type="glossdef">')


def link_terms(body: str, glossary_file: str, term_ids: dict[str, str]) -> tuple[str, set[str]]:
    """Turn term markers into glossary links. Returns the new body and marker texts with no glossary entry.

    Markers don't always match the glossary headword ("scope" -> "Scopes", "raw idea" -> "Raw ideas",
    "cleanup" -> "Cleanup mode"), so try an exact or plural match, then a unique headword starting with the
    marker, then a unique headword containing it.
    """
    unmatched: set[str] = set()

    def find(text: str) -> str | None:
        key = html.unescape(text).lower()
        for form in (key, key + "s", key + "es"):
            if form in term_ids:
                return term_ids[form]
        for test in (str.startswith, str.__contains__):
            hits = [t for t in term_ids if test(t, key)]
            if len(hits) == 1:
                return term_ids[hits[0]]
        return None

    def repl(m: re.Match) -> str:
        term_id = find(m[1])
        if term_id is None:
            unmatched.add(m[1])
            return m[0]
        return f'<a class="term" epub:type="glossref" href="{glossary_file}#{term_id}">{m[1]}</a>'

    return re.sub(r'<span class="term">(.*?)</span>', repl, body), unmatched


class Xhtmlizer(HTMLParser):
    """Re-serialize a web-book HTML fragment as clean XHTML, downloading images."""

    def __init__(self, slug: str, slugs: set[str], images: dict[str, tuple[str, bytes, bool]]):
        super().__init__(convert_charrefs=True)
        self.slug, self.slugs, self.images = slug, slugs, images
        self.out: list[str] = []
        self.stack: list[str] = []  # emitted open tags, for closing
        self.drop_depth = 0
        self.section = ""  # id of the latest <h2 id>, for links back to the web page

    def _attrs(self, attrs) -> str:
        parts = []
        for k, v in attrs:
            if k not in KEEP_ATTRS or v is None:
                continue
            if k == "href":
                v = self._link(v)
            parts.append(f' {k}="{html.escape(v, quote=True)}"')
        return "".join(parts)

    def _img(self, attrs) -> str:
        a = dict(attrs)
        if not a.get("src"):
            return ""
        a["src"], animated = self._image(a["src"])
        a["alt"] = a.get("alt") or ""
        if not animated:
            return f"<img{self._attrs(a.items())}/>"
        a["alt"] = "Still image from an animation. " + a["alt"]
        web = f"{BOOK}/{self.slug}" + (f"#{self.section}" if self.section else "")
        return (f'<img{self._attrs(a.items())} class="animation"/>'
                f'<a class="web-link" href="{html.escape(web, quote=True)}">Watch the animation online</a>')

    def _void(self, tag: str, attrs) -> str:
        return self._img(attrs) if tag == "img" else f"<{tag}{self._attrs(attrs)}/>"

    def _image(self, src: str) -> tuple[str, bool]:
        """Download an image once; return its EPUB path and whether it was an animation."""
        url = src if src.startswith("http") else BASE + src
        if url not in self.images:
            print(f"image {url}", file=sys.stderr)
            data = fetch(url)
            suffix = PurePosixPath(url.split("?")[0]).suffix.lower()
            animated = is_animated(data)
            if animated:
                data, suffix = still_frame(data), ".png"
            elif suffix == ".png":
                data = flatten(data)
            self.images[url] = (f"images/{len(self.images):03d}{suffix}", data, animated)
        name, _, animated = self.images[url]
        return "../" + name, animated

    def _link(self, href: str) -> str:
        m = re.match(r"^(?:https://basecamp\.com)?/shapeup/([^#?]+)(#.*)?$", href)
        if m and m.group(1) in self.slugs:
            return f"{m.group(1)}.xhtml{m.group(2) or ''}"
        if href.startswith("/"):
            return BASE + href
        return href

    def handle_starttag(self, tag, attrs):
        if self.drop_depth or tag in DROP:
            if tag not in VOID:
                self.drop_depth += 1
            return
        cls = dict(attrs).get("class") or ""
        if tag == "code" and "language-plaintext" in cls:
            # Glossary terms are marked up as inline code on the site.
            self.out.append('<span class="term">')
            self.stack.append("span")
            return
        if tag == "h2" and dict(attrs).get("id"):
            self.section = dict(attrs)["id"]
        if tag in VOID:
            self.out.append(self._void(tag, attrs))
        else:
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self.drop_depth or tag in DROP:
            return
        if tag in VOID:
            self.out.append(self._void(tag, attrs))
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.drop_depth:
            self.drop_depth -= 1
            return
        if self.stack:
            self.out.append(f"</{self.stack.pop()}>")

    def handle_data(self, data):
        if not self.drop_depth:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def page(title: str, body: str, matter: str = "") -> str:
    body_type = f' epub:type="{matter}"' if matter else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">\n'
        f'<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
        '<link rel="stylesheet" type="text/css" href="../style.css"/></head>\n'
        f"<body{body_type}>\n{body}\n</body>\n</html>\n"
    )


def parse_toc(index_html: str):
    """Return [(part_title, [(slug, chapter_number_label, title), ...]), ...] from the sidebar TOC."""
    toc_html = index_html[index_html.index('<div class="toc">'):]
    parts = []
    for block in re.split(r'<div class="toc__part">', toc_html)[1:]:
        pt = re.search(r'toc__part-title[^"]*"[^>]*>([^<]+)<', block)
        chapters = []
        for li in re.split(r'<li class="toc__chapter">', block)[1:]:
            num = re.search(r'toc__chapter-number">([^<]+)<', li)
            link = re.search(r'toc__chapter-title"><a href="([^"]+)">([^<]+)<', li)
            if link:
                chapters.append((slug_of(link.group(1)), html.unescape(num.group(1)) if num else "", html.unescape(link.group(2))))
        parts.append((html.unescape(pt.group(1)) if pt else "", chapters))
    return parts


def extract_content(doc: str) -> str:
    # Attribute values contain ">" (e.g. data-action="click->..."), so match quoted attributes explicitly.
    start = re.search(r'<div class="content"(?:\s+[\w-]+="[^"]*")*\s*>', doc).end()
    end = doc.index('<nav class="pagination', start)
    return doc[start:end]


def main(out_path: str) -> None:
    first = fetch(BOOK + "/0.1-foreword").decode("utf-8")
    parts = parse_toc(first)
    slugs = {s for _, chs in parts for s, _, _ in chs}
    images: dict[str, tuple[str, bytes, bool]] = {}
    files: dict[str, bytes] = {}
    spine: list[str] = ["text/cover.xhtml", "text/titlepage.xhtml", "text/copyright.xhtml", "text/nav.xhtml"]
    first_of: dict[str, str] = {}  # section type -> first slug of that type, for landmarks
    nav_items: list[str] = []
    ncx_points: list[str] = []
    order = 0

    def ncx(label: str, src: str, children: str = "") -> str:
        nonlocal order
        order += 1
        return (f'<navPoint id="np{order}" playOrder="{order}"><navLabel><text>{html.escape(label)}</text></navLabel>'
                f'<content src="{src}"/>{children}</navPoint>')

    for pi, (part_title, chapters) in enumerate(parts):
        chapter_nav, chapter_ncx = [], []
        part_file = None
        if part_title and part_title != "Preface":
            part_file = f"text/part-{pi}.xhtml"
            matter = semantics(chapters[0][0], chapters[0][2])[0]
            heading = f'<h1 class="part" id="title">{html.escape(part_title)}</h1>'
            files[part_file] = page(part_title, section("part", heading), matter).encode()
            spine.append(part_file)
        for slug, num, title in chapters:
            print(f"fetching {slug}", file=sys.stderr)
            doc = fetch(f"{BOOK}/{slug}").decode("utf-8")
            conv = Xhtmlizer(slug, slugs, images)
            conv.feed(extract_content(doc))
            conv.close()
            matter, kind = semantics(slug, title)
            first_of.setdefault(kind, slug)
            body = conv.result()
            if kind == "glossary":
                body = mark_glossary(body)
            head = (f'<p class="masthead">{html.escape(num)}</p>' if num else "") + f'<h1 id="title">{html.escape(title)}</h1>'
            fname = f"text/{slug}.xhtml"
            files[fname] = page(title, section(kind, head + "\n" + body), matter).encode()
            spine.append(fname)
            label = f"{num}: {title}" if num else title
            sections = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', files[fname].decode())
            sec_nav = "".join(f'<li><a href="{slug}.xhtml#{sid}">{re.sub("<[^>]+>", "", t)}</a></li>' for sid, t in sections)
            chapter_nav.append(f'<li><a href="{slug}.xhtml">{html.escape(label)}</a>' + (f"<ol>{sec_nav}</ol>" if sec_nav else "") + "</li>")
            sec_ncx = "".join(ncx(html.unescape(re.sub("<[^>]+>", "", t)), f"text/{slug}.xhtml#{sid}") for sid, t in sections)
            chapter_ncx.append(ncx(label, f"text/{slug}.xhtml", sec_ncx))
        if part_file:
            nav_items.append(f'<li><a href="part-{pi}.xhtml">{html.escape(part_title)}</a><ol>{"".join(chapter_nav)}</ol></li>')
            ncx_points.append(ncx(part_title, part_file, "".join(chapter_ncx)))
        else:
            nav_items.extend(chapter_nav)
            ncx_points.extend(chapter_ncx)

    glossary_file = f'{first_of["glossary"]}.xhtml'
    glossary = files["text/" + glossary_file].decode()
    term_ids = {html.unescape(t).lower(): i for i, t in re.findall(r'<dt epub:type="glossterm" id="([^"]+)">(.*?)</dt>', glossary)}
    unmatched: set[str] = set()
    for name in spine:
        if name.startswith("text/") and name in files and name != "text/" + glossary_file:
            body, missing = link_terms(files[name].decode(), glossary_file, term_ids)
            files[name] = body.encode()
            unmatched |= missing
    if unmatched:
        print(f"glossary: no entry for {sorted(unmatched)}", file=sys.stderr)

    built = datetime.now(timezone.utc)

    for name, data, _ in images.values():
        files[name] = data
    files["images/cover.jpeg"] = COVER.read_bytes()
    files["text/cover.xhtml"] = page(
        "Shape Up",
        '<section epub:type="cover" class="cover">'
        '<img role="doc-cover" src="../images/cover.jpeg" alt="Shape Up by Ryan Singer"/></section>',
        "frontmatter",
    ).encode()
    files["text/titlepage.xhtml"] = page(
        "Title Page",
        '<section epub:type="titlepage" class="titlepage" aria-label="Title page">'
        '<h1>Shape Up</h1><p class="subtitle">Stop Running in Circles and Ship Work that Matters</p>'
        '<p class="author">Ryan Singer</p><p>Foreword by Jason Fried</p>'
        '<p class="publisher">Basecamp</p></section>',
        "frontmatter",
    ).encode()
    files["text/copyright.xhtml"] = page(
        "Copyright",
        '<section epub:type="copyright-page" class="copyright" aria-label="Copyright">'
        "<p><em>Shape Up: Stop Running in Circles and Ship Work that Matters</em><br/>by Ryan Singer</p>"
        "<p>Copyright © 37signals LLC. All rights reserved.</p>"
        "<p>First published as a free web book by Basecamp in July 2019. A print edition is sold at "
        '<a href="https://basecamp-goods.com/products/shapeup">basecamp-goods.com</a>.</p>'
        "<p>This EPUB is not an official edition. It was made for personal reading from the free web edition at "
        f'<a href="{BOOK}">{BOOK.removeprefix("https://")}</a>, '
        f"downloaded on {built:%-d %B %Y}. The text and images are unchanged, except that:</p>"
        "<ul><li>Images with see-through backgrounds were given white backgrounds so they show up in dark mode.</li>"
        "<li>The animated Hill Chart shows one still image, with a link to the animation online.</li>"
        "<li>Terms in the text link to their entries in the Glossary.</li>"
        "<li>The cover was made from the title graphic on the web edition’s home page.</li></ul>"
        "</section>",
        "frontmatter",
    ).encode()
    start = f'{first_of["chapter"]}.xhtml'
    landmarks = (
        '<nav epub:type="landmarks" id="landmarks" hidden=""><h2>Landmarks</h2><ol>'
        '<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>'
        '<li><a epub:type="titlepage" href="titlepage.xhtml">Title Page</a></li>'
        '<li><a epub:type="copyright-page" href="copyright.xhtml">Copyright</a></li>'
        '<li><a epub:type="toc" href="#toc">Contents</a></li>'
        f'<li><a epub:type="bodymatter" href="{start}">Start of Reading</a></li>'
        f'<li><a epub:type="glossary" href="{first_of["glossary"]}.xhtml">Glossary</a></li>'
        "</ol></nav>"
    )
    files["text/nav.xhtml"] = page(
        "Contents",
        f'<nav epub:type="toc" role="doc-toc" id="toc"><h1>Contents</h1><ol>{"".join(nav_items)}</ol></nav>\n{landmarks}',
        "frontmatter",
    ).encode()
    files["style.css"] = CSS.encode()

    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, BOOK)}"
    files["toc.ncx"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f'<head><meta name="dtb:uid" content="{book_id}"/></head><docTitle><text>Shape Up</text></docTitle>'
        f'<navMap>{"".join(ncx_points)}</navMap></ncx>'
    ).encode()

    media = {".xhtml": "application/xhtml+xml", ".css": "text/css", ".jpeg": "image/jpeg", ".jpg": "image/jpeg",
             ".png": "image/png", ".gif": "image/gif", ".svg": "image/svg+xml", ".ncx": "application/x-dtbncx+xml"}
    ids = {name: f"f{i}" for i, name in enumerate(files)}
    manifest = []
    for name in files:
        props = {"text/nav.xhtml": ' properties="nav"', "images/cover.jpeg": ' properties="cover-image"'}.get(name, "")
        manifest.append(f'<item id="{ids[name]}" href="{name}" media-type="{media[PurePosixPath(name).suffix]}"{props}/>')
    spine_xml = "".join(f'<itemref idref="{ids[n]}"/>' for n in spine)
    guide = (
        '<guide><reference type="cover" title="Cover" href="text/cover.xhtml"/>'
        '<reference type="title-page" title="Title Page" href="text/titlepage.xhtml"/>'
        '<reference type="copyright-page" title="Copyright" href="text/copyright.xhtml"/>'
        '<reference type="toc" title="Contents" href="text/nav.xhtml"/>'
        f'<reference type="text" title="Start of Reading" href="text/{start}"/></guide>'
    )
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="bookid">{book_id}</dc:identifier>'
        '<dc:title id="title">Shape Up</dc:title>'
        '<meta refines="#title" property="title-type">main</meta>'
        '<dc:title id="subtitle">Stop Running in Circles and Ship Work that Matters</dc:title>'
        '<meta refines="#subtitle" property="title-type">subtitle</meta>'
        '<dc:creator id="author">Ryan Singer</dc:creator>'
        '<meta refines="#author" property="role" scheme="marc:relators">aut</meta>'
        '<meta refines="#author" property="file-as">Singer, Ryan</meta>'
        '<dc:contributor id="foreword">Jason Fried</dc:contributor>'
        '<meta refines="#foreword" property="role" scheme="marc:relators">aui</meta>'
        '<dc:language>en</dc:language><dc:publisher>Basecamp</dc:publisher>'
        # Web edition announced 2019-07-10: https://signalvnoise.com/svn3/announcing-shape-up-a-deep-dive-into-how-we-work/
        '<dc:date>2019-07-10</dc:date>'
        '<dc:description>Shape Up will help you break free of “best practices” that aren’t really working, '
        'think deeper about the right problems, and start shipping meaningful projects your team can celebrate.'
        '</dc:description>'
        '<dc:subject>Software development</dc:subject><dc:subject>Product management</dc:subject>'
        '<dc:subject>Project management</dc:subject>'
        '<dc:rights>Copyright © 37signals LLC. All rights reserved.</dc:rights>'
        f'<dc:source>{BOOK}</dc:source>'
        f'<meta property="dcterms:modified">{built:%Y-%m-%dT%H:%M:%SZ}</meta>'
        # EPUB Accessibility 1.1 discovery metadata. No dcterms:conformsTo: that claim needs an audit (e.g. DAISY Ace).
        '<meta property="schema:accessMode">textual</meta><meta property="schema:accessMode">visual</meta>'
        '<meta property="schema:accessModeSufficient">textual,visual</meta>'
        '<meta property="schema:accessModeSufficient">textual</meta>'
        '<meta property="schema:accessibilityFeature">alternativeText</meta>'
        '<meta property="schema:accessibilityFeature">structuralNavigation</meta>'
        '<meta property="schema:accessibilityFeature">tableOfContents</meta>'
        '<meta property="schema:accessibilityFeature">readingOrder</meta>'
        '<meta property="schema:accessibilityFeature">displayTransformability</meta>'
        '<meta property="schema:accessibilityHazard">none</meta>'
        '<meta property="schema:accessibilitySummary">Every image has a text description, so the book can be read '
        "fully as text. Chapters and sections use real headings, and the table of contents links to each one. "
        "Text reflows and can be resized. Glossary terms link to their definitions. There is no sound, flashing "
        "or motion: the one animation is shown as a still image with a link to view it online.</meta>"
        f'<meta name="cover" content="{ids["images/cover.jpeg"]}"/></metadata>'
        f'<manifest>{"".join(manifest)}</manifest><spine toc="{ids["toc.ncx"]}">{spine_xml}</spine>{guide}</package>'
    )
    container = (
        '<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in files.items():
            z.writestr("OEBPS/" + name, data, compress_type=zipfile.ZIP_DEFLATED)
    print(f"wrote {out_path}: {len(spine)} spine items, {len(images)} images", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shape-up.epub")

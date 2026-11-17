# Considerations for great EPUBs

A checklist for turning a free web or PDF book into an EPUB that reads well on an e-reader. Each item says why it matters, and whether this project does it.

**Status key:** ✅ done · ❌ not done · ⛔ left out on purpose

## Choosing a source

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Build from HTML, not PDF** | HTML already has headings, paragraphs and image descriptions, so the text reflows cleanly. A PDF stores text at fixed places on a page. Converting it often leaves broken lines, page numbers and headers in the text. Use a PDF only when nothing else exists. | ✅ Built from the web edition. |
| **Check for an official EPUB first** | An official edition is usually better and supports the author. | ✅ Checked: Basecamp offers only the web edition and a PDF. |
| **Don't commit the book** | The text and images belong to the publisher. Keep the build script in git, not the output. | ✅ `*.epub` is in `.gitignore`. |

## Validity

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Pass EPUBCheck with no errors or warnings** | Some stores and services (for example Send to Kindle) reject files that fail it. Readers may also show broken pages. | ✅ 0 errors, 0 warnings. |
| **Use strict XHTML** | EPUB pages must be well-formed XML. Web HTML often isn't. | ✅ Every page is re-written as XHTML. |
| **Avoid CSS that EPUBCheck can't parse** | EPUBCheck rejects some newer CSS, such as `:has()`. | ✅ A class (`p.image`) is used instead. |

## Navigation

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Nested table of contents** | Lets readers jump to parts, chapters and sections. | ✅ Parts → chapters → sections. |
| **Older table of contents (NCX)** | Older readers use this instead of the EPUB 3 contents page. | ✅ Included. |
| **Landmarks** | A short list of key places (cover, contents, start of reading, glossary) used by "Go to beginning" and similar menus. | ✅ Included, plus the older `<guide>` list. |
| **Links stay inside the book** | Links between chapters should open the chapter in the book, not the website. | ✅ Rewritten to point inside the book. |
| **Glossary terms link to definitions** | Replaces the web book's hover-to-define feature. Some readers show the definition as a pop-up. | ✅ 65 links to 24 glossary entries. |

## Structure and accessibility

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Real headings** | Screen readers and reader menus use headings to move around the book. | ✅ |
| **Semantic tags** (`epub:type`, DPUB-ARIA roles) | Mark each file as a foreword, chapter, part, appendix or glossary. Readers and screen readers use them. | ✅ |
| **Image descriptions** (alt text) | Lets people who can't see images, or who use text-only modes, follow the book. | ✅ Every image has one, from Basecamp. |
| **Accessibility metadata** | Tells stores and readers how the book can be read: as text, with images described, with a table of contents, with no hazards. | ✅ EPUB Accessibility 1.1 discovery fields. |
| **Formal conformance claim** (for example WCAG AA) | Only add this after an audit, such as with [DAISY Ace](https://daisy.github.io/ace/). | ❌ No audit done, so no claim. |

## Images

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Keep full quality** | E-reader storage is rarely a problem. Recompressing makes diagrams and screenshots blurry. | ✅ Original files, no recompression. |
| **No see-through backgrounds** | In dark mode, black lines on a see-through background disappear against a black page. Put them on solid white. | ✅ 21 PNGs given white backgrounds. |
| **No animations** | E-ink shows only the first frame, which may look broken. Use one clear still frame, say so in the description, and link to the animation online. | ✅ The Hill Chart animation is now a still image with a link. |
| **Tall images fit the screen** | A tall image can run off the page. | ✅ Limited to 95% of the screen height. |

## Page layout

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Keep headings with their text** | A heading alone at the bottom of a page is confusing. | ✅ |
| **Keep images with their captions** | A caption on the next page is hard to match to its image. | ✅ |
| **Avoid single stray lines** | One line of a paragraph alone at the top or bottom of a page (widows and orphans). | ✅ |
| **Choose the text alignment** | If the book doesn't set one, many readers justify text. On a narrow screen that can leave wide gaps between words. Left-aligned text is easier for many people to read. | ✅ Left-aligned. |
| **Hyphenate body text** | Gives more even lines on a narrow screen. Never hyphenate headings. | ✅ |
| **Let the reader choose fonts and spacing** | People set their e-reader the way they like. The stylesheet should add structure, not force a look. | ✅ |
| **Don't embed licensed fonts** | Many fonts, including the web edition's FF Meta Serif, need a paid licence. | ⛔ Left out. |

Readers follow layout CSS unevenly. A reader that ignores a rule just lays out the page as if the rule weren't there, so these rules can't break anything. Test on your own device.

## Front matter and metadata

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **A tall cover image** | Libraries show the cover as a thumbnail. A wide image shows as a thin strip. About 1600 × 2400 is a good size. | ✅ Made from the web edition's title graphic. |
| **Title page** | Shows the title, subtitle, author and publisher inside the book. | ✅ |
| **Copyright page** | States the rights, the source, and that the file is unofficial. Lists every change made. | ✅ |
| **Full metadata** | Title, subtitle, author (with a sort name), contributors, publisher, date, description, subjects, language, rights and source. Readers use these for sorting and search. | ✅ No ISBN, since none could be confirmed. |

## Optional extras

| Consideration | Why it matters | Status |
| --- | --- | --- |
| **Print page numbers** (a page list) | Lets you cite pages, or read alongside someone with the paper copy. Takes a lot of work: the text must be matched to the printed pages. | ❌ Not needed for now. |
| **Device-specific formats** | Kobo reads KEPUB better (page counts, reading stats). Calibre can convert to it. | ❌ Not built by default. See the README. |

## Testing

1. Run `epubcheck` on every build.
2. Preview in Calibre: `ebook-viewer shape-up.epub`.
3. To check page breaks, convert to a PDF at your screen size: `ebook-convert shape-up.epub layout.pdf --custom-size 1404x1872 --unit devicepixel`
4. Finally, read a few chapters on the real device, in both light and dark mode. This is the only test that really proves the book works.

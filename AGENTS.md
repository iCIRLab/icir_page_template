# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, Copilot, Cursor, etc.) when working with code in this repository.

## What this is

A template for iCIR Lab project pages. Researchers edit `content.yaml`; `build.py` renders `docs/index.html`, which GitHub Pages serves from `main` `/docs`. The README (Korean) is the user guide.

## Commands

```sh
python3 build.py            # write docs/index.html (needs PyYAML)
python3 build.py --check    # exit 1 if docs/index.html is stale
python3 build.py --serve    # build, then preview at http://localhost:8000/
```

There are no tests; verify by building and viewing the page in a browser at desktop and phone widths, in each configured language.

## Architecture

- **Generated vs. static.** Only `docs/index.html` is generated. `docs/assets/site.css` and `site.js` are hand-edited and shared by every section; `build.py` appends a content hash (`?v=`) to their URLs.
- **Validation lives in `build.py`.** `SCHEMA` lists allowed keys per object (unknown keys are errors), `Page.text()` resolves a value that is either a string or a `{en, ko}` mapping and errors on a missing translation, and missing media files are collected and reported together. A new field or section type must be added to `SCHEMA` (and `SECTION_TYPES`).
- **Two kinds of localized markup.** Content inside `#content-<lang>` panels is rendered once per language (`Page.panel`). Copy outside the panels (title, authors, links, demo) is rendered by `Page.shared()` as sibling elements with `data-lang`, toggled by `site.js`.
- **Ids the JS depends on.** Section headings are `<id>-title-<lang>` and nav links carry `data-section="<id>-title"`; `site.js` rewrites nav hrefs/text from those headings and maps the reading position across languages via each section's `aria-labelledby`. Keep this pattern for any new section type.
- **Single-language pages** omit `#language-toggle`; `site.js` treats it as optional and derives the language list from the panels.
- Text values are inserted as inline HTML (attributes use `attr()`, which strips tags); `external_links()` adds `target="_blank"` to absolute links.

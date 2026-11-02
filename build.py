#!/usr/bin/env python3
"""Generate docs/index.html from content.yaml.

Usage:
  python3 build.py            write docs/index.html
  python3 build.py --check    exit 1 if docs/index.html is out of date
  python3 build.py --serve    write, then preview at http://localhost:8000/

Text values are either a plain string (shared by every language) or a mapping
such as {en: ..., ko: ...}. Text may contain inline HTML (<a>, <strong>, <em>, <br>).
docs/assets/site.css and site.js are static and are not generated.
"""
import argparse
import functools
import hashlib
import html
import http.server
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: sudo apt install python3-yaml  (or: pip install pyyaml)")

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content.yaml"
DOCS = ROOT / "docs"
PAGE = DOCS / "index.html"
LANGUAGES = ("en", "ko")
VIDEO_TYPES = {".mp4": "video/mp4", ".webm": "video/webm"}
SECTION_TYPES = ("abstract", "overview", "cases", "text")

# Allowed keys per object; anything else is reported as a likely typo.
COMMON = {"type", "id", "kicker", "title", "intro", "band"}
SCHEMA = {
    "page": {"languages", "lab", "title", "authors", "affiliations", "links", "demo", "sections"},
    "lab": {"name", "url", "logo"},
    "author": {"name", "url", "affiliations"},
    "link": {"label", "url", "icon"},
    "demo": {"title", "media", "intro", "note"},
    "abstract": COMMON | {"body"},
    "text": COMMON | {"body", "media", "caption", "note"},
    "cases": COMMON | {"summary", "note", "label", "meta", "items"},
    "case": {"media", "title", "text", "meta"},
    "overview": COMMON | {"flow", "media", "caption"},
    "stage": {"arrow", "title", "text", "tag", "loop", "feedback", "outcome"},
    "step": {"title", "text"},
    "outcome": {"tag", "title", "text"},
}
DEFAULT_TITLES = {
    "demo": {"en": "Demo Video", "ko": "데모 영상"},
    "abstract": {"en": "Abstract", "ko": "초록"},
    "overview": {"en": "System overview", "ko": "시스템 개요"},
    "cases": {"en": "Case videos", "ko": "케이스별 영상"},
}
# Sections with a full-width tinted background unless `band` says otherwise.
DEFAULT_BAND = {"cases": True, "overview": True}
ICONS = {
    "code": "m7 7-5 5 5 5M17 7l5 5-5 5M14 4l-4 16",
    "paper": "M14 3H6v18h12V7zM14 3v4h4M9 12h6M9 16h6",
    "video": "M3 6h12v12H3zM15 10l6-3v10l-6-3",
    "data": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
    "link": "M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
}
ARROW_DOWN = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3v17m-5-5 5 5 5-5"/></svg>'
ARROW_RIGHT = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 12h17m-5-5 5 5-5 5"/></svg>'
NEW_TAB = 'target="_blank" rel="noopener noreferrer"'


class ContentError(Exception):
    pass


def check_keys(obj, kind, path):
    if not isinstance(obj, dict):
        raise ContentError(f"{path}: expected a mapping")
    unknown = sorted(set(obj) - SCHEMA[kind])
    if unknown:
        raise ContentError(f"{path}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(sorted(SCHEMA[kind]))}")


def require(obj, key, path):
    if obj.get(key) in (None, ""):
        raise ContentError(f"{path}.{key} is required")
    return obj[key]


def plain(markup):
    """Text without tags, for attributes and the document title."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup)).strip()


def attr(markup):
    return html.escape(plain(markup), quote=True)


def external_links(markup):
    # Inline links to other sites open in a new tab, like the page's buttons.
    return re.sub(r'<a (href="https?://[^"]*")(?![^>]*\btarget=)', rf"<a \1 {NEW_TAB}", markup)


class Page:
    def __init__(self, data):
        check_keys(data, "page", "content.yaml")
        self.data = data
        self.languages = data.get("languages") or ["en"]
        if (not isinstance(self.languages, list) or len(set(self.languages)) != len(self.languages)
                or not set(self.languages) <= set(LANGUAGES)):
            raise ContentError(f"languages must list one or both of {', '.join(LANGUAGES)} (first is the default)")
        self.default = self.languages[0]
        self.media_errors = []
        self.section_ids = []
        for index, section in enumerate(data.get("sections") or []):
            path = f"sections[{index}]"
            kind = require(section, "type", path)
            if kind not in SECTION_TYPES:
                raise ContentError(f"{path}.type: unknown section type {kind!r}; use {', '.join(SECTION_TYPES)}")
            check_keys(section, kind, path)
            sid = str(section.get("id") or kind)
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
                raise ContentError(f"{path}.id: use lowercase letters, digits and hyphens")
            base, n = sid, 2
            while sid in self.section_ids:
                sid, n = f"{base}-{n}", n + 1
            self.section_ids.append(sid)

    # Text --------------------------------------------------------------

    def text(self, value, lang, path):
        if isinstance(value, dict):
            if lang not in value or value[lang] in (None, ""):
                raise ContentError(f"{path}: missing {lang!r} text")
            value = value[lang]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ContentError(f"{path}: expected text (quote values such as yes/no/on/off)")
        return external_links(str(value).strip())

    def paragraphs(self, value, lang, path):
        blocks = re.split(r"\n\s*\n", self.text(value, lang, path))
        return "\n".join(f"<p>{' '.join(block.split())}</p>" for block in blocks if block.strip())

    def shared(self, value, path, tag="span", cls=""):
        """Copy outside the language panels: one element per language, toggled by site.js."""
        texts = {lang: self.text(value, lang, path) for lang in self.languages}
        cls = f' class="{cls}"' if cls else ""
        if len(set(texts.values())) == 1 and tag == "span":
            return texts[self.default]
        return "".join(
            f'<{tag}{cls} data-lang="{lang}"{"" if lang == self.default else " hidden"}>{texts[lang]}</{tag}>'
            for lang in self.languages)

    def nav_labels(self, value, path):
        labels = {lang: plain(self.text(value, lang, path)) for lang in self.languages}
        data = "".join(f' data-label-{lang}="{html.escape(label)}"' for lang, label in labels.items())
        return data, html.escape(labels[self.default])

    # Media -------------------------------------------------------------

    def media(self, src, label, path, media_class=""):
        src = str(src)
        if not (src.startswith(("http://", "https://")) or (DOCS / src).is_file()):
            self.media_errors.append(f"{path}: docs/{src} not found")
        suffix = Path(src).suffix.lower()
        cls = f' class="{media_class}"' if media_class else ""
        if suffix in VIDEO_TYPES:
            return (f'<video{cls} controls autoplay loop muted playsinline preload="metadata" aria-label="{attr(label)}">'
                    f'<source src="{html.escape(src)}" type="{VIDEO_TYPES[suffix]}"><a href="{html.escape(src)}">MP4</a></video>')
        return f'<img{cls} src="{html.escape(src)}" alt="{attr(label)}" loading="lazy">'

    @functools.cache
    def asset(self, path):
        # Content hash in the URL so browsers pick up edited styles and scripts.
        digest = hashlib.sha1((DOCS / path).read_bytes()).hexdigest()[:8]
        return f"{path}?v={digest}"

    # Page --------------------------------------------------------------

    def render(self):
        d = self.data
        title = require(d, "title", "content.yaml")
        page = f"""<!DOCTYPE html>
<html lang="{self.default}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Generated by build.py from content.yaml. Edit content.yaml and rebuild instead of editing this file. -->
    <title>{html.escape(plain(self.text(title, self.default, "title")))}</title>
    <link href="https://fonts.googleapis.com/css?family=Google+Sans:400,600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{self.asset("assets/site.css")}">
    <script defer src="{self.asset("assets/site.js")}"></script>
</head>

<body>
{self.site_header()}
    <main>
        <header>
            <h1 class="publication-title" id="publication-title">{self.shared(title, "title")}</h1>
{self.byline()}
{self.links()}
        </header>
{self.demo()}
        <hr class="section-divider">
        <div id="project-content">
            <span class="sr-only" id="language-status" role="status" aria-live="polite"></span>
{"".join(self.panel(lang) for lang in self.languages)}        </div>
    </main>
</body>
</html>
"""
        if self.media_errors:
            # Each language panel renders the same media, so report each file once.
            raise ContentError("missing media files:\n  " + "\n  ".join(dict.fromkeys(self.media_errors)))
        return page

    def site_header(self):
        lab = self.data.get("lab") or {}
        check_keys(lab, "lab", "lab")
        name = html.escape(str(lab.get("name", "iCIR Lab")))
        url = html.escape(str(lab.get("url", "https://sites.google.com/view/icir-lab/%ED%99%88")))
        logo = str(lab.get("logo", "assets/lab-logo.png"))
        if not (DOCS / logo).is_file():
            self.media_errors.append(f"lab.logo: docs/{logo} not found")
        items = ['<li><a href="#publication-title" data-label-en="Top" data-label-ko="맨 위">{}</a></li>'.format(
            "맨 위" if self.default == "ko" else "Top")]
        if self.data.get("demo"):
            labels, label = self.nav_labels(self.data["demo"].get("title") or DEFAULT_TITLES["demo"], "demo.title")
            items.append(f'<li><a href="#demo-title"{labels}>{label}</a></li>')
        for index, (section, sid) in enumerate(zip(self.data.get("sections") or [], self.section_ids)):
            heading = plain(self.text(self.section_title(section, index), self.default, f"sections[{index}].title"))
            items.append(f'<li><a href="#{sid}-title-{self.default}" data-section="{sid}-title">{html.escape(heading)}</a></li>')
        toggle = ""
        if len(self.languages) == 2:
            toggle = """
                <button class="language-switch" id="language-toggle" type="button" data-language="en"
                        aria-label="Current content language: English. Switch to Korean."
                        title="한국어로 전환" aria-controls="content-en content-ko">
                    <span lang="en" aria-hidden="true">EN</span>
                    <span lang="ko" aria-hidden="true">한국어</span>
                </button>"""
        nav = "\n".join(f"                    {item}" for item in items)
        return f"""    <header class="site-header">
        <div class="top-nav">
            <a class="lab-brand" href="{url}" {NEW_TAB} aria-label="{name} (opens in a new tab)">
                <img src="{html.escape(logo)}" alt="{name}">
            </a>
            <button class="menu-toggle" id="section-menu-toggle" type="button" hidden
                    aria-controls="section-navigation" aria-expanded="false" aria-label="Open section menu">
                <svg class="menu-open-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
                <svg class="menu-close-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 6 12 12M18 6 6 18"/></svg>
            </button>
            <nav class="section-nav" id="section-navigation" aria-label="Page sections" lang="{self.default}">
                <ul>
{nav}
                </ul>
            </nav>
            <div class="top-nav-controls">{toggle}
            </div>
        </div>
    </header>"""

    def byline(self):
        authors = self.data.get("authors") or []
        affiliations = self.data.get("affiliations") or []
        numbered = any(isinstance(a, dict) and a.get("affiliations") for a in authors)
        names = []
        for index, author in enumerate(authors):
            path = f"authors[{index}]"
            check_keys(author, "author", path)
            name = self.shared(require(author, "name", path), f"{path}.name")
            if author.get("url"):
                name = f'<a href="{html.escape(str(author["url"]))}" {NEW_TAB}>{name}</a>'
            marks = ",".join(str(n) for n in author.get("affiliations") or [])
            names.append(f"<li>{name}{f'<sup>{marks}</sup>' if marks else ''}</li>")
        lines = [f"<p>{f'<sup>{n}</sup>' if numbered else ''}{self.shared(line, f'affiliations[{n - 1}]')}</p>"
                 for n, line in enumerate(affiliations, 1)]
        out = ""
        if names:
            out += f'            <ul class="publication-authors" aria-label="Authors">{"".join(names)}</ul>\n'
        if lines:
            out += f'            <div class="publication-affiliations">{"".join(lines)}</div>'
        return out

    def links(self):
        buttons = []
        for index, link in enumerate(self.data.get("links") or []):
            path = f"links[{index}]"
            check_keys(link, "link", path)
            icon = link.get("icon", "link")
            if icon not in ICONS:
                raise ContentError(f"{path}.icon: use one of {', '.join(ICONS)}")
            label = require(link, "label", path)
            buttons.append(
                f'<a class="code-link" href="{html.escape(str(require(link, "url", path)))}" {NEW_TAB}>'
                f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
                f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="{ICONS[icon]}"/></svg>'
                f'<span>{self.shared(label, f"{path}.label")}</span></a>')
        return f'            <div class="publication-links">{"".join(buttons)}</div>' if buttons else ""

    def demo(self):
        demo = self.data.get("demo")
        if not demo:
            return ""
        check_keys(demo, "demo", "demo")
        title = demo.get("title") or DEFAULT_TITLES["demo"]
        parts = [f'<h2 class="section-title" id="demo-title">{self.shared(title, "demo.title")}</h2>']
        if demo.get("intro"):
            parts.append(self.shared(demo["intro"], "demo.intro", "p", "overview-intro"))
        label = plain(self.text(title, self.default, "demo.title"))
        parts.append(self.media(require(demo, "media", "demo"), label, "demo.media", "demo-video"))
        if demo.get("note"):
            parts.append(self.shared(demo["note"], "demo.note", "p", "video-method-note"))
        body = "\n            ".join(parts)
        return f"""        <section class="demo" aria-labelledby="demo-title">
            {body}
        </section>"""

    # Sections ----------------------------------------------------------

    def section_title(self, section, index):
        if section.get("title"):
            return section["title"]
        if section["type"] not in DEFAULT_TITLES:
            raise ContentError(f"sections[{index}].title is required for {section['type']} sections")
        return DEFAULT_TITLES[section["type"]]

    def panel(self, lang):
        sections = "\n".join(self.section(section, index, sid, lang) for index, (section, sid)
                             in enumerate(zip(self.data.get("sections") or [], self.section_ids)))
        hidden = "" if lang == self.default else " hidden"
        return f"""            <div class="localized-content" id="content-{lang}" lang="{lang}"{hidden}>
{sections}
            </div>
"""

    def section(self, section, index, sid, lang):
        path = f"sections[{index}]"
        t = lambda key, obj=section, p=path: self.text(obj[key], lang, f"{p}.{key}") if obj.get(key) else ""
        kind = section["type"]
        heading_id = f"{sid}-title-{lang}"
        title = self.text(self.section_title(section, index), lang, f"{path}.title")
        head = []
        if section.get("kicker"):
            head.append(f'<p class="section-kicker">{t("kicker")}</p>')
        head.append(f'<h2 class="section-title" id="{heading_id}">{title}</h2>')
        if section.get("intro"):
            head.append(f'<p class="overview-intro">{t("intro")}</p>')
        head = "\n                    ".join(head)
        band = " section-band" if section.get("band", DEFAULT_BAND.get(kind, False)) else ""

        if kind == "abstract":
            return f"""                <section class="abstract{band}" aria-labelledby="{heading_id}">
                    {head}
                    <div class="abstract-copy">
{self.paragraphs(require(section, "body", path), lang, f"{path}.body")}
                    </div>
                </section>"""

        if kind == "text":
            body = ""
            if section.get("body"):
                body = f'<div class="abstract-copy">\n{self.paragraphs(section["body"], lang, f"{path}.body")}\n</div>'
            figure = self.figure(section, lang, path, title) if section.get("media") else ""
            note = f'<p class="video-method-note">{t("note")}</p>' if section.get("note") else ""
            return f"""                <section class="content-section text-section{band}" aria-labelledby="{heading_id}">
                    {head}
                    {body}{figure}{note}
                </section>"""

        if kind == "cases":
            items = require(section, "items", path)
            prefix = plain(t("label")) if section.get("label") else "CASE"
            cards = []
            for n, item in enumerate(items, 1):
                ipath = f"{path}.items[{n - 1}]"
                check_keys(item, "case", ipath)
                name = self.text(require(item, "title", ipath), lang, f"{ipath}.title")
                meta = t("meta", item, ipath) or t("meta")
                label = f"{prefix} {n:02d}"
                text = f"<p>{t('text', item, ipath)}</p>" if item.get("text") else ""
                cards.append(f"""                        <article class="case-card">
                            <div class="case-media">{self.media(require(item, "media", ipath), f"{label}: {plain(name)}", f"{ipath}.media")}</div>
                            <div class="case-copy"><div class="case-meta"><span>{label}</span><span>{meta}</span></div><h3>{name}</h3>{text}</div>
                        </article>""")
            summary = f'\n                    <p class="case-count">{t("summary")}</p>' if section.get("summary") else ""
            note = f'\n                    <p class="video-method-note">{t("note")}</p>' if section.get("note") else ""
            cards = "\n".join(cards)
            return f"""                <section class="content-section case-showcase{band}" aria-labelledby="{heading_id}">
                    {head}{summary}
                    <div class="case-grid">
{cards}
                    </div>{note}
                </section>"""

        # overview
        if section.get("media"):
            body = self.figure(section, lang, path, title)
        else:
            body = self.flow(require(section, "flow", path), lang, path, sid, section)
        return f"""                <section class="content-section system-overview{band}" aria-labelledby="{heading_id}">
                    {head}
                    {body}
                </section>"""

    def figure(self, section, lang, path, title):
        caption = self.text(section["caption"], lang, f"{path}.caption") if section.get("caption") else ""
        media = self.media(section["media"], plain(caption) or plain(title), f"{path}.media")
        caption = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f'<figure class="content-figure">{media}{caption}</figure>'

    def flow(self, stages, lang, path, sid, section):
        """The stage/loop/outcome diagram, built from a list of stages."""
        t = lambda obj, key, p: self.text(obj[key], lang, f"{p}.{key}") if obj.get(key) else ""
        out = []
        for n, stage in enumerate(stages, 1):
            spath = f"{path}.flow[{n - 1}]"
            check_keys(stage, "stage", spath)
            number = f'<span class="system-stage-number" aria-hidden="true">{n:02d}</span>'
            title = self.text(require(stage, "title", spath), lang, f"{spath}.title")
            tag = f'<span class="system-stage-tag">{t(stage, "tag", spath)}</span>' if stage.get("tag") else ""
            if n > 1:
                out.append(f'<div class="system-connector">{ARROW_DOWN}<span>{t(stage, "arrow", spath)}</span></div>')
            if stage.get("loop"):
                steps = stage["loop"]
                lis = []
                for k, step in enumerate(steps):
                    kpath = f"{spath}.loop[{k}]"
                    check_keys(step, "step", kpath)
                    text = f"<p>{t(step, 'text', kpath)}</p>" if step.get("text") else ""
                    lis.append(f'<li class="system-loop-step"><h4>{self.text(require(step, "title", kpath), lang, f"{kpath}.title")}</h4>{text}</li>')
                intro = f'<p class="system-search-intro">{t(stage, "text", spath)}</p>' if stage.get("text") else ""
                feedback = ""
                if stage.get("feedback"):
                    # Arrow from the last step's center back to the first step's center.
                    first, last = 450 / len(steps), 900 - 450 / len(steps)
                    feedback = (f'<div class="system-feedback"><svg viewBox="0 0 900 42" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
                                f'<path d="M{last:g} 1v25H{first:g}V1m-5 6 5-6 5 6"/></svg>'
                                f'<p><span aria-hidden="true">↺</span> {t(stage, "feedback", spath)}</p></div>')
                heading = f"{sid}-stage{n}-{lang}"
                out.append(f'<div class="system-search" role="group" aria-labelledby="{heading}">'
                           f'<div class="system-search-heading">{number}<h3 id="{heading}">{title}</h3>{tag}</div>{intro}'
                           f'<ol class="system-loop" style="--loop-steps: {len(steps)}">{"".join(lis)}</ol>{feedback}</div>')
                continue
            text = f"<p>{t(stage, 'text', spath)}</p>" if stage.get("text") else ""
            box = f'<div class="system-stage">{number}<div><h3>{title}</h3>{text}</div>{tag}</div>'
            if stage.get("outcome"):
                outcome, opath = stage["outcome"], f"{spath}.outcome"
                check_keys(outcome, "outcome", opath)
                otag = f'<span class="system-stage-tag">{t(outcome, "tag", opath)}</span>' if outcome.get("tag") else ""
                otext = f"<p>{t(outcome, 'text', opath)}</p>" if outcome.get("text") else ""
                box = (f'<div class="system-outcome">{box}<div class="system-outcome-arrow">{ARROW_RIGHT}</div>'
                       f'<div class="system-stage system-evaluation"><div>{otag}<h3>{self.text(require(outcome, "title", opath), lang, f"{opath}.title")}</h3>{otext}</div></div></div>')
            out.append(box)
        caption_id = f"{sid}-caption-{lang}"
        caption = f'<figcaption id="{caption_id}">{self.text(section["caption"], lang, f"{path}.caption")}</figcaption>' if section.get("caption") else ""
        described = f' aria-describedby="{caption_id}"' if caption else ""
        flow = "\n                        ".join(out)
        return f"""<figure class="system-overview-figure"{described}>
                        <div class="system-flow">
                        {flow}
                        </div>
                        {caption}
                    </figure>"""


def build():
    try:
        data = yaml.safe_load(CONTENT.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ContentError(f"content.yaml is not valid YAML:\n{error}")
    return Page(data or {}).render()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if docs/index.html is out of date")
    parser.add_argument("--serve", action="store_true", help="build, then serve docs/ on localhost")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        page = build()
    except ContentError as error:
        sys.exit(f"content.yaml: {error}")
    if args.check:
        current = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
        if current != page:
            sys.exit("docs/index.html is out of date; run python3 build.py")
        print("docs/index.html is up to date")
        return
    PAGE.write_text(page, encoding="utf-8")
    print(f"wrote {PAGE.relative_to(ROOT)}")
    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DOCS)
        with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
            print(f"preview: http://localhost:{args.port}/  (Ctrl+C to stop)")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()

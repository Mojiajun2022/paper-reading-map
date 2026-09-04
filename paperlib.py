#!/usr/bin/env python3
"""What argument-map and literature-map both need: reading a paper, checking the numbers a
graph states against it, and one grammar for the Markdown both of them export.

It lives here, next to argument-map, because the dependency runs that way round — a corpus is
made of papers, and literature-map already reads argument-map's Markdown with --from-md. It is
one file with no imports of its own beyond the standard library, so vendoring a copy next to
either script also works.

Two copies of a parser are two places for the same bug to live. We paid that once already: the
table-separator rule was fixed in one script and left wrong in the other, and a Markdown file
reformatted by an ordinary editor stopped building.
"""
import hashlib
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- source text


def extract_text(path: Path, layout: bool = True) -> str:
    """Text of the paper. PDFs go through pdftotext; anything else is read as text.

    The two modes are for two different jobs. `-layout` keeps the physical lines, which is what
    a table needs to stay readable — so the number check uses it. But on a two-column paper it
    also splices the two columns together on every line: a word broken across a line comes out
    as `magnetic sys-` followed by the *other column's* text, and any quotation longer than one
    physical line becomes unfindable. Reading order (no `-layout`) follows the column and mends
    the hyphen, so that is what the quotation check reads."""
    if path.suffix.lower() == ".pdf":
        if not shutil.which("pdftotext"):
            sys.exit("error: --source is a PDF but pdftotext is not installed "
                     "(brew install poppler), or pass an extracted .txt instead")
        cmd = ["pdftotext"] + (["-layout"] if layout else []) + [str(path), "-"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"error: pdftotext failed on {path}: {out.stderr.strip()}")
        return out.stdout
    return path.read_text(encoding="utf-8", errors="ignore")


def fingerprint(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def gather_full(paths: list) -> tuple:
    """One pass over the sources: joined text, a fingerprint each, and a page index.

    pdftotext separates pages with a form feed, so the pages come free — and with them the
    ability to say which page a quotation is on instead of asking the writer to remember."""
    records = gather_records(paths)
    text = [r["layout_text"] for r in records]
    stamps = [r["stamp"] for r in records]
    pages = [page for r in records for page in r["pages"]]
    return "\n".join(text), stamps, pages


def gather_records(paths: list) -> list:
    """Read sources once, retaining per-source and per-page text for scoped checks."""
    records = []
    seen = set()
    for raw in paths:
        f = Path(raw)
        if not f.exists():
            sys.exit(f"error: --source not found: {f}")
        resolved = f.resolve()
        if resolved in seen:
            sys.exit(f"error: --source was provided more than once: {f}")
        seen.add(resolved)

        # Number checks need layout-preserving text so table cells stay legible. Quote
        # checks need reading-order text so two-column lines do not get interleaved. A
        # plain-text source has no second representation, so do not read it twice.
        layout_text = extract_text(f, layout=True)
        reading_text = (extract_text(f, layout=False)
                        if f.suffix.lower() == ".pdf" else layout_text)
        if not layout_text.strip() and not reading_text.strip():
            if f.suffix.lower() == ".pdf":
                sys.exit(f"error: {f} contains no extractable text; it may be a scanned PDF. "
                         "OCR it first or pass an extracted .txt source")
            sys.exit(f"error: --source is empty: {f}")

        page_texts = layout_text.split("\f")
        pages = []
        for i, page in enumerate(reading_text.split("\f"), 1):
            flat = squash(page)
            if flat:
                pages.append((f.name, i, flat, dehyphen(flat)))
        records.append({
            "file": f.name,
            "layout_text": layout_text,
            "page_texts": page_texts,
            "pages": pages,
            "stamp": fingerprint(f),
        })
    return records


def gather(paths: list) -> tuple:
    """Text of every source, and a fingerprint for each."""
    text, stamps, _ = gather_full(paths)
    return text, stamps


# ---------------------------------------------------------------- number check


# Keep scientific notation together. The old expression split ``1e-3`` into ``1``
# and ``3``, allowing a wrong exponent to pass when those digits appeared elsewhere.
# Uncertainty suffixes such as ``3.45(2)`` intentionally remain two values: the
# source reports both the measured value and its uncertainty.
NUMBER = re.compile(
    r"(?<![\w.])[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)"
    r"(?:\s*[eE]\s*[+-]?\s*\d+)?%?(?![\d.,])"
)


# text fields the reader sees; each may also appear as <field>_en / <field>_zh
TEXT_FIELDS = {"label", "detail"}
LANGS = {"en", "zh"}


def is_text_field(name: str) -> bool:
    """`detail`, and its per-language twins `detail_en` / `detail_zh`."""
    if name in TEXT_FIELDS:
        return True
    base, _, lang = name.rpartition("_")
    return bool(base) and base in TEXT_FIELDS and lang in LANGS


def vwidth(s: str) -> int:
    """Visual width in half-widths: the renderer's budget, and CJK is twice as wide as latin."""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in s)


def dehyphen(s: str) -> str:
    """A line break inside a word leaves a hyphen in the extracted text that is not in the paper.
    Someone quoting from the page will not have typed it, so compare with both gone."""
    return s.replace("-", "").replace("\u2010", "").replace("\u2011", "").replace("\u00ad", "")


# Typesetters write compound words with an en dash, a figure dash or a non-breaking hyphen;
# someone copying the sentence types a plain one. That is a difference in typography, not in
# what the paper says, so it is normalised away like whitespace. A different WORD is not.
DASHES = {ord(c): "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"}


def squash(s: str) -> str:
    """Whitespace, dash style and compatibility forms gone, so a quotation still matches after
    the typesetter has wrapped it across two lines or two columns."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s).translate(DASHES))


def number_text(s: str) -> str:
    """Normalise source text for numeric matching without erasing word boundaries.

    Quote matching can safely remove every space. Number matching cannot: after
    ``squash("value 3")`` there is no way to distinguish a standalone value from
    an identifier suffix. Keep one regular space, while also normalising Unicode
    minus signs and compatibility forms.
    """
    text = unicodedata.normalize("NFKC", s).translate(DASHES)
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text)


def compact_number_spacing(s: str) -> str:
    """Remove only whitespace that splits one numeric token in extracted PDF text."""
    text = re.sub(r"(?<=\d)\s+(?=[.,])", "", s)
    text = re.sub(r"(?<=[.,])\s+(?=\d)", "", text)
    text = re.sub(r"(?<=\d)\s+(?=[eE])", "", text)
    # Require a digit before ``e`` so the final ``e`` in a word such as ``value``
    # is never treated as an exponent marker.
    text = re.sub(r"(?<=\d[eE])\s+(?=[+-])", "", text)
    text = re.sub(r"(?<=\d[eE])\s+(?=\d)", "", text)
    text = re.sub(r"(?<=\d[eE][+-])\s+(?=\d)", "", text)
    return text


def variants(num: str) -> list:
    """Ways the same quantity may legitimately appear in the source text."""
    base = unicodedata.normalize("NFKC", str(num))
    base = base.replace("\u2212", "-").replace("\u00a0", "")
    base = re.sub(r"\s+", "", base)
    out = {base}
    # Exponent markers are case-insensitive in ordinary scientific notation.
    if "E" in base:
        out.add(base.replace("E", "e"))
    elif "e" in base:
        out.add(base.replace("e", "E"))
    suffix = "%" if base.endswith("%") else ""
    core = base[:-1] if suffix else base
    compact = core.replace(",", "")
    out.add(compact + suffix)
    if core.endswith(".0"):
        out.add(core[:-2] + suffix)
    if "." not in core:
        out.add(core + ".0" + suffix)
    return [v for v in out if v]


def _number_token_present(candidate: str, flat: str) -> bool:
    """Match a complete numeric token, not a substring of a larger number.

    ``squash`` removes whitespace, so boundaries around digits, decimal points and
    comma separators reject ``2`` inside ``12`` or ``3`` inside ``3.14``. A
    comma-free view is checked as well so ``1,000`` and ``1000`` are equivalent.
    """
    candidate = squash(candidate)
    if not candidate:
        return False
    compact = compact_number_spacing(flat)
    compact = re.sub(r"(?<=\d),(?=\d)", "", compact)
    # The extra exponent guards keep a bare ``1`` or ``3`` from matching the two
    # components of ``1e-3`` when the source text has been compacted by a caller.
    literal = re.escape(candidate[:-1]) + r"\s*%" if candidate.endswith("%") else re.escape(candidate)
    signed = candidate.startswith(("+", "-"))
    left = r"(?<![\d.,])" if signed else r"(?<![+\-\d.,])"
    pattern = re.compile(
        rf"{left}(?<!\d[eE])(?<!\d[eE][+-])"
        rf"{literal}"
        rf"(?!\d)(?![.,]\d)(?![eE][+-]?\d)",
        re.IGNORECASE,
    )
    return bool(pattern.search(flat) or pattern.search(compact))


def found(num: str, flat: str) -> bool:
    """Is this quantity in the paper?

    Comma-grouped values are matched only as the complete value or its comma-free
    equivalent. Separate occurrences of the comma-separated pieces are not evidence.
    """
    if any(_number_token_present(v, flat) for v in variants(num)):
        return True
    return False


def check_numbers(obj: dict, source_text: str) -> tuple:
    """Every number a node states must be findable in the paper. Returns (checked, misses)."""
    flat = number_text(source_text)
    checked, misses = 0, []
    for n in obj.get("nodes") or []:
        # a translated detail states the paper's numbers just as the original does, so it is
        # held to the same standard — otherwise the English half of a page would be unchecked
        for field in [f for f in n if is_text_field(f)]:
            for raw in NUMBER.findall(str(n.get(field) or "")):
                num = raw.rstrip(".,")
                if not num or not any(c.isdigit() for c in num):
                    continue
                checked += 1
                if found(num, flat):
                    continue
                misses.append((n.get("id", "?"), n.get("label", ""), field, num))
    return checked, misses


def locate_quote(q: str, pages: list):
    """Where a quotation occurs verbatim: (file, page) or None.

    Whitespace is already gone on both sides, so a quotation that wrapped across lines or
    columns still matches; hyphens are tried both ways for the same reason."""
    needle = squash(q)
    if not needle:
        return None
    bare = dehyphen(needle)
    for name, no, flat, flat_bare in pages:
        if needle in flat or bare in flat_bare:
            return (name, no)
    return None


def diverges_at(q: str, pages: list) -> tuple:
    """Where a quotation stops matching the paper, and what the paper says at that point.

    "Not found" is a useless thing to tell someone holding a sentence they believe they copied.
    Binary-searching the longest prefix that *is* in the paper points straight at the word that
    differs. When the difference is near the start there is no useful prefix, so the same search
    runs from the other end — a quotation usually diverges at one place, not everywhere.

    Returns (side, matched length, the source text just past the match), side being "start" or
    "end", or ("", 0, "") when nothing meaningful matched."""
    needle = dehyphen(squash(q))
    if len(needle) < 16:
        return "", 0, ""

    def longest(take):
        """take(k) is the k-character piece being searched for."""
        lo, hi, best, where = 0, len(needle), 0, None
        while lo < hi:
            mid = (lo + hi + 1) // 2
            piece = take(mid)
            hit = next(((flat_bare, flat_bare.find(piece)) for _, _, _, flat_bare in pages
                        if piece in flat_bare), None)
            if hit:
                lo, best, where = mid, mid, hit
            else:
                hi = mid - 1
        return best, where

    head, head_at = longest(lambda k: needle[:k])
    tail, tail_at = longest(lambda k: needle[-k:])
    if head >= tail and head >= 10 and head_at:
        flat, at = head_at
        return "start", head, flat[at + head: at + head + 60]
    if tail >= 10 and tail_at:
        flat, at = tail_at
        return "end", tail, flat[max(0, at - 60): at]
    return "", 0, ""


def check_quotes(obj: dict, pages: list) -> tuple:
    """Every quotation a node carries must be in the paper, word for word.

    This is the check the number check cannot do. A number is confirmed to exist *somewhere*;
    it is not confirmed to belong to the claim it was attached to. A quotation is the claim, so
    finding it verbatim ties the node to a specific sentence on a specific page.

    Returns (checked, misses, located-by-node-id)."""
    checked, misses, located = 0, [], {}
    for n in obj.get("nodes") or []:
        q = n.get("quote")
        if not q:
            continue
        checked += 1
        hit = locate_quote(str(q), pages)
        if hit:
            located[n.get("id")] = hit
        else:
            misses.append((n.get("id", "?"), n.get("label", ""), str(q),
                           diverges_at(str(q), pages)))
    return checked, misses, located


# ---------------------------------------------------------------- markdown grammar


MIME_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "image/svg+xml": ".svg", "image/bmp": ".bmp",
    "image/avif": ".avif", "image/apng": ".apng", "image/x-icon": ".ico",
    "image/tiff": ".tif",
}


# One typed vocabulary for both dialects: the union is safe because a key that one of them
# never writes simply never comes up, and the exporters' round-trip check would catch it if it did.
MD_INT = {"importance", "year", "numbers_checked", "numbers_verified", "bytes",
          "quote_page", "quotes_checked", "quotes_verified"}


MD_FLOAT = {"stage"}


MD_BOOL = {"main", "focal"}


# prose, written as a blockquote rather than a `- key: value` line
BLOCK_PREFIXES = ("detail", "note", "summary", "evidence")
KV = re.compile(r"-\s+([A-Za-z_][A-Za-z_0-9]*):\s?(.*)$")
BLOCK_KEY = re.compile(r"([A-Za-z_][A-Za-z_0-9]*):$")
HEAD_ID = re.compile(r"`([^`]*)`(?:\s+—\s+(.*))?$")


def md_scalar(key: str, raw: str):
    """Turn a `- key: value` line back into the type the renderer expects."""
    if key in MD_INT:
        try:
            return int(raw)
        except ValueError:
            return raw
    if key in MD_FLOAT:
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw
    if key in MD_BOOL:
        return raw.strip().lower() in ("yes", "true", "1")
    return raw


def md_meaningful(v) -> bool:
    """Absent, empty and false all render the same; 0 does not, so it is kept."""
    return not (v is None or v == "" or v is False)


def md_fields(obj: dict, skip: set) -> tuple:
    """Split an object into `- key: value` lines and blockquote blocks."""
    lines, blocks = [], []
    for k, v in obj.items():
        if k in skip or not md_meaningful(v):
            continue
        if isinstance(v, (dict, list)):
            continue                       # only figures/meta nest, and they have their own section
        s = "yes" if v is True else str(v)
        if k.startswith(BLOCK_PREFIXES) or "\n" in s:
            blocks.append((k, s))
        else:
            lines.append(f"- {k}: {s}")
    return lines, blocks


def md_block(key: str, text: str) -> list:
    """Prose as a blockquote: readable anywhere, and one `> ` strip parses it back exactly."""
    return [f"{key}:", ""] + [f"> {ln}" if ln else ">" for ln in text.split("\n")] + [""]


def md_cell(v) -> str:
    if v is True:
        return "yes"
    if v is None or v is False:
        return ""
    return (str(v).replace("\\", "\\\\").replace("|", "\\|")
            .replace("\n", "\\n").replace("\r", ""))


def md_is_rule(line: str) -> bool:
    """`|---|---|` separates a table's header from its rows, and an editor that reformats the
    file writes it as `| :--- | :--- |`. Take every pipe out before looking at what is left,
    or the alignment row arrives as an edge whose source is ':---'."""
    body = line.replace("|", "").strip()
    return body == "" or set(body) <= set("- :")


def md_unescape_cell(value: str) -> str:
    """Decode the small escape vocabulary used by Markdown table cells."""
    out, i = [], 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt in ("\\", "|"):
                out.append(nxt)
                i += 2
                continue
        out.append(value[i])
        i += 1
    return "".join(out)


def md_split_cells(line: str) -> list:
    """Split a table row without treating escaped pipes as delimiters."""
    cells, buf, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] in ("\\", "|", "n"):
            buf.extend((ch, line[i + 1]))
            i += 2
            continue
        if ch == "|":
            cells.append(md_unescape_cell("".join(buf).strip()))
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append(md_unescape_cell("".join(buf).strip()))
    return cells


def md_row(line: str, cols: list) -> dict:
    """One table row, keyed by the header. An empty cell means the key is absent."""
    cells = md_split_cells(line.strip())
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return {c: md_scalar(c, v) for c, v in zip(cols, cells) if v != ""}


def md_read_block(lines: list, i: int) -> tuple:
    """A `key:` line followed by a blockquote. Returns (text, next index) or (None, i)."""
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    buf = []
    while j < len(lines) and lines[j].startswith(">"):
        buf.append(lines[j][2:] if lines[j].startswith("> ") else lines[j][1:])
        j += 1
    return ("\n".join(buf), j) if buf else (None, i)


def md_diff(a, b, path="") -> list:
    """Every place the round trip lost or changed something, named precisely."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: appeared out of nowhere ({b[k]!r})")
            elif k not in b:
                out.append(f"{path}.{k}: lost ({a[k]!r})")
            else:
                out += md_diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: {len(a)} items became {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in md_diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} -> {b!r}"]


def md_normalise(d, _root=True):
    """Absent / empty / false are one state in the renderer; compare them as one."""
    if isinstance(d, dict):
        return {k: md_normalise(v, False) for k, v in d.items()
                if md_meaningful(v) and (not _root or k != "source")}
    if isinstance(d, list):
        return [md_normalise(x, False) for x in d]
    return d

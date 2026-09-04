#!/usr/bin/env python3
"""Build a self-contained 3D knowledge-graph HTML from a logic-chain JSON.

    python3 build_graph.py graph.json -o out.html --source paper.pdf
    python3 build_graph.py graph.json --export-md graph.md
    python3 build_graph.py graph.md  -o out.html --source paper.pdf
    python3 build_graph.py --check graph.json --source paper.pdf
    python3 build_graph.py --verify out.html --source paper.pdf

Modes:
    --validate graph.json                 check graph structure only
    --check graph.json --source paper.pdf check graph and source claims without writing output
    graph.json -o out.html --source paper.pdf
                                            build the self-contained HTML page
    graph.json --export-md graph.md        export editable Markdown
    --verify out.html --source paper.pdf   re-check an existing page

The Markdown export carries everything the JSON does and is checked to round-trip before it
is written, so it can be read, diffed, hand-edited and built back into the same page.

With --source, every number written into a node is checked against the text of the
paper itself, and the build fails on any number that is not there. The source file's
hash is stamped into the page, so a graph can always be re-checked against the paper
it claims to describe — a graph whose paper has since changed looks exactly like a
hallucinated one otherwise.
"""
import argparse
import base64
import binascii
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# The number checking and the Markdown grammar are shared with literature-map, so there is
# one implementation of each rather than two that drift apart.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paperlib import (  # noqa: E402  — path is set just above
    MIME_EXT,
    check_numbers, check_quotes, gather_full, md_scalar, md_meaningful, md_fields, md_block,
    md_cell, md_is_rule, md_diff, md_normalise, vwidth, gather_records, number_text,
)

KNOWN_TYPES = {
    "background", "related", "problem", "hypothesis", "method",
    "experiment", "result", "conclusion", "limitation", "future",
}
KNOWN_RELATIONS = {
    "motivates", "addresses", "proposes", "uses", "produces",
    "supports", "refutes", "leads_to", "compares", "limits",
}
# text fields the reader sees; each may also appear as <field>_en / <field>_zh


# ---------------------------------------------------------------- source text


# ---------------------------------------------------------------- number check


def report_misses(misses: list, hard: bool) -> None:
    word = "error" if hard else "warning"
    print(f"\n{len(misses)} number(s) could not be found in the source text:", file=sys.stderr)
    for nid, label, field, num in misses:
        print(f"  {word}: {num!r} in {field} of node '{nid}' ({label})", file=sys.stderr)
    print("\nEither the number is wrong, or the source text extractor dropped it — "
          "pdftotext loses digits inside some tables. Check each one against the paper. "
          "Pass --allow-unverified to build anyway; the page will say so.", file=sys.stderr)


def report_quote_misses(qmisses: list, hard: bool) -> None:
    """Print quotation failures with the first useful point of divergence."""
    word = "error" if hard else "warning"
    print(f"\n{len(qmisses)} quotation(s) do not appear in the source text:", file=sys.stderr)
    for nid, label, quote, (side, kept, rest) in qmisses:
        short = quote if len(quote) <= 90 else quote[:87] + "..."
        print(f"  {word}: node '{nid}' ({label})\n      {short!r}", file=sys.stderr)
        if side == "start":
            print(f"      matches the paper for its first {kept} characters, which there "
                  f"continue {rest!r}", file=sys.stderr)
        elif side == "end":
            print(f"      its last {kept} characters are in the paper, preceded there by "
                  f"{rest!r}", file=sys.stderr)
    print("\nA quotation must be the paper's own words. Copy it again, shorten it to the "
          "part you can verify, or drop the field. If pdftotext mangled the passage, "
          "confirm it visually and pass --allow-unverified.", file=sys.stderr)


def check_against_sources(data: dict, sources: list) -> dict:
    """Run source checks, applying an optional node file/page scope."""
    records = gather_records(sources)
    stamps = [r["stamp"] for r in records]
    text = "\n".join(r["layout_text"] for r in records)
    pages = [page for r in records for page in r["pages"]]
    by_name = {}
    for record in records:
        by_name.setdefault(record["file"], []).append(record)

    def scope_for(node):
        filename = node.get("evidence_file")
        page_no = node.get("evidence_page")
        if page_no is not None and filename is None:
            raise ValueError(f"node '{node.get('id', '?')}' has evidence_page without evidence_file")
        if filename is None:
            return text, pages
        matches = by_name.get(filename, [])
        if not matches:
            raise ValueError(f"node '{node.get('id', '?')}' evidence_file {filename!r} "
                             "does not match any supplied source basename")
        if len(matches) != 1:
            raise ValueError(f"node '{node.get('id', '?')}' evidence_file {filename!r} "
                             "is ambiguous among supplied sources")
        record = matches[0]
        scoped_text = record["layout_text"]
        scoped_pages = record["pages"]
        if page_no is not None:
            if page_no < 1 or page_no > len(record["page_texts"]):
                raise ValueError(f"node '{node.get('id', '?')}' evidence_page {page_no} "
                                 f"is outside {filename!r} (1-{len(record['page_texts'])})")
            scoped_text = record["page_texts"][page_no - 1]
            scoped_pages = [p for p in record["pages"] if p[1] == page_no]
        return scoped_text, scoped_pages

    checked = verified = quoted = qverified = 0
    misses, qmisses, located = [], [], {}
    node_results = {}
    for node in data.get("nodes") or []:
        scoped_text, scoped_pages = scope_for(node)
        one = {"nodes": [node]}
        n_checked, n_misses = check_numbers(one, scoped_text)
        q_checked, n_qmisses, n_located = check_quotes(one, scoped_pages)
        checked += n_checked
        verified += n_checked - len(n_misses)
        quoted += q_checked
        qverified += q_checked - len(n_qmisses)
        misses.extend(n_misses)
        qmisses.extend(n_qmisses)
        located.update(n_located)
        node_results[node.get("id")] = {
            "numbers_checked": n_checked,
            "numbers_verified": n_checked - len(n_misses),
            "quote_checked": bool(q_checked),
            "quote_verified": bool(q_checked and not n_qmisses),
            "scope": (node.get("evidence_file"), node.get("evidence_page")),
        }
    return {
        "stamps": stamps,
        "pages": pages,
        "checked": checked,
        "misses": misses,
        "verified": verified,
        "quoted": quoted,
        "qmisses": qmisses,
        "qverified": qverified,
        "located": located,
        "node_results": node_results,
    }


# ---------------------------------------------------------------- structure

def validate(data: dict) -> tuple:
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["graph root must be a JSON object"], warnings
    for field in ("title", "title_en", "title_zh", "short_title", "short_title_en",
                  "short_title_zh", "summary", "summary_en", "summary_zh"):
        if field in data and data[field] is not None and not isinstance(data[field], str):
            errors.append(f"'{field}' must be a string")
    if not data.get("title"):
        warnings.append("no 'title' — the header will be empty")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("'nodes' must be a non-empty list")
    if not isinstance(edges, list):
        errors.append("'edges' must be a list")
    if data.get("meta") is not None and not isinstance(data.get("meta"), dict):
        errors.append("'meta' must be an object")
    raw_figures = data.get("figures")
    figures = {} if raw_figures is None else raw_figures
    if not isinstance(figures, dict):
        errors.append("'figures' must be an object")
        figures = {}
    if errors:
        # Continue through a well-formed list when possible so one run reports all useful
        # input problems instead of stopping at the first malformed top-level field.
        if not isinstance(nodes, list) or not nodes:
            return errors, warnings
        if not isinstance(edges, list):
            edges = []

    ids = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"nodes[{i}] must be an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            errors.append(f"nodes[{i}] has no 'id'"); continue
        if nid in ids:
            errors.append(f"duplicate node id '{nid}'")
        ids.add(nid)
        for bad in ("quote_en", "quote_zh"):
            if n.get(bad):
                errors.append(f"node '{nid}' has '{bad}' — a quotation is the paper's own words "
                              "and must not be translated; keep the one 'quote' field")
        # `quote_page` / `quote_file` are generated metadata that Markdown preserves for
        # readers. A hand-authored `page` is the field that should be discouraged because
        # the builder cannot trust it and will locate the quotation itself.
        if n.get("page") and not data.get("source"):
            warnings.append(f"node '{nid}' sets a page — the build finds the quotation itself "
                            "and overwrites it, so the field is not needed")
        for f in ("label", "label_en", "label_zh", "detail", "detail_en", "detail_zh", "quote"):
            if f in n and n[f] is not None and not isinstance(n[f], str):
                errors.append(f"node '{nid}' {f} must be a string")
        for f in ("section", "section_en", "section_zh"):
            if f in n and n[f] is not None and not isinstance(n[f], str):
                errors.append(f"node '{nid}' {f} must be a string")
        evidence_file = n.get("evidence_file")
        if evidence_file is not None and (
                not isinstance(evidence_file, str) or not evidence_file.strip()
                or Path(evidence_file).name != evidence_file
                or "/" in evidence_file or "\\" in evidence_file):
            errors.append(f"node '{nid}' evidence_file must be a source basename")
        evidence_page = n.get("evidence_page")
        if evidence_page is not None and (
                isinstance(evidence_page, bool) or not isinstance(evidence_page, int)
                or evidence_page < 1):
            errors.append(f"node '{nid}' evidence_page must be a positive integer")
        if evidence_page is not None and evidence_file is None:
            errors.append(f"node '{nid}' evidence_page requires evidence_file")
        if n.get("quote") and len(str(n["quote"])) < 12:
            warnings.append(f"node '{nid}' quote is {len(str(n['quote']))} characters — too short "
                            "to pin a claim, and likely to match somewhere by accident")
        if not n.get("label"):
            errors.append(f"node '{nid}' has no 'label'")
        for f in ("label", "label_en", "label_zh"):
            if not n.get(f):
                continue
            w = vwidth(str(n[f]))
            if w > 32:
                warnings.append(f"node '{nid}' {f} is {w} units wide — the renderer truncates "
                                "past 32 (a CJK character counts 2, a latin one 1)")
        node_type = n.get("type")
        if node_type is not None and not isinstance(node_type, str):
            errors.append(f"node '{nid}' type must be a string")
        elif node_type not in KNOWN_TYPES:
            warnings.append(f"node '{nid}' type {n.get('type')!r} is unknown — it renders gray")
        if not n.get("detail"):
            warnings.append(f"node '{nid}' has no 'detail' — its side panel will be empty")
        importance = n.get("importance")
        if importance is not None and (
            isinstance(importance, bool) or not isinstance(importance, (int, float))
            or not math.isfinite(float(importance)) or int(importance) != importance
            or not 1 <= int(importance) <= 3
        ):
            errors.append(f"node '{nid}' importance {importance!r} must be an integer from 1 to 3")
        stage = n.get("stage")
        if stage is not None and (
            isinstance(stage, bool) or not isinstance(stage, (int, float))
            or not math.isfinite(float(stage))
        ):
            errors.append(f"node '{nid}' stage must be a finite number")
        if n.get("figure") is not None:
            if not isinstance(n.get("figure"), str):
                errors.append(f"node '{nid}' figure reference must be a string")
            elif n.get("figure") not in figures:
                errors.append(f"node '{nid}' refers to missing figure {n.get('figure')!r}")
            elif not isinstance(figures[n["figure"]], dict) or not figures[n["figure"]].get("uri"):
                errors.append(f"node '{nid}' refers to figure {n.get('figure')!r} without an image URI")

    for key, figure in figures.items():
        if (not isinstance(key, str) or key in ("", ".", "..")
                or "/" in key or "\\" in key or Path(key).name != key):
            errors.append(f"figure key {key!r} is not a safe single path component")
            continue
        if not isinstance(figure, dict):
            errors.append(f"figure {key!r} must be an object")
            continue
        uri = figure.get("uri")
        if uri is None or uri == "":
            continue
        if not isinstance(uri, str):
            errors.append(f"figure {key!r} uri must be a string")
            continue
        if not uri.lower().startswith("data:image/"):
            errors.append(f"figure {key!r} is external; use a data:image/... URI so the HTML "
                          "stays self-contained")
            continue
        head, sep, payload = uri.partition(",")
        if not sep or not payload:
            errors.append(f"figure {key!r} has an incomplete data URI")
            continue
        mime = head[5:].split(";")[0].lower()
        if mime not in MIME_EXT:
            errors.append(f"figure {key!r} uses unsupported image MIME {mime!r}")
        elif ";base64" in head.lower():
            try:
                base64.b64decode(payload, validate=True)
            except (ValueError, binascii.Error):
                errors.append(f"figure {key!r} has invalid base64 image data")

    touched, main_edges = set(), []
    seen_edges = set()
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"edges[{i}] must be an object")
            continue
        s, t = e.get("source"), e.get("target")
        valid_source = isinstance(s, str) and s in ids
        valid_target = isinstance(t, str) and t in ids
        if not valid_source:
            errors.append(f"edges[{i}] source {s!r} is not a node id")
        if not valid_target:
            errors.append(f"edges[{i}] target {t!r} is not a node id")
        if "main" in e and not isinstance(e["main"], bool):
            errors.append(f"edges[{i}] main flag must be a boolean")
        if s == t:
            (errors if e.get("main") is True else warnings).append(
                f"edges[{i}] is a self-loop on {s!r}")
        r = e.get("relation")
        if r is None:
            warnings.append(f"edges[{i}] has no 'relation' — the edge will have no explanatory verb")
        elif not isinstance(r, str):
            errors.append(f"edges[{i}] relation must be a string")
        elif r and r not in KNOWN_RELATIONS:
            warnings.append(f"edges[{i}] relation {r!r} is not a known relation")
        for f in ("label", "label_en", "label_zh"):
            if f in e and e[f] is not None and not isinstance(e[f], str):
                errors.append(f"edges[{i}] {f} must be a string")
        for f in ("reason", "reason_en", "reason_zh"):
            if f in e and e[f] is not None and not isinstance(e[f], str):
                errors.append(f"edges[{i}] {f} must be a string")
        if valid_source and valid_target:
            touched.update((s, t))
            pair = (s, t)
            if pair in seen_edges:
                errors.append(f"duplicate edge {s!r} -> {t!r}")
            seen_edges.add(pair)
        if e.get("main") is True and valid_source and valid_target:
            main_edges.append((s, t))

    isolated = ids - touched
    if isolated:
        warnings.append(f"isolated nodes (no edges): {sorted(isolated)}")
    if not main_edges:
        warnings.append('no edge has "main": true — mark the spine so it can be highlighted '
                        "and so the 起点/终点 markers have something to attach to")
    else:
        for issue in check_spine(main_edges):
            if issue.startswith("error: "):
                errors.append(issue[7:])
            else:
                warnings.append(issue)

        # Supporting evidence is useful only when it joins the argument spine. Keep this
        # a warning for compatibility; --strict turns it into a build-blocking error.
        all_adj = {}
        for e in edges:
            if not isinstance(e, dict):
                continue
            s, t = e.get("source"), e.get("target")
            if s in ids and t in ids:
                all_adj.setdefault(s, set()).add(t)
                all_adj.setdefault(t, set()).add(s)
        spine_nodes = {n for pair in main_edges for n in pair}
        seen_components = set()
        for start in sorted(touched):
            if start in seen_components:
                continue
            component, stack = set(), [start]
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                stack.extend(all_adj.get(node, set()))
            seen_components.update(component)
            if component.isdisjoint(spine_nodes):
                warnings.append(f"supporting component {sorted(component)} is disconnected from "
                                "the main spine")
    if isinstance(nodes, list) and len(nodes) > 60:
        warnings.append(f"{len(nodes)} nodes — consider merging minor ones; >60 gets cluttered")
    return errors, warnings


def check_spine(main_edges: list) -> list:
    """The spine may branch and rejoin — a paper's argument often converges from several
    strands and then forks into separate claims. What it may not do is start or end in more
    than one place, because 起点/终点 have to be unambiguous, or run in a circle."""
    out_deg, in_deg, seen = {}, {}, set()
    for s, t in main_edges:
        out_deg[s] = out_deg.get(s, 0) + 1
        in_deg[t] = in_deg.get(t, 0) + 1
        seen.update((s, t))
    notes = []
    roots = sorted(n for n in seen if not in_deg.get(n))
    tips = sorted(n for n in seen if not out_deg.get(n))
    if len(roots) != 1:
        notes.append(f"error: the spine has {len(roots)} entry points {roots} — 起点 would mark "
                     "one arbitrarily; give the argument a single starting claim")
    if len(tips) != 1:
        notes.append(f"error: the spine has {len(tips)} endpoints {tips} — 终点 would mark one "
                     "arbitrarily; branches should rejoin at the conclusion")
    # Detect cycles independently of roots/tips. A cycle can be attached to an otherwise
    # valid root-to-tip path, in which case the old root/tip-only check silently accepted it.
    adj = {}
    indegree = {n: 0 for n in seen}
    for s, t in main_edges:
        adj.setdefault(s, []).append(t)
        indegree[t] += 1
    queue = [n for n in sorted(seen) if indegree[n] == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adj.get(node, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(seen):
        notes.append("error: the spine contains a cycle — it has to flow one way, background → conclusion")

    # every spine node must be reachable from the root, or it is a detached fragment
    if len(roots) != 1:
        return notes
    reached, stack = set(), [roots[0]]
    while stack:
        n = stack.pop()
        if n in reached:
            continue
        reached.add(n)
        stack.extend(adj.get(n, []))
    stranded = sorted(seen - reached)
    if stranded:
        notes.append(f"spine node(s) {stranded} are not reachable from 起点 — the main edges "
                     "form more than one disconnected chain")
    return notes


# ---------------------------------------------------------------- markdown round trip
# The graph JSON is the machine's copy; this is the one a person can read, diff, hand-edit and
# keep. It carries everything the JSON does, so a build from the Markdown produces the same page
# — with one deliberate exception, the provenance stamp, which is never restored from a file.
# A stamp says "these numbers were checked against that PDF"; re-attaching it without redoing the
# check would let an edited graph inherit a clean bill it never earned. Pass --source again.

MD_HEADER = "<!-- argument-map graph · markdown v1 -->"
MD_SKIP_TOP = {"nodes", "edges", "figures", "meta", "source", "title"}


def dump_md(data: dict, fig_dir_name: str, embed: bool) -> tuple:
    """Render the graph as Markdown. Returns (text, {relative path: bytes}) for the figures."""
    import base64
    out = [MD_HEADER, ""]
    out += [f"# {data.get('title', '')}".rstrip(), ""]

    lines, blocks = md_fields(data, MD_SKIP_TOP)
    out += ["## Graph", ""]
    out += lines + ([""] if lines else [])
    for k, v in blocks:
        out += md_block(k, v)

    meta = data.get("meta") or {}
    if meta:
        out += ["## Meta", ""]
        out += [f"- {k}: {v}" for k, v in meta.items() if md_meaningful(v)] + [""]

    src = data.get("source")
    if src:
        out += ["## Source (record only)", "",
                "What this graph was last checked against. Rebuilding from this file does **not**",
                "restore it — pass `--source` again so the numbers are checked afresh.", ""]
        for k, v in src.items():
            if k == "files":
                for f in v:
                    out.append(f"- file: {f.get('file')} · {f.get('sha256')} · "
                               f"{f.get('bytes')} bytes · {f.get('modified')}")
            elif md_meaningful(v):
                out.append(f"- {k}: {v}")
        out.append("")

    figs, blobs = data.get("figures") or {}, {}
    if figs:
        out += ["## Figures", ""]
        for key, f in figs.items():
            out += [f"### `{key}`", ""]
            for k, v in f.items():
                if k != "uri" and md_meaningful(v):
                    out.append(f"- {k}: {v}")
            uri = f.get("uri") or ""
            if embed or not uri.startswith("data:"):
                if uri:
                    out.append(f"- uri: {uri}")
            else:
                head, sep, payload = uri.partition(",")
                if ";base64" not in head.lower() or not sep:
                    # Non-base64 data URIs are already self-contained. Keep them inline
                    # instead of trying to decode percent-encoded SVG/XML as base64.
                    out.append(f"- uri: {uri}")
                else:
                    mime = head[5:].split(";")[0].lower()
                    try:
                        blob = base64.b64decode(payload, validate=True)
                    except (ValueError, binascii.Error) as e:
                        raise ValueError(f"figure {key!r} contains invalid base64 data") from e
                    rel = f"{fig_dir_name}/{key}{MIME_EXT.get(mime, '.bin')}"
                    blobs[rel] = blob
                    out.append(f"- image: {rel}")
            out.append("")

    out += ["## Nodes", ""]
    for n in data.get("nodes", []):
        label = n.get("label", "")
        out += [f"### `{n.get('id', '')}`" + (f" — {label}" if label else ""), ""]
        lines, blocks = md_fields(n, {"id", "label"})
        out += lines + ([""] if lines else [])
        for k, v in blocks:
            out += md_block(k, v)

    edges = data.get("edges", [])
    if edges:
        cols, seen = ["source", "target", "relation", "main"], set()
        for e in edges:
            for k in e:
                if k not in cols and k not in seen:
                    seen.add(k)
        cols += sorted(seen)
        out += ["## Edges", "", "| " + " | ".join(cols) + " |",
                "|" + "|".join("---" for _ in cols) + "|"]
        for e in edges:
            out.append("| " + " | ".join(md_cell(e.get(c)) for c in cols) + " |")
        out.append("")
    return "\n".join(out).rstrip() + "\n", blobs


def parse_md(path) -> dict:
    """Read back what dump_md wrote. The provenance stamp is deliberately not restored."""
    import base64
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeError as e:
        sys.exit(f"error: Markdown graph is not valid UTF-8: {path} ({e})")
    lines = text.split("\n")
    data, section, cur, i = {}, None, None, 0
    nodes, figures, edges = [], {}, []

    def put(target, key, value):
        target[key] = md_scalar(key, value) if isinstance(value, str) else value

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("## "):
            section = ln[3:].strip().split(" (")[0].lower()
            cur = None
            i += 1
            continue
        if ln.startswith("# "):
            data["title"] = ln[2:].strip()
            i += 1
            continue
        if ln.startswith("### "):
            key = re.match(r"###\s+`([^`]*)`(?:\s+—\s+(.*))?$", ln)
            if key:
                if section == "nodes":
                    cur = {"id": key.group(1)}
                    if key.group(2):
                        cur["label"] = key.group(2).strip()
                    nodes.append(cur)
                elif section == "figures":
                    cur = {}
                    figures[key.group(1)] = cur
            i += 1
            continue
        m = re.match(r"-\s+([A-Za-z_][A-Za-z_0-9]*):\s?(.*)$", ln)
        if m:
            k, v = m.group(1), m.group(2)
            if section == "source":
                pass                                   # recorded for the reader, never restored
            elif section == "meta":
                data.setdefault("meta", {})[k] = v
            elif cur is not None:
                put(cur, k, v)
            elif section == "graph":
                put(data, k, v)
            i += 1
            continue
        m = re.match(r"([A-Za-z_][A-Za-z_0-9]*):$", ln)
        if m and i + 1 < len(lines):
            k, j, buf = m.group(1), i + 1, []
            while j < len(lines) and not lines[j].strip():
                j += 1
            while j < len(lines) and lines[j].startswith(">"):
                buf.append(lines[j][2:] if lines[j].startswith("> ") else lines[j][1:])
                j += 1
            if buf:
                (cur if cur is not None else data)[k] = "\n".join(buf)
                i = j
                continue
        # a reformatting editor may also drop the outer pipes; inside the Edges section a line
        # with a pipe in it is a table line either way, since nothing else lives there
        if section == "edges" and "|" in ln:
            if md_is_rule(ln):
                i += 1
                continue
            cells = [c.strip().replace("\\|", "|") for c in ln.strip().strip("|").split("|")]
            if not edges and "source" in cells:
                data["_edge_cols"] = cells
            else:
                cols = data.get("_edge_cols") or []
                e = {}
                for c, val in zip(cols, cells):
                    if val != "":
                        e[c] = md_scalar(c, val)
                if e:
                    edges.append(e)
            i += 1
            continue
        i += 1

    data.pop("_edge_cols", None)
    base_dir = Path(path).resolve().parent
    for key, f in figures.items():
        rel = f.pop("image", None)
        if rel:
            candidate = Path(rel)
            if candidate.is_absolute():
                print(f"warning: {key} image path is absolute and was ignored: {rel}")
                continue
            p = (base_dir / candidate).resolve()
            try:
                p.relative_to(base_dir)
            except ValueError:
                print(f"warning: {key} image path escapes the Markdown folder and was ignored: {rel}")
                continue
            if p.is_file():
                mime = next((m for m, e in MIME_EXT.items() if p.suffix.lower() == e), "image/jpeg")
                f["uri"] = f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
            else:
                print(f"warning: {key} image not found at {p} — the graph keeps the "
                      f"reference, so restoring the folder brings the figure back")
    data["nodes"] = nodes
    data["edges"] = edges
    if figures:
        data["figures"] = {k: v for k, v in figures.items() if v}
    return data


def remove_path(path: Path) -> None:
    """Remove a staged file, directory, or symlink without masking the original error."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def commit_md_export(dest: Path, staged_md: Path, staged_fig_dir,
                     fig_dir_name: str) -> None:
    """Commit a validated Markdown export without deleting unrelated figure assets."""
    target_fig_dir = dest.parent / fig_dir_name
    try:
        if staged_fig_dir:
            if target_fig_dir.is_symlink() or (
                    target_fig_dir.exists() and not target_fig_dir.is_dir()):
                raise OSError(f"figure destination is not a directory: {target_fig_dir}")
            target_fig_dir.mkdir(parents=True, exist_ok=True)
            for staged in staged_fig_dir.iterdir():
                os.replace(staged, target_fig_dir / staged.name)
        os.replace(staged_md, dest)
    except OSError as e:
        raise RuntimeError(f"could not commit Markdown export: {e}") from e


def reject_output_collision(dest: Path, graph: Path, sources=None) -> None:
    """Prevent an output path from replacing the graph or any source file."""
    output = dest.resolve()
    inputs = [graph]
    inputs.extend(Path(s) for s in (sources or []))
    for item in inputs:
        if output == item.expanduser().resolve():
            sys.exit(f"error: output path {dest} is also an input ({item}); choose another output")


def do_export_md(args) -> None:
    src = Path(args.graph)
    data = load_graph(src)
    errors, warnings = validate(data)
    if args.strict and warnings:
        errors.extend(f"strict mode: {w}" for w in warnings)
        warnings = []
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    dest = Path(args.export_md).expanduser().resolve()
    reject_output_collision(dest, src)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.exit(f"error: could not create Markdown destination folder {dest.parent}: {e}")
    fig_dir_name = dest.stem + ".figures"
    try:
        text, blobs = dump_md(data, fig_dir_name, embed=args.md_embed)
    except (ValueError, binascii.Error) as e:
        sys.exit(f"error: could not export Markdown: {e}")

    # Stage the Markdown and its figure folder first. The parser reads the staged copy,
    # so a failed round-trip cannot leave a half-written destination or stale assets.
    try:
        with tempfile.TemporaryDirectory(prefix=f".{dest.stem}-export-", dir=dest.parent) as raw:
            stage = Path(raw)
            staged_md = stage / dest.name
            staged_md.write_text(text, encoding="utf-8")
            for rel, blob in blobs.items():
                p = stage / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(blob)

            back = parse_md(staged_md)
            diff = md_diff(md_normalise(data), md_normalise(back))
            if diff:
                print("error: the Markdown does not round-trip; the export would lose information:",
                      file=sys.stderr)
                for d in diff[:20]:
                    print(f"  {d}", file=sys.stderr)
                if len(diff) > 20:
                    print(f"  … and {len(diff) - 20} more", file=sys.stderr)
                sys.exit(1)

            staged_fig_dir = stage / fig_dir_name if blobs else None
            commit_md_export(dest, staged_md, staged_fig_dir, fig_dir_name)
    except RuntimeError as e:
        sys.exit(f"error: {e}")

    kb = sum(len(b) for b in blobs.values()) / 1024
    figs = f", {len(blobs)} figure file(s) in {fig_dir_name}/ ({kb:.0f} KB)" if blobs else ""
    print(f"ok: {len(data.get('nodes', []))} nodes, {len(data.get('edges', []))} edges "
          f"-> {dest}{figs}")
    print(f"    round-trip verified; rebuild with: "
          f"python3 {Path(__file__).name} {dest} -o out.html --source <paper.pdf>")


# ---------------------------------------------------------------- modes

def load_graph(path: Path) -> dict:
    """A graph arrives as JSON, as the Markdown export, or embedded in an already-built page."""
    if not path.exists():
        sys.exit(f"error: graph file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".md":
        return parse_md(path)
    if suffix in (".html", ".htm"):
        return load_embedded(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeError as e:
        sys.exit(f"error: graph file is not valid UTF-8: {path} ({e})")
    except json.JSONDecodeError as e:
        sys.exit(f"error: graph JSON does not parse: {e}")
    if not isinstance(data, dict):
        sys.exit("error: graph root must be a JSON object")
    return data


def load_embedded(html_path: Path) -> dict:
    try:
        source = html_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"error: built HTML not found: {html_path}")
    except UnicodeError as e:
        sys.exit(f"error: built HTML is not valid UTF-8: {html_path} ({e})")
    m = re.search(r"^const DATA = (.*);$", source, re.M)
    if not m:
        sys.exit(f"error: no embedded graph found in {html_path}")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        sys.exit(f"error: embedded graph JSON does not parse in {html_path}: {e}")
    if not isinstance(data, dict):
        sys.exit(f"error: embedded graph in {html_path} is not an object")
    return data


def write_atomic(path: Path, text: str) -> None:
    """Write text through a sibling temporary file, then replace the destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def emit_validation(errors: list, warnings: list, strict: bool = False) -> list:
    """Print validation diagnostics and return the effective hard errors."""
    hard = list(errors)
    visible_warnings = list(warnings)
    if strict:
        hard.extend(f"strict mode: {w}" for w in visible_warnings)
        visible_warnings = []
    for w in visible_warnings:
        print(f"warning: {w}")
    for e in hard:
        print(f"error: {e}", file=sys.stderr)
    return hard


def do_validate(args) -> None:
    data = load_graph(Path(args.graph))
    errors, warnings = validate(data)
    hard = emit_validation(errors, warnings, args.strict)
    if hard:
        sys.exit(1)
    print(f"ok: graph is valid ({len(data.get('nodes', []))} nodes, "
          f"{len(data.get('edges', []))} edges)")


def do_check(args) -> None:
    """Validate a graph and its sources without writing an output artifact."""
    data = load_graph(Path(args.graph))
    errors, warnings = validate(data)
    hard = emit_validation(errors, warnings, args.strict)
    if hard:
        sys.exit(1)
    if not args.source:
        sys.exit("error: --check needs at least one --source")

    try:
        result = check_against_sources(data, args.source)
    except ValueError as e:
        sys.exit(f"error: source evidence binding: {e}")
    misses, qmisses = result["misses"], result["qmisses"]
    if misses:
        report_misses(misses, hard=not args.allow_unverified)
    if qmisses:
        report_quote_misses(qmisses, hard=not args.allow_unverified)
    if misses or qmisses:
        print(f"\n{result['verified']}/{result['checked']} numbers and "
              f"{result['qverified']}/{result['quoted']} quotations match the sources.")
        if not args.allow_unverified:
            sys.exit(1)
        print("warning: --allow-unverified was used; review every exception before publishing.")

    print("checked sources:")
    for stamp in result["stamps"]:
        print(f"  {stamp['file']}  {stamp['sha256'][:12]}")
    print(f"ok: {result['verified']}/{result['checked']} numbers and "
          f"{result['qverified']}/{result['quoted']} quotations verified")


def do_verify(args) -> None:
    built = Path(args.verify)
    data = load_embedded(built)
    errors, warnings = validate(data)
    hard = emit_validation(errors, warnings, args.strict)
    if hard:
        sys.exit(1)
    stamp = data.get("source")
    if not isinstance(stamp, dict):
        sys.exit(f"error: {built.name} was built without --source, so there is nothing to verify "
                 "against. Rebuild it with --source to make it checkable.")
    was = stamp.get("files") or [stamp]
    if (not isinstance(was, list) or not was or not all(isinstance(w, dict) for w in was)
            or any(not isinstance(w.get("sha256"), str) or len(w["sha256"]) != 64 for w in was)):
        sys.exit(f"error: {built.name} has an invalid source stamp; rebuild it")
    try:
        result = check_against_sources(data, args.source)
    except ValueError as e:
        sys.exit(f"error: source evidence binding: {e}")
    now = result["stamps"]
    pages = result["pages"]
    print("graph built from :")
    for w in was:
        print(f"  {w['file']}  {w['sha256'][:12]}")
    print(f"  (built {stamp.get('built', '?')})")
    print("source files now :")
    for f in now:
        print(f"  {f['file']}  {f['sha256'][:12]}  (modified {f['modified']})")
    if [w["sha256"] for w in was] != [f["sha256"] for f in now]:
        print("\nSOURCES CHANGED since this graph was built. The results below describe the current "
              "source files; rebuild to refresh the graph's provenance.")
    checked, misses = result["checked"], result["misses"]
    quoted, qmisses, located = result["quoted"], result["qmisses"], result["located"]
    # a quotation that has moved page is not a failure — the paper was re-typeset, not falsified —
    # but one that is no longer in the paper at all is exactly what this check exists to catch
    moved = [(n.get("id"), n.get("quote_page"), located[n.get("id")][1])
             for n in (data.get("nodes") or [])
             if n.get("quote_page") and located.get(n.get("id"))
             and located[n.get("id")][1] != n.get("quote_page")]
    if misses:
        report_misses(misses, hard=False)
    if qmisses:
        report_quote_misses(qmisses, hard=False)
    if misses or qmisses:
        print(f"\n{checked - len(misses)}/{checked} numbers and "
              f"{quoted - len(qmisses)}/{quoted} quotations still match the sources.")
        sys.exit(1)
    for nid, was_p, now_p in moved:
        print(f"note: node '{nid}' quotation moved from p.{was_p} to p.{now_p}")
    print(f"\nok: all {checked} numbers and {quoted} quotation(s) still appear in the sources")


def do_build(args) -> None:
    data = load_graph(Path(args.graph))
    dest = Path(args.output).expanduser().resolve()
    reject_output_collision(dest, Path(args.graph), args.source)

    errors, warnings = validate(data)
    # Do not spend time extracting a PDF when the graph itself cannot render.
    if errors or (args.strict and warnings):
        if emit_validation(errors, warnings, args.strict):
            sys.exit(1)
    checked = verified = 0
    quoted = qverified = 0
    if args.source:
        try:
            result = check_against_sources(data, args.source)
        except ValueError as e:
            sys.exit(f"error: source evidence binding: {e}")
        stamps = result["stamps"]
        checked, misses = result["checked"], result["misses"]
        verified = result["verified"]
        if misses:
            report_misses(misses, hard=not args.allow_unverified)
            if not args.allow_unverified:
                sys.exit(1)
        # A quotation is the claim itself, so finding it word for word ties the node to one
        # sentence on one page — which the number check cannot do, since it only ever confirms
        # that a number exists somewhere in the paper, not that it belongs to what it was
        # attached to. The page is looked up rather than written down: one less thing to get wrong.
        quoted, qmisses, located = result["quoted"], result["qmisses"], result["located"]
        qverified = result["qverified"]
        for n in data.get("nodes") or []:
            hit = located.get(n.get("id"))
            node_result = result["node_results"].get(n.get("id"), {})
            n.pop("quote_page", None)
            n.pop("quote_file", None)
            if hit:
                n["quote_file"], n["quote_page"] = hit[0], hit[1]
            n["numbers_checked"] = node_result.get("numbers_checked", 0)
            n["numbers_verified"] = node_result.get("numbers_verified", 0)
            evidence_count = n["numbers_checked"] + int(node_result.get("quote_checked", False))
            evidence_verified = (n["numbers_verified"]
                                 + int(node_result.get("quote_verified", False)))
            n["verification_status"] = (
                "no_evidence" if evidence_count == 0 else
                "matched" if evidence_verified == evidence_count else "partial")
        if qmisses:
            report_quote_misses(qmisses, hard=not args.allow_unverified)
            if not args.allow_unverified:
                sys.exit(1)
        data["source"] = {
            "file": " + ".join(f["file"] for f in stamps),
            "sha256": stamps[0]["sha256"],
            "files": stamps,
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "numbers_checked": checked,
            "numbers_verified": verified,
            "quotes_checked": quoted,
            "quotes_verified": qverified,
        }
    else:
        # A graph loaded from an HTML/Markdown export may carry an old provenance
        # record and generated quotation locations. Without a fresh source check those
        # values are not evidence and must not be displayed as if they were current.
        data.pop("source", None)
        for n in data.get("nodes") or []:
            if isinstance(n, dict):
                n.pop("verification_status", None)
                n.pop("numbers_checked", None)
                n.pop("numbers_verified", None)
                n.pop("quote_page", None)
                n.pop("quote_file", None)
        warnings.append("built without --source, so no number in this graph has been checked "
                        "against the paper, and the page cannot be re-verified later")

    hard = emit_validation(errors, warnings, args.strict)
    if hard:
        sys.exit(1)

    tpl = Path(args.template) if args.template else \
        Path(__file__).resolve().parent.parent / "assets" / "template.html"
    if not tpl.exists():
        sys.exit(f"error: template not found: {tpl}")

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page_title = data.get("short_title") or data.get("title") or "论文逻辑图谱"
    try:
        template = tpl.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        sys.exit(f"error: could not read template {tpl}: {e}")
    out = (template.replace("__PAPER_TITLE__", html.escape(page_title))
                  .replace("__GRAPH_JSON__", payload))
    try:
        write_atomic(dest, out)
    except OSError as e:
        sys.exit(f"error: could not write HTML to {dest}: {e}")

    spine = sum(1 for e in data["edges"] if e.get("main"))
    qtail = f", {qverified}/{quoted} quotes located" if quoted else ""
    tail = (f", {verified}/{checked} numbers verified{qtail} against {data['source']['file']}"
            if args.source else ", UNVERIFIED")
    print(f"ok: {len(data['nodes'])} nodes, {len(data['edges'])} edges "
          f"({spine} on the main spine){tail} -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graph", nargs="?", help="path to the graph JSON")
    ap.add_argument("-o", "--output", help="output HTML path")
    ap.add_argument("--source", action="append", metavar="FILE",
                    help="the paper itself (PDF or extracted .txt) to check numbers against. "
                         "Repeat it for a paper that has a supplement — a graph legitimately cites "
                         "both, and numbers are looked up across all of them")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="build even though some numbers were not found in the source")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--verify", metavar="BUILT_HTML",
                       help="re-check an already-built page against the current source file")
    modes.add_argument("--export-md", metavar="OUT_MD",
                       help="write the graph as round-trippable Markdown instead of building. "
                            "The input may be a graph JSON, a previous .md, or a built .html")
    modes.add_argument("--validate", action="store_true",
                       help="validate graph structure without rendering an HTML page")
    modes.add_argument("--check", action="store_true",
                       help="validate a graph and its source files without writing HTML")
    ap.add_argument("--md-embed", action="store_true",
                    help="with --export-md, inline the figures as base64 in the Markdown "
                         "instead of writing them beside it (one big file, nothing to lose)")
    ap.add_argument("--strict", action="store_true",
                    help="treat validation warnings as errors (useful in CI and batch builds)")
    ap.add_argument("--template", help="override the renderer template")
    args = ap.parse_args()

    if args.verify:
        if args.graph:
            ap.error("--verify takes the built HTML path as its value; do not pass a graph argument")
        if not args.source:
            ap.error("--verify needs --source")
        if args.allow_unverified or args.md_embed or args.template:
            ap.error("--verify only accepts --source and --strict")
        do_verify(args)
        return
    if args.export_md:
        if not args.graph:
            ap.error("--export-md needs a graph to export")
        if args.source or args.allow_unverified or args.template:
            ap.error("--export-md does not verify sources or use a renderer template; use --check or build separately")
        do_export_md(args)
        return
    if args.validate:
        if not args.graph:
            ap.error("--validate needs a graph")
        if args.output:
            ap.error("--validate does not write an output file; remove -o")
        if args.source or args.allow_unverified or args.md_embed or args.template:
            ap.error("--validate only checks graph structure; use --check for source verification")
        do_validate(args)
        return
    if args.check:
        if not args.graph:
            ap.error("--check needs a graph")
        if not args.source:
            ap.error("--check needs at least one --source")
        if args.output:
            ap.error("--check does not write an output file; remove -o")
        if args.md_embed or args.template:
            ap.error("--check does not export Markdown or render HTML; remove --md-embed/--template")
        do_check(args)
        return
    if not args.graph or not args.output:
        ap.error("give a graph and -o OUTPUT (or use --export-md / --verify / --validate / --check)")
    do_build(args)


if __name__ == "__main__":
    main()

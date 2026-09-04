#!/usr/bin/env python3
"""Regression tests for argument-map and literature-map.

    python3 tests/run_tests.py

What these do NOT test is whether a graph is a faithful reading of its paper. That takes
reading the paper, and no cheap test substitutes for it.

What they do test is every guarantee the two skills actually make: that a fabricated number is
caught, that a paraphrased quotation is caught, that a broken spine is reported, that the
Markdown carries everything back, that a Markdown file reformatted by an ordinary editor still
builds. Those are the claims the whole project rests on, and they have already been broken once
— a table-parsing rule was fixed in one script and left wrong in the other, and nothing noticed.

Everything runs against a synthetic fixture, so there is no PDF dependency and no network.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AM = HERE.parent / "scripts" / "build_graph.py"
LM = HERE.parent.parent / "literature-map" / "scripts" / "build_corpus.py"
PAPER = HERE / "fixture_paper.txt"
GRAPH = HERE / "fixture_graph.json"

PASS, FAIL, SKIP = [], [], []


def run(*args, expect=0):
    """Run a build script and return (exit code, stdout+stderr)."""
    p = subprocess.run([sys.executable, *[str(a) for a in args]],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "ok  " if cond else "FAIL"
    print(f"  {mark}  {name}" + (f"\n         {detail}" if not cond and detail else ""))


def skip(name, detail=""):
    SKIP.append(name)
    print(f"  skip  {name}" + (f"\n         {detail}" if detail else ""))


def embedded(html: Path, var="DATA") -> dict:
    t = html.read_text(encoding="utf-8")
    i = t.index(f"const {var} = ") + len(f"const {var} = ")
    return json.loads(t[i:t.index("\n", i)].rstrip().rstrip(";"))


def broken(tmp: Path, name: str, mutate) -> Path:
    """A copy of the fixture graph with one thing deliberately wrong."""
    d = json.loads(GRAPH.read_text(encoding="utf-8"))
    mutate(d)
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="argmap-tests-"))
    try:
        print("\nbuild and verification")
        out = tmp / "ok.html"
        code, log = run(AM, GRAPH, "-o", out, "--source", PAPER)
        check("a valid graph builds", code == 0 and out.exists(), log.strip()[-300:])
        m = re.search(r"(\d+)/(\d+) numbers verified", log)
        check("every number is checked and found", bool(m) and m.group(1) == m.group(2),
              log.strip()[-200:])
        q = re.search(r"(\d+)/(\d+) quotes located", log)
        check("every quotation is located", bool(q) and q.group(1) == q.group(2) and int(q.group(2)) == 3,
              log.strip()[-200:])
        numbers_in_fixture = int(m.group(2)) if m else -1

        data = embedded(out) if out.exists() else {}
        src = data.get("source", {})
        rendered = out.read_text(encoding="utf-8") if out.exists() else ""
        check("the generated page includes node search", 'id="bt-search"' in rendered
              and 'id="search-input"' in rendered)
        check("the generated page has no remote script tag",
              not re.search(r'<script[^>]+src=["\']https?://', rendered, re.I))
        check("the source is stamped with a hash", len(src.get("sha256", "")) == 64)
        by_id = {n["id"]: n for n in data.get("nodes", [])}
        check("the page of a quotation is found, not authored",
              by_id.get("bg", {}).get("quote_page") == 2,
              f"got {by_id.get('bg', {}).get('quote_page')!r}, the fixture puts it on page 2")
        check("a quotation broken across a hyphen is still found",
              by_id.get("prob", {}).get("quote_page") == 2,
              "'substan-\\ntial' in the source vs 'substantial' in the quote")

        code, log = run(AM, "--verify", out, "--source", PAPER)
        check("a fresh build re-verifies", code == 0 and "still appear in the sources" in log)

        code, log = run(AM, "--check", GRAPH, "--source", PAPER)
        check("--check verifies a graph without writing HTML",
              code == 0 and "15/15 numbers" in log and "3/3 quotations" in log
              and not list(tmp.glob("*.html.check")), log.strip()[-300:])

        scoped_source = tmp / "supplement.txt"
        scoped_source.write_text("The supplement reports a response of 3.45(2) units and a sample mass of 21.7 mg.", encoding="utf-8")
        scoped = broken(tmp, "scoped", lambda d: d["nodes"][3].update(
            detail_en="The response is 3.45 units.", evidence_file="supplement.txt"))
        code, log = run(AM, "--check", scoped, "--source", PAPER, "--source", scoped_source)
        check("a node can scope evidence to one source file", code == 0 and "14/14 numbers" in log,
              log.strip()[-300:])
        bad_scope = broken(tmp, "bad-scope", lambda d: d["nodes"][3].update(evidence_file="missing.txt"))
        code, log = run(AM, "--check", bad_scope, "--source", PAPER)
        check("an unknown evidence source fails clearly", code == 1 and "evidence_file" in log,
              log.strip()[-300:])

        status_page = tmp / "status.html"
        code, log = run(AM, GRAPH, "-o", status_page, "--source", PAPER)
        status_data = embedded(status_page) if status_page.exists() else {}
        check("a verified build records per-node evidence status",
              code == 0 and all(n.get("verification_status") in {"matched", "partial", "no_evidence"}
                                for n in status_data.get("nodes", [])))
        code, log = run(AM, GRAPH, "-o", PAPER, "--source", PAPER)
        check("a build refuses to overwrite its source", code == 1 and "output" in log.lower(),
              log.strip()[-300:])

        print("\nwhat must be refused")
        bad = broken(tmp, "badnum", lambda d: d["nodes"][3].update(
            detail_en="The response is 9.87 units."))
        code, log = run(AM, bad, "-o", tmp / "badnum.html", "--source", PAPER)
        check("a fabricated number fails the build", code == 1)
        check("...and the failing node is named", "'res'" in log, log.strip()[-200:])
        check("...and no file is written", not (tmp / "badnum.html").exists())
        code, log = run(AM, "--check", bad, "--source", PAPER)
        check("--check fails on a fabricated number", code == 1 and "9.87" in log,
              log.strip()[-300:])

        allow = broken(tmp, "allow", lambda d: d["nodes"][3].update(
            detail_en="The response is 9.87 units."))
        code, log = run(AM, "--check", allow, "--source", PAPER, "--allow-unverified")
        check("--check can explicitly report an allowed extraction exception",
              code == 0 and "allow-unverified" in log and "13/14" in log,
              log.strip()[-400:])

        bad = broken(tmp, "badquote", lambda d: d["nodes"][4].update(
            quote="the widget is unambiguously dominated by the third neighbour"))
        code, log = run(AM, bad, "-o", tmp / "badquote.html", "--source", PAPER)
        check("a paraphrased quotation fails the build", code == 1)
        check("...and the divergence is diagnosed",
              "matches the paper for its first" in log or "characters are in the paper" in log,
              log.strip()[-400:])

        bad = broken(tmp, "translated", lambda d: d["nodes"][0].update(
            quote_en="An identical molecular field acts on all the sites"))
        code, log = run(AM, bad, "-o", tmp / "translated.html", "--source", PAPER)
        check("a translated quotation is refused", code == 1 and "must not be translated" in log,
              log.strip()[-200:])

        def cut_spine(d):
            for e in d["edges"]:
                if e["source"] == "prob":
                    e.pop("main", None)
        bad = broken(tmp, "spine", cut_spine)
        code, log = run(AM, bad, "-o", tmp / "spine.html", "--source", PAPER)
        check("a spine in two pieces is reported", "entry points" in log or "not reachable" in log,
              log.strip()[-300:])

        bad = broken(tmp, "isolated", lambda d: d["nodes"].append(
            {"id": "orphan", "type": "result", "label": "孤儿", "detail": "连不上任何东西。"}))
        code, log = run(AM, bad, "-o", tmp / "isolated.html", "--source", PAPER)
        check("a node connected to nothing is reported", "isolated nodes" in log and "orphan" in log,
              log.strip()[-400:])

        # A cycle attached to an otherwise valid root-to-tip path used to pass because
        # the old validator only looked at the number of roots and tips.
        bad = broken(tmp, "cycle", lambda d: d["edges"].append(
            {"source": "meth", "target": "prob", "relation": "refutes", "main": True}))
        code, log = run(AM, bad, "-o", tmp / "cycle.html", "--source", PAPER)
        check("an attached cycle fails the build", code == 1 and "cycle" in log.lower(),
              log.strip()[-400:])

        # A diamond is intentional: branches may split and rejoin, as long as the
        # renderer still has one unambiguous entry and exit.
        diamond = broken(tmp, "diamond", lambda d: (
            d["nodes"].append({"id": "res2", "type": "result", "label": "另一结果",
                                "detail": "另一结果与原文相同。"}),
            d["edges"].extend([
                {"source": "meth", "target": "res2", "relation": "produces", "main": True},
                {"source": "res2", "target": "concl", "relation": "supports", "main": True},
            ])))
        code, log = run(AM, "--validate", diamond)
        check("a branching spine that rejoins is valid", code == 0, log.strip()[-300:])

        print("\ninput and CLI validation")
        bad_root = tmp / "bad-root.json"
        bad_root.write_text("[1, 2, 3]", encoding="utf-8")
        code, log = run(AM, bad_root, "-o", tmp / "bad-root.html")
        check("a non-object graph gets a readable error",
              code == 1 and "graph root must be a JSON object" in log and "Traceback" not in log,
              log.strip()[-300:])
        bad_node = broken(tmp, "bad-node", lambda d: d["nodes"].__setitem__(0, "not an object"))
        code, log = run(AM, bad_node, "-o", tmp / "bad-node.html")
        check("a malformed node gets a readable error",
              code == 1 and "nodes[0] must be an object" in log and "Traceback" not in log,
              log.strip()[-300:])
        bad_edge = broken(tmp, "bad-edge", lambda d: d["edges"].__setitem__(0, "not an object"))
        code, log = run(AM, bad_edge, "-o", tmp / "bad-edge.html")
        check("a malformed edge gets a readable error",
              code == 1 and "edges[0] must be an object" in log and "Traceback" not in log,
              log.strip()[-300:])
        strict = broken(tmp, "strict", lambda d: d["nodes"].append(
            {"id": "orphan-strict", "type": "result", "label": "孤儿", "detail": "没有边。"}))
        code, log = run(AM, "--validate", strict, "--strict")
        check("strict validation promotes warnings to errors", code == 1 and "strict mode" in log,
              log.strip()[-300:])
        bad_figure = broken(tmp, "bad-figure", lambda d: (
            d.update(figures={"fig1": {"label": "Figure 1"}}),
            d["nodes"][0].update(figure="fig1")))
        code, log = run(AM, "--validate", bad_figure)
        check("a referenced figure without an image is rejected",
              code == 1 and "without an image URI" in log, log.strip()[-300:])
        code, log = run(AM, "--validate", GRAPH, "--source", PAPER)
        check("structure-only validation rejects a misleading source option",
              code == 2 and "use --check" in log, log.strip()[-300:])
        code, log = run(AM, "--check", GRAPH, "--source", PAPER, "-o", tmp / "check.html")
        check("source checking rejects an output option",
              code == 2 and "does not write an output file" in log, log.strip()[-300:])

        code, log = run(AM, GRAPH, "-o", tmp / "unver.html")
        check("building with no source still works, marked unverified",
              code == 0 and "UNVERIFIED" in log, log.strip()[-200:])
        if (tmp / "unver.html").exists():
            unver = embedded(tmp / "unver.html")
            check("an unverified rebuild drops stale provenance",
                  "source" not in unver and all("quote_page" not in n and "quote_file" not in n
                                                 for n in unver.get("nodes", [])))

        print("\nmarkdown round trip")
        md = tmp / "rt.md"
        code, log = run(AM, out, "--export-md", md)
        check("the export round-trips before it is written", code == 0 and md.exists(),
              log.strip()[-300:])
        rebuilt = tmp / "rt.html"
        code, log = run(AM, md, "-o", rebuilt, "--source", PAPER)
        check("the Markdown builds back", code == 0 and rebuilt.exists(), log.strip()[-300:])

        if rebuilt.exists():
            a, b = embedded(out), embedded(rebuilt)
            strip = lambda d: {k: v for k, v in d.items() if k != "source"}
            check("the rebuilt graph is identical", strip(a) == strip(b),
                  "fields differ between the original build and the one from Markdown")
            pipe = next((n for n in b["nodes"] if n["id"] == "meth"), {})
            check("a pipe inside prose survives", "| pipe |" in pipe.get("detail_en", ""),
                  f"got {pipe.get('detail_en')!r}")
            check("both languages survive", pipe.get("detail") and pipe.get("detail_en"))

        no_source_md = tmp / "no-source-from-md.html"
        code, log = run(AM, md, "-o", no_source_md)
        check("Markdown rebuilt without a source is visibly unverified",
              code == 0 and "UNVERIFIED" in log and no_source_md.exists(), log.strip()[-300:])
        if no_source_md.exists():
            no_source_data = embedded(no_source_md)
            check("...and does not retain Markdown quotation pages",
                  "source" not in no_source_data and all("quote_page" not in n
                                                         for n in no_source_data.get("nodes", [])))

        # what an editor does to a Markdown table: alignment colons, padding, no outer pipes
        ref = tmp / "reformatted.md"
        lines = []
        for ln in md.read_text(encoding="utf-8").split("\n"):
            if re.match(r"^\|[\s\-:|]+\|$", ln) and "-" in ln:
                lines.append("| " + " | ".join([":---"] * (ln.count("|") - 1)) + " |")
            elif ln.startswith("|"):
                # padded, and with the outer pipes dropped — what a formatter actually does
                cells = ln.strip().strip("|").split("|")
                lines.append(" | ".join(f"{c.strip():<12}" for c in cells))
            else:
                lines.append(ln)
        ref.write_text("\n".join(lines), encoding="utf-8")
        code, log = run(AM, ref, "-o", tmp / "ref.html", "--source", PAPER)
        check("a table reformatted by an editor still builds", code == 0, log.strip()[-300:])
        if (tmp / "ref.html").exists():
            check("...with every edge intact",
                  len(embedded(tmp / "ref.html")["edges"]) == len(embedded(out)["edges"]))

        # An unsupported image MIME must be rejected without touching an existing file.
        badfig = broken(tmp, "badfig", lambda d: (
            d.update(figures={"unknown": {"uri": "data:image/x-unknown;base64,AQID"}}),
            d["nodes"][0].update(figure="unknown")))
        keep = tmp / "keep.md"
        keep.write_text("previous export", encoding="utf-8")
        oldfig = tmp / "keep.figures"
        oldfig.mkdir()
        (oldfig / "old.bin").write_bytes(b"old")
        code, log = run(AM, badfig, "--export-md", keep)
        check("a failed Markdown export leaves the destination untouched",
              code == 1 and keep.read_text(encoding="utf-8") == "previous export",
              log.strip()[-400:])
        check("...and leaves old figure assets untouched", (oldfig / "old.bin").exists())

        print("\nliterature-map")
        if not LM.exists():
            skip("literature-map integration (optional)", f"not found at {LM}")
        else:
            corpus = tmp / "corpus.json"
            code, log = run(LM, "--corpus", corpus, "--from-md", md, "--search", HERE)
            check("a paper imports from single-paper Markdown", code == 0 and corpus.exists(),
                  log.strip()[-300:])
            if corpus.exists():
                c = json.loads(corpus.read_text(encoding="utf-8"))
                stamped = (c["papers"][0].get("source") or {}).get("numbers_verified")
                check("...and its stamp is re-earned, not inherited",
                      stamped == numbers_in_fixture,
                      f"numbers_verified={stamped!r}, the build found {numbers_in_fixture}")
                cmd = tmp / "corpus.md"
                code, log = run(LM, "--corpus", corpus, "--export-md", cmd)
                check("the corpus round-trips to Markdown", code == 0 and cmd.exists(),
                      log.strip()[-300:])
                code, log = run(LM, "--corpus", cmd, "-o", tmp / "map.html")
                check("the corpus Markdown builds back", code == 0, log.strip()[-300:])

        print("\nshared library")
        sys.path.insert(0, str(AM.parent))
        import paperlib as pl
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 2"}]}, "The measured value is 12.34.")
        check("numeric verification rejects a substring of a larger value",
              count == 1 and misses and misses[0][-1] == "2")
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 1e-3"}]}, "The measured value is 1e-3.")
        check("numeric verification keeps scientific notation together", count == 1 and not misses)
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 1e-3"}]}, "The measured value is 1 e - 3.")
        check("numeric verification tolerates PDF spacing inside a token", count == 1 and not misses)
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 1e-4"}]}, "The measured value is 1e-3.")
        check("numeric verification rejects a wrong exponent", count == 1 and misses)
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 10%"}]}, "The measured value is 10 units.")
        check("numeric verification does not drop a percentage sign", count == 1 and misses)
        count, misses = pl.check_numbers(
            {"nodes": [{"id": "x", "detail": "值为 10%"}]}, "The measured value is 10 %.")
        check("numeric verification tolerates a spaced percentage sign", count == 1 and not misses)
        check("an alignment row is not a table row", pl.md_is_rule("| :--- | ---: |"))
        check("a dashed data row is still data", not pl.md_is_rule("| a-b | c |"))
        _, _, pages = pl.gather_full([PAPER])
        check("a quotation across a line break is found",
              pl.locate_quote("An identical molecular field acts on all the sites", pages))
        check("a quotation the paper does not contain is not found",
              pl.locate_quote("the widget is unambiguously the best", pages) is None)
        check("dash style is normalised away, a different word is not",
              pl.squash("spin-orbit") == pl.squash("spin\u2013orbit")
              and pl.squash("net") != pl.squash("nontrivial"))
        side, kept, rest = pl.diverges_at("An identical molecular field acts on every site", pages)
        check("a quote that diverges late is diagnosed from the start",
              side == "start" and kept > 20 and "all" in rest,
              f"side={side} matched={kept} source continues {rest[:40]!r}")
        side, kept, rest = pl.diverges_at(
            "the widget is unambiguously dominated by the third neighbour", pages)
        check("a quote that diverges early is diagnosed from the end",
              side == "end" and kept > 20 and "widget" in rest,
              f"side={side} matched={kept} preceded by {rest[-40:]!r}")

        print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
        for f in FAIL:
            print(f"  failed: {f}")
        return 1 if FAIL else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

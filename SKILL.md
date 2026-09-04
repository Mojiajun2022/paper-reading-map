---
name: argument-map
description: "Build a source-grounded, interactive 3D argument map from an academic paper PDF or extracted text. Use when the user asks for a paper's logic chain, argument structure, research-gap-to-conclusion path, knowledge graph, mind map, or help understanding a paper (论文逻辑、论证链、知识图谱、论文结构、思维导图); do not use for an abstract-only summary, ordinary translation, or a cross-paper literature map."
---

# Paper to 3D Argument Map

Turn one paper's reasoning into a self-contained interactive HTML graph. The graph is a model of
the paper's claims and evidence, not a decorative 3D illustration. A reader should be able to
follow the marked spine from motivation to conclusion and inspect why each edge is justified.

## Scope And Routing

Use this skill when the user wants any of the following:

- the argument or logic chain inside one paper;
- the research gap, question, method, evidence, and conclusion connected together;
- a knowledge graph, mind map, or interactive visualization of a paper;
- a careful explanation of how a paper reaches its main claim.

Do not activate it for an abstract-only summary, ordinary translation, formatting unrelated to a
paper's reasoning, or relationships among multiple papers. If the request mixes a summary and a
map, produce the map and include a concise prose summary in the final response.

## Non-Negotiable Contract

- Read the whole paper in scope. Never construct the graph from the abstract alone.
- Use only values, names, conditions, and claims supported by the paper. Write `not reported in
  the paper` when a field would otherwise require invention.
- Include the primary PDF and any supplement, appendix, or data file that contains load-bearing
  evidence.
- Build with `--source` whenever a source file is available. A page built without a source is
  visibly unverified and is not a finished source-grounded deliverable.
- When multiple sources are supplied, set `evidence_file` and, when needed, `evidence_page` on a
  node whose claim belongs to one source. Treat an invalid or ambiguous binding as a build error.
- Copy quotations verbatim from the paper. Never translate, paraphrase, or hand-author a quotation
  page number.
- If `--allow-unverified` is needed because text extraction dropped a value, state every affected
  node and the reason in the final response.
- Deliver the HTML path, verification status, and a short prose walk-through of the spine.

## Phase 1: Read The Paper

Identify the input files first. Treat a supplement as part of the source when the argument relies
on it. A source can be a PDF or an extracted UTF-8 text file; PDFs are checked through
`pdftotext`.

Read the paper in argument order, not just section order. Record a scratch outline containing:

1. field context and the specific gap;
2. the question, failure mode, or competing explanation;
3. the hypothesis or design choice and why it addresses the gap;
4. every independent measurement, derivation, control, baseline, or ablation;
5. the result of each test and the claim it supports or refutes;
6. limitations, boundary conditions, and open questions.

If the PDF reader imposes a page limit, read in batches of no more than 20 pages and cover the
whole paper. For a very long paper, read the introduction, methods, results, discussion, and
conclusion carefully; skim only material that cannot affect the argument, such as the reference
list.

Do not infer exact values from plot pixels. Attach the relevant figure if it helps the reader, but
say that the value is not text-verified when the paper does not state it in extractable text.

## Phase 2: Model The Argument

Build the spine before adding supporting detail.

### Spine

Mark the load-bearing route by setting `main: true` on its edges. The spine may be a line, a
diamond, or another branch-and-rejoin structure:

- branches are valid when independent strands converge on a result;
- branches are valid when one result supports claims that are tested separately;
- the main graph must be acyclic;
- it must have exactly one entry point and one endpoint;
- every main node must be reachable from the entry point.

Do not flatten a real diamond into a line merely to fit a template. Conversely, do not mark every
interesting detail as main. A method that rules out a competing explanation before the central
measurement belongs on the spine because later claims depend on it.

### Supporting Nodes

Add method components, controls, baselines, individual experiments, metrics, ablations,
limitations, and future work as supporting nodes. Every node must connect directly or transitively
to the spine. Remove nodes that add context but support no part of the argument.

Use the number of nodes the paper supports. Fifteen to thirty-five is common, but it is not a
target. A review may have no experiments; a position paper may have no results; a theory paper may
have no dataset. Do not invent a stage to satisfy a taxonomy.

### Node Quality

For each node:

- `label` is a compact concept, not a sentence. Keep it within the renderer's 32 half-width-unit
  budget; a CJK character counts as two units.
- `detail` is normally 2-4 sentences. Name the object, measurement, condition, and claim. State
  which measurement each number belongs to.
- `section` points to the paper location, such as `Section 3.2`, `Table 2`, or `page 5`.
- `importance` is `3` for spine-critical, `2` for supporting, and `1` for peripheral detail.
- `quote` is one short load-bearing sentence copied exactly from the paper. Keep it on one page
  and away from a figure caption or column boundary when possible.

Preserve reported precision. Do not silently round, convert units, or turn `22 of 24` into `92%`.
If a derived value is useful, retain the source values and label the derivation explicitly; the
derived numeral still has to appear in the source or be explicitly approved with
`--allow-unverified` after manual confirmation.

### Language

If the user wants a bilingual graph, provide matching fields such as `label` / `label_en`,
`detail` / `detail_en`, `title` / `title_en`, `summary` / `summary_en`, and edge `label` /
`label_en`. Both versions must preserve the same values, measurements, and meaning. Do not create
`quote_en` or `quote_zh`: a quotation has one canonical form, the paper's own words.

If the user wants one language only, omit the twins rather than producing a poor translation. The
renderer falls back to the bare field when a language twin is absent.

## Phase 3: Validate And Verify

Write a working JSON graph first. Run structural validation before spending time on PDF checks:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" --validate graph.json
python3 "$SKILL_DIR/scripts/build_graph.py" --validate graph.json --strict
```

`--validate` checks graph structure, field types, spine topology, figure references, and renderer
constraints. It does not check whether claims appear in a paper. `--strict` promotes warnings such
as missing details, unknown types, duplicate edges, and isolated nodes to errors.

Run the complete source check without writing an HTML file when iterating on the graph:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" \
  --check graph.json \
  --source paper.pdf \
  --source paper-supplement.pdf
```

`--check` verifies every numeric token in the supported text fields and every `quote` against the
current sources. It is useful for CI and for checking Markdown edits before rendering. By default a
node searches all supplied sources; `evidence_file` and `evidence_page` restrict that node to one
source basename and one-based extracted page.

If a source check fails:

1. Re-open the paper and correct a misread value or quotation.
2. If the value is present only in a table or special glyph that `pdftotext` dropped, confirm it
   visually and use `--allow-unverified` only for that extraction failure.
3. Never use `--allow-unverified` to make an invented number or paraphrased quotation pass.
4. Record every exception in the final response.

## Phase 4: Build The Deliverable

Build with every source file in scope:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" graph.json \
  -o paper-argument-map.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The builder creates one self-contained HTML file. It embeds the graph, the renderer, and any valid
`data:image/...` figures. It records source fingerprints, build time, numeric verification counts,
quotation counts, and located quotation pages.

Re-check a built page later with:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" \
  --verify paper-argument-map.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The source may be a re-typeset copy. A quotation moving to a new page is reported but is not a
failure; a number or quotation that disappears is a failure.

## Figures

Attach paper figures when they make a node easier to inspect. Put them in a top-level `figures`
map and reference them from a node:

```json
{
  "figures": {
    "fig3": {
      "uri": "data:image/jpeg;base64,...",
      "label": "Figure 3"
    }
  },
  "nodes": [
    {
      "id": "result",
      "type": "result",
      "label": "Core result",
      "detail": "Figure 3 shows the result; the paper does not report exact endpoint values in text.",
      "figure": "fig3"
    }
  ]
}
```

Use a crop that includes the caption and inspect it before delivery. External image URLs are
rejected so the generated HTML remains offline-capable. Supported image data must use a recognized
image MIME type and valid base64 when `;base64` is present.

## Markdown Maintenance

Export Markdown when a graph will be reviewed or maintained by people:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" \
  paper-argument-map.html \
  --export-md paper-argument-map.md
```

The export includes nodes, edges, language fields, figures, and a human-readable provenance record.
The exporter stages files in a temporary directory, parses the staged Markdown back, compares it
field by field, and only then replaces the destination. Figures normally live in a matching
`.figures/` directory; use `--md-embed` for a single-file Markdown artifact.

Rebuild after edits:

```bash
python3 "$SKILL_DIR/scripts/build_graph.py" \
  paper-argument-map.md \
  -o rebuilt.html \
  --source paper.pdf
```

An old provenance record in Markdown is for reference only. A rebuild without `--source` removes
stale verification metadata and produces a visibly unverified page.

## Graph Vocabulary

Node types:

`background`, `related`, `problem`, `hypothesis`, `method`, `experiment`, `result`, `conclusion`,
`limitation`, `future`.

Edge relations:

`motivates`, `addresses`, `proposes`, `uses`, `produces`, `supports`, `refutes`, `leads_to`,
`compares`, `limits`.

Edges may also carry `reason`, `reason_en`, and `reason_zh`. These are human-written explanations
of why the source node supports, motivates, refutes, or otherwise relates to the target. The
builder preserves and displays them; it does not prove the relation automatically.

Use `stage` when the paper's actual argument order differs from the default type order. A method
used to eliminate a rival explanation may belong before the main experiment.

Minimal graph shape:

```json
{
  "title": "The full paper title",
  "title_en": "The full paper title",
  "short_title": "Short title",
  "summary": "One sentence describing what the paper did and found.",
  "meta": {
    "authors": "First Author et al.",
    "venue": "NeurIPS",
    "year": "2024"
  },
  "nodes": [
    {
      "id": "gap",
      "type": "problem",
      "importance": 3,
      "label": "Research gap",
      "detail": "State the gap with the paper's concrete object, measurement, and condition.",
      "section": "Section 1"
    }
  ],
  "edges": [
    {
      "source": "gap",
      "target": "method",
      "relation": "addresses",
      "label": "addresses",
      "main": true
    }
  ]
}
```

## Delivery Checklist

Before responding to the user, confirm:

- the output HTML exists at the requested location;
- the graph passed `--validate` and, when appropriate, `--strict`;
- the graph passed `--check` or was built with `--source`;
- every `--allow-unverified` exception is listed;
- the HTML is self-contained and contains no external runtime dependency;
- the main spine is explained in prose from entry to endpoint;
- the page was opened or otherwise inspected when preview tooling is available.

The page supports orbit, pan, zoom, node selection, details, figures, upstream/downstream links,
type filters, spine-only mode, node search with `/` and arrow keys, a stable Reading view ordered
along the main spine, previous/next spine navigation, language and theme settings, browser printing,
and PNG export. Use the Reading view when the graph is dense, when WebGL is unavailable, or when a
printable record is needed. Relation `reason` fields are displayed as author-provided explanations;
they are not automatically proved.

## Development Checks

Before changing scripts, run:

```bash
python3 "$SKILL_DIR/tests/run_tests.py"
python3 -m py_compile "$SKILL_DIR/scripts/paperlib.py" \
  "$SKILL_DIR/scripts/build_graph.py" \
  "$SKILL_DIR/tests/run_tests.py"
```

For a release-style check, run:

```bash
python3 "$SKILL_DIR/scripts/release_check.py"
```

This standard-library-only gate checks repository shape, README language, template
self-containment, the tutorial example, source verification, compilation, and regression tests.

The regression suite uses synthetic text fixtures and no network or PDF dependency. It covers
numeric token boundaries, scientific notation, exact quotations, spine cycles and diamonds,
malformed input, strict validation, the no-output `--check` mode, Markdown round trips, atomic
exports, stale provenance removal, figure handling, and optional `literature-map` integration. A
missing sibling `literature-map` is a skipped integration, not a failure of this standalone skill.

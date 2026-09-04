# argument-map

[English](README.md) | [简体中文](README.zh-CN.md)

<div align="center">

**Turn dense papers into an argument you can see.**

Source-checked claims. Interactive 3D reasoning. One self-contained HTML file.

[![CI](https://github.com/Mojiajun2022/argument-map/actions/workflows/ci.yml/badge.svg)](https://github.com/Mojiajun2022/argument-map/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Mojiajun2022/argument-map?style=flat&logo=github)](https://github.com/Mojiajun2022/argument-map/stargazers)
[![License](https://img.shields.io/github/license/Mojiajun2022/argument-map)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

[**Open the live demo**](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/argument-map/main/demo.html) | [Download demo HTML](demo.html) | [Quick start](#quick-start)

![argument-map demo](overview.png)

<sub>If this helps you read one difficult paper faster, <a href="https://github.com/Mojiajun2022/argument-map">give it a star</a> and share it with a researcher.</sub>

</div>

`argument-map` is a Codex skill and a small local build tool for understanding the structure of
one academic paper. It connects the paper's motivation, research gap, question, method, evidence,
results, conclusion, limitations, and open questions in a graph that a reader can inspect step by
step.

The output is a single HTML file with an interactive WebGL scene. It contains the graph data, the
renderer, and any attached figures, so it can be opened offline and shared as a standalone file.

> The graph is a structured reading of a paper, not an automated peer review. The builder can
> verify that a number appears in the source and that a quotation is exact; it cannot decide
> whether the overall argument was interpreted correctly.

## What It Does

- Extracts a paper's argument from background to conclusion.
- Marks a load-bearing argument spine with `main: true` edges.
- Preserves real branch-and-rejoin reasoning instead of forcing every paper into a flat list.
- Checks numeric tokens in node labels and details against the source text, with optional per-node
  source file and page scope.
- Locates verbatim quotations and records their source file and page.
- Shows per-node evidence status: `matched`, `partial`, `no_evidence`, or `unverified`.
- Embeds source fingerprints, verification counts, and build time in the HTML.
- Supports JSON for machine editing and Markdown for human review and version control.
- Provides node details, figures, upstream/downstream navigation, edge reasons, type filters,
  spine-only mode, node search, a scrollable Reading view, main-spine previous/next navigation,
  language and theme settings, printing, and PNG export.
- Keeps the generated page self-contained. The default renderer loads no CDN, external JavaScript,
  external stylesheet, or remote image.

## What It Does Not Do

- It does not replace reading the paper.
- It does not infer exact values from plot pixels.
- It does not prove that an edge represents a valid causal or logical relationship.
- It does not automatically build relationships among several papers. That is a separate
  cross-paper workflow.

## Quick Start

There are two ways to use the project.

### Option A: Ask Codex

Attach a paper PDF and ask for its argument structure. For an explicit invocation, use:

```text
$argument-map Turn this paper into a source-checked 3D argument map. Read the full paper, mark the main spine, and explain the spine in prose.
```

Include the supplement or appendix when it contains evidence used by the paper's conclusion. A
good request can also specify the desired language, output directory, or whether figures should be
attached.

The skill should return:

1. a self-contained HTML graph;
2. a short explanation of the main spine;
3. the source verification status;
4. a list of any values that required `--allow-unverified`.

### Option B: Build Locally

Create a graph JSON file and build it against the paper:

```bash
python3 scripts/build_graph.py graph.json \
  -o paper-argument-map.html \
  --source paper.pdf
```

For a paper with a supplement, repeat `--source`:

```bash
python3 scripts/build_graph.py graph.json \
  -o paper-argument-map.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

## CLI Reference

The script has five mutually exclusive modes. The input graph can be JSON, Markdown, or a
previously built HTML page, depending on the mode.

| Command | Writes a file? | Source verification? | Use it when |
| --- | --- | --- | --- |
| `python3 scripts/build_graph.py graph.json -o out.html --source paper.pdf` | Yes, HTML | Yes | You want the final interactive page. |
| `python3 scripts/build_graph.py --validate graph.json` | No | No | You are checking graph structure only. |
| `python3 scripts/build_graph.py --check graph.json --source paper.pdf` | No | Yes | You are iterating or running CI before rendering. |
| `python3 scripts/build_graph.py graph.json --export-md graph.md` | Yes, Markdown | No | You want a human-editable graph copy. |
| `python3 scripts/build_graph.py --verify out.html --source paper.pdf` | No | Yes | You are auditing an existing HTML artifact. |

Common options:

| Option | Meaning |
| --- | --- |
| `--source FILE` | Add a PDF or UTF-8 text source. Repeat it for supplements. |
| `--strict` | Treat structural warnings as errors. |
| `--allow-unverified` | Continue after a manually confirmed extraction failure. |
| `--md-embed` | Keep figures inline when exporting Markdown. |
| `--template FILE` | Use a compatible local renderer template. |

Exit status is `0` for success, `1` for graph/source/build failure, and `2` for invalid command
line usage. The script never sends source files over the network.

The source checker accepts optional per node scope fields. Set `evidence_file` to the exact
basename of one supplied source and `evidence_page` to its one based extracted page number when a
claim must be checked in one place. An invalid or ambiguous binding fails the check instead of
falling back to another file.

## Detailed Tutorial

This section is a complete workflow for a first build. It uses the included tutorial files, so it
can be run without downloading a real paper.

### 1. Check the Environment

The graph builder uses only the Python standard library. PDF verification additionally needs
Poppler's `pdftotext`.

Check the tools:

```bash
python3 --version
pdftotext -v
```

On macOS, install Poppler with Homebrew if necessary:

```bash
brew install poppler
```

On Debian or Ubuntu:

```bash
sudo apt-get install poppler-utils
```

If a PDF is scanned, OCR it before building, or export its text as UTF-8 and pass that text file
as `--source`. An empty or non-extractable PDF is rejected rather than silently treated as a
verified source.

### 2. Prepare the Source Files

Keep the main paper and every load-bearing supplement together. A node that cites a calibration
table, derivation, or control experiment from a supplement must be checked against that supplement.

The `--source` option accepts:

- a PDF, extracted with `pdftotext`;
- a UTF-8 text file, useful after OCR or custom extraction.

Plain text sources are treated as one page unless they contain form-feed page separators. PDF page
numbers are based on the extracted document pages, not necessarily the printed page label in the
paper.

### 3. Read Before Modeling

Read the full paper before writing the graph. While reading, make a scratch outline:

1. What field or problem is the paper entering?
2. What precise gap, failure mode, or competing explanation motivates the work?
3. What question must be answered?
4. What method or hypothesis addresses that question?
5. Which measurements, experiments, controls, baselines, or derivations provide evidence?
6. Which result supports or refutes which claim?
7. What are the limitations and open questions?

Do not turn the paper's section headings into nodes automatically. A node is useful only when it
plays a role in the reasoning.

### 4. Write the Graph JSON

Start from the included example:

```bash
cp examples/tutorial-graph.json my-graph.json
```

Open `my-graph.json` and replace the tutorial content with the paper's claims. The central design
choice is the spine. A common spine looks like this:

```text
background -> problem -> hypothesis -> method -> experiment -> result -> conclusion
```

That is a guide, not a required template. A review may have no experiments. A theory paper may
replace experiments with a derivation. A position paper may move directly from a problem to a
proposal and implications.

Use supporting nodes for controls, baselines, measurements, ablations, limitations, and future
work. Connect every supporting node to the spine. Remove context that does not support a claim.

For a paper with independent evidence strands, use a diamond instead of inventing a false linear
order:

```text
                 -> experiment A ->
method -> shared result              -> conclusion
                 -> experiment B ->
```

The `main` edges may branch and rejoin, but they must be acyclic, connected, and have exactly one
entry point and one endpoint. This makes the start and end markers unambiguous in the renderer.

### 5. Validate the Graph Structure

Run the lightweight structural check first:

```bash
python3 scripts/build_graph.py --validate my-graph.json
```

For a release or CI check, promote warnings to errors:

```bash
python3 scripts/build_graph.py --validate my-graph.json --strict
```

This catches malformed nodes and edges, duplicate IDs, invalid references, duplicate edges,
invalid stages, missing figure data, unsafe figure keys, isolated nodes, and invalid spine
topology. It does not read the paper and cannot verify claims.

### 6. Check Claims Against the Paper

Use `--check` while iterating. It performs the full source check without writing HTML:

```bash
python3 scripts/build_graph.py \
  --check my-graph.json \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The command checks:

- numbers in `label`, `detail`, `label_en`, `label_zh`, `detail_en`, and `detail_zh`;
- every `quote` field;
- quotation locations and source pages;
- all supplied source files and their fingerprints.

A successful result looks like:

```text
checked sources:
  paper.pdf  8d4c2a1f09ab
ok: 42/42 numbers and 8/8 quotations verified
```

If a number is rejected, first check whether it was misread, rounded, converted, or inferred. If a
quotation is rejected, copy it again from the PDF and shorten it if it crosses a column, figure
caption, or page break.

Only use `--allow-unverified` when you have manually confirmed that a source extractor lost a value
or damaged a quotation. For example:

```bash
python3 scripts/build_graph.py \
  --check my-graph.json \
  --source paper.pdf \
  --allow-unverified
```

This command reports the shortfall and exits successfully, but the resulting graph is not fully
verified. Document every exception before sharing it.

The builder adds `numbers_checked`, `numbers_verified`, and `verification_status` to every node.
It adds `quote_file` and `quote_page` when a quotation is located. `matched` means every supplied
number and quotation for that node was found; `partial` means the build continued with an allowed
failure; `no_evidence` means there was no numeric token or quotation to check. A graph built
without `--source` is shown as unverified and does not inherit old generated status fields.

### 7. Build the HTML Page

Once the graph passes the checks, build the page:

```bash
mkdir -p build
python3 scripts/build_graph.py my-graph.json \
  -o build/paper-argument-map.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The output is one HTML file. It contains the graph data and renderer, and can be opened directly:

```bash
open build/paper-argument-map.html       # macOS
xdg-open build/paper-argument-map.html   # Linux
```

On Windows, open the file in a browser normally or use `start` from a command prompt.

### 8. Add Figures When They Help

Figures are optional. Attach a paper figure when it makes a node easier to inspect, especially for
results whose exact values are visible only in a plot.

The graph stores images as data URIs:

```json
{
  "figures": {
    "fig3": {
      "uri": "data:image/png;base64,...",
      "label": "Figure 3"
    }
  },
  "nodes": [
    {
      "id": "result",
      "type": "result",
      "label": "Core result",
      "detail": "Figure 3 shows the trend. The paper does not report exact endpoint values in text.",
      "figure": "fig3"
    }
  ]
}
```

To create a base64 payload on macOS or Linux:

```bash
printf 'data:image/png;base64,' > figure-uri.txt
base64 < figure.png | tr -d '\\n' >> figure-uri.txt
```

Paste the resulting value into the JSON, or use a small local script to generate the JSON safely.
Crop the figure with its caption, inspect the crop, and keep it reasonably small. External image
URLs are rejected because the final HTML must remain self-contained.

### 9. Review the Page

The page provides:

- drag to orbit the 3D scene;
- right-click or middle-click drag, or `Shift` drag, to pan;
- scroll or a two-finger gesture to zoom;
- click a node for its detail, quotation, source page, figure, and neighboring nodes;
- click legend chips to filter node types;
- use `Spine only` to fade non-spine content;
- click the search icon or press `/` to search IDs, labels, sections, and details;
- use arrow keys to select a search result, `Enter` to open it, and `Escape` to close search;
- use settings to switch interface language and theme;
- export a PNG with the paper title and provenance line.

Switch to `Reading` for a stable, scrollable presentation of every node. Main spine nodes appear in
root-to-tip order, followed by supporting material. Each row includes details, evidence status,
quotation, figure, and incoming/outgoing relations. Optional edge `reason` fields explain why the
relation holds. The arrow controls move through the main spine, and `Print reading view` prints the
reading layout instead of the WebGL canvas.

The header provenance line is part of the artifact. It tells the reader which source files were
used, which short hashes identify them, and how many numeric values and quotations were verified.

### 10. Export Markdown for Review

Export a readable Markdown copy when the graph will be edited or reviewed:

```bash
python3 scripts/build_graph.py \
  build/paper-argument-map.html \
  --export-md build/paper-argument-map.md
```

By default, images are written beside it in:

```text
build/paper-argument-map.figures/
```

Use `--md-embed` for a single Markdown file with images kept inline:

```bash
python3 scripts/build_graph.py \
  build/paper-argument-map.html \
  --export-md build/paper-argument-map.md \
  --md-embed
```

The exporter stages files in a temporary directory, parses the Markdown back, compares it field by
field, and replaces the destination only after the round trip succeeds. A failed export does not
overwrite an existing Markdown file or leave a partial figure directory.

### 11. Rebuild After Editing

Edit the Markdown, then rebuild it against the current source:

```bash
python3 scripts/build_graph.py \
  build/paper-argument-map.md \
  -o build/rebuilt.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The old provenance record in Markdown is for human reference only. A rebuild must check the source
again and earns a new provenance record. Rebuilding without `--source` removes stale verification
metadata and marks the output as unverified.

### 12. Verify a Shared or Older Page

Re-check an existing HTML artifact against the current source files:

```bash
python3 scripts/build_graph.py \
  --verify build/paper-argument-map.html \
  --source paper.pdf \
  --source paper-supplement.pdf
```

The command reports source fingerprint changes and quotation page moves. A missing number or
quotation causes verification to fail.

### 13. Run the Release Gate

Before publishing the skill, run the standard-library release checker:

```bash
python3 scripts/release_check.py
```

It checks the repository files, English README, skill metadata, JSON evaluations, tutorial graph,
source verification, Python syntax, regression suite, and a temporary self-contained HTML build.
It does not publish anything or modify repository files. For the optional browser suite, install
Playwright and point `ARGMAP_BROWSER` at a local Chromium or Chrome executable:

```bash
NODE_PATH=/path/to/playwright/node_modules \
ARGMAP_BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
node tests/browser_smoke.cjs
```

## Graph Data Reference

### Top-Level Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `title` | Recommended | string | Full title shown in the page header. |
| `title_en`, `title_zh` | Optional | string | Language-specific title fallbacks. |
| `short_title` | Optional | string | Compact browser title and PNG filename basis. |
| `summary` | Optional | string | One-sentence paper summary. |
| `summary_en`, `summary_zh` | Optional | string | Language-specific summary fallbacks. |
| `meta` | Optional | object | Usually `authors`, `venue`, and `year`. |
| `nodes` | Required | array | Argument claims, evidence, and context. |
| `edges` | Required | array | Reasoning relationships between nodes. |
| `figures` | Optional | object | Embedded figure data keyed by figure ID. |

### Node Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `id` | Yes | string | Unique stable identifier used by edges. |
| `label` | Yes | string | Short concept shown next to the node. |
| `label_en`, `label_zh` | Optional | string | Language-specific label fallbacks. |
| `type` | Recommended | string | One of the supported node types below. Unknown types render as `Other`. |
| `detail` | Recommended | string | Evidence-rich text shown in the detail panel. |
| `detail_en`, `detail_zh` | Optional | string | Language-specific detail fallbacks. |
| `section` | Optional | string | Paper location, such as `Section 3.2` or `Table 2`. |
| `importance` | Optional | integer | `1` peripheral, `2` supporting, `3` spine-critical. |
| `stage` | Optional | number | Explicit horizontal position; fractional values are allowed. |
| `quote` | Optional | string | One exact sentence from the paper. Never translate it. |
| `figure` | Optional | string | Key in the top-level `figures` map. |
| `evidence_file` | Optional | string | Exact basename of the source used for this node's checks. |
| `evidence_page` | Optional | integer | One based extracted page within `evidence_file`. |
| `quote_file` | Generated | string | Source file where the quote was located. |
| `quote_page` | Generated | integer | Source page where the quote was located. |
| `numbers_checked` | Generated | integer | Numeric tokens checked in this node. |
| `numbers_verified` | Generated | integer | Numeric tokens found for this node. |
| `verification_status` | Generated | string | `matched`, `partial`, or `no_evidence`. |

Supported node types:

```text
background  related  problem  hypothesis  method
experiment  result   conclusion  limitation  future
```

### Edge Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `source` | Yes | string | ID of the preceding node. |
| `target` | Yes | string | ID of the node that follows. |
| `relation` | Recommended | string | Semantic relationship from the list below. |
| `label` | Optional | string | Short verb shown on the edge when a node is focused. |
| `label_en`, `label_zh` | Optional | string | Language-specific edge label fallbacks. |
| `reason`, `reason_en`, `reason_zh` | Optional | string | Human explanation of why the relation holds. |
| `main` | Optional | boolean | Set to `true` for a spine edge. |

Supported edge relations:

```text
motivates  addresses  proposes  uses  produces
supports   refutes    leads_to  compares  limits
```

### Authoring Rules

- Keep labels conceptual rather than sentence-like.
- Keep labels within the renderer's 32 half-width-unit budget.
- Use 2-4 sentences in each detail field when the claim needs explanation.
- Name the measurement, sample, condition, dataset, or model associated with every number.
- Preserve the paper's precision. Do not silently round, convert units, or invent percentages.
- Use `not reported in the paper` instead of filling an absent value.
- Keep one quotation in one readable source region whenever possible.
- Use `stage` when the paper's argument order differs from the default type order.
- Do not create artificial experiment or result nodes for paper types that do not contain them.

## Verification Semantics

The builder performs two different checks.

### Numeric Presence Check

It checks whether each numeric token in supported text fields appears in the source. It handles
common thousands separators, percentages, integer and `.0` forms, scientific notation, and spaces
introduced by PDF extraction.

This is a presence check, not semantic attribution. A number can appear somewhere in the paper and
still be attached to the wrong node. That is why details must identify which measurement produced
the number, and why a quotation is useful for a load-bearing claim.

### Exact Quotation Check

The builder normalizes whitespace, compatibility forms, and typesetting dash variants. It also
handles ordinary line-break hyphens. It does not accept a changed word, a missing sentence, or a
quotation that becomes ambiguous across a page or figure-caption boundary.

### Provenance Check

Each source is fingerprinted with SHA-256. A page records the source names, hashes, build time, and
verification counts. When a source changes, `--verify` checks the current text and tells the reader
whether the page is merely stale or contains a claim that can no longer be found.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `pdftotext is not installed` | Poppler is missing. | Install Poppler or pass extracted text. |
| `contains no extractable text` | The PDF is scanned or protected. | OCR it and pass the extracted text or a new PDF. |
| A number is not found | The value was misread, transformed, or dropped by extraction. | Check the PDF, preserve the reported value, or document a manual `--allow-unverified` exception. |
| A quotation is not found | It was paraphrased, translated, or crosses a layout boundary. | Copy it exactly and shorten it to one source region. |
| `entry points` or `endpoints` error | The main edges have multiple roots or tips. | Make branches rejoin, or mark only the true load-bearing path as main. |
| `spine contains a cycle` | Main edges point back to an earlier node. | Remove the loop; an argument spine must flow forward. |
| `isolated nodes` warning | A node has no connection to the argument. | Connect it to a claim it supports or remove it. |
| `missing figure` or external image error | The node reference or image URI is invalid. | Add a valid embedded `data:image/...` figure. |
| Markdown rebuild loses a figure | The matching `.figures/` directory is missing. | Restore the directory or use `--md-embed`. |
| `--strict` rejects an otherwise buildable graph | A warning was promoted to an error. | Fix the warning or use non-strict mode for exploratory work. |
| Page opens but cannot draw 3D | WebGL is unavailable. | Use a WebGL-capable browser; the page will show a fallback message. |

## CI and GitHub Release Checklist

Before committing or publishing the skill, run:

```bash
python3 scripts/release_check.py
python3 scripts/build_graph.py --validate examples/tutorial-graph.json --strict
python3 scripts/build_graph.py --check examples/tutorial-graph.json \
  --source examples/tutorial-paper.txt
python3 scripts/build_graph.py examples/tutorial-graph.json \
  -o /tmp/argument-map-tutorial.html \
  --source examples/tutorial-paper.txt
python3 tests/run_tests.py
python3 -m py_compile scripts/paperlib.py scripts/build_graph.py tests/run_tests.py
```

Also inspect the generated HTML for:

- external `script`, `link`, `img`, or CSS URL references;
- a visible source provenance line;
- a nonblank WebGL canvas;
- a working node detail panel;
- a working search field;
- correct figures and language fallbacks.

Before making a repository public:

- add a project license appropriate for your intended use;
- inspect embedded figures and metadata for sensitive material;
- keep generated outputs in an ignored build directory unless they are intentional examples;
- do not commit source PDFs that you do not have permission to redistribute;
- document any known `--allow-unverified` exceptions.

The included `.gitignore` excludes common local caches, bytecode, and build output directories.

For a single release gate, run:

```bash
python3 scripts/release_check.py
```

The release checker uses only the standard library. It verifies required files, the English README,
the self-contained template, the tutorial graph, source verification, Python compilation, the
regression suite, and a temporary HTML build. It does not publish anything or modify repository
files.

## Examples

The included tutorial graph is a small synthetic example that can be built end to end:

```bash
python3 scripts/build_graph.py --validate examples/tutorial-graph.json
python3 scripts/build_graph.py --check examples/tutorial-graph.json \
  --source examples/tutorial-paper.txt
python3 scripts/build_graph.py examples/tutorial-graph.json \
  -o build/tutorial.html \
  --source examples/tutorial-paper.txt
```

The repository also includes pre-built screenshots from a real paper:

![Full argument map](overview.png)

![Spine only](spine.png)

## Development

Run the regression suite:

```bash
python3 tests/run_tests.py
```

The suite uses synthetic text fixtures and no network or PDF dependency. It covers numeric token
boundaries, scientific notation, PDF spacing, exact quotations, quotation diagnostics, spine
cycles and diamonds, malformed input, strict validation, the no-output `--check` mode, Markdown
round trips, atomic exports, stale provenance removal, figure handling, generated-page
self-containment, and optional `literature-map` integration.

The optional browser suite requires Playwright and an installed Chromium or Chrome executable. It
checks the rendered canvas, Reading view, search, keyboard navigation, figures, language switching,
mobile layout, and the no-WebGL fallback:

```bash
NODE_PATH=/path/to/playwright/node_modules \
ARGMAP_BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
node tests/browser_smoke.cjs
```

The script writes screenshots to a temporary directory unless `ARGMAP_SCREENSHOTS` is set. It does
not upload the paper or generated graph anywhere.

Validate the skill metadata with the bundled skill validator when it is available:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py .
```

The validator may require PyYAML. The graph builder itself does not.

## Repository Layout

```text
argument-map/
|-- SKILL.md                  Codex workflow and generation requirements
|-- agents/openai.yaml        UI metadata and default invocation prompt
|-- scripts/build_graph.py    validate, check, build, verify, and export
|-- scripts/paperlib.py       shared text, numeric, quotation, and Markdown utilities
|-- scripts/release_check.py  local release gate
|-- assets/template.html      self-contained WebGL renderer
|-- examples/                 copyable tutorial graph and source text
|-- tests/run_tests.py        regression tests
|-- evals/evals.json          trigger evaluations for realistic user requests
`-- docs/                     example screenshots
```

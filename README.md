# Paper Reading Map

[English](README.md) | [Chinese](README.zh-CN.md)

<div align="center">

**Read difficult papers faster, one claim at a time.**

Paper Reading Map turns a paper into a source-checked, interactive map: follow the main argument, branch into evidence, click any node for its explanation and quotation, and inspect figures in context.

[![CI](https://github.com/Mojiajun2022/paper-reading-map/actions/workflows/ci.yml/badge.svg)](https://github.com/Mojiajun2022/paper-reading-map/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Mojiajun2022/paper-reading-map?style=flat&logo=github)](https://github.com/Mojiajun2022/paper-reading-map/stargazers)
[![License](https://img.shields.io/github/license/Mojiajun2022/paper-reading-map)](LICENSE)

[**Try the live demo**](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/paper-reading-map/main/demo.html) | [Download `demo.html`](demo.html) | [Chinese guide](README.zh-CN.md)

![Paper Reading Map](overview.png)

</div>

## What you get

- **Main spine:** see the paper's problem -> method -> evidence -> conclusion at a glance.
- **Branching evidence:** separate accuracy, ablation, comparison, or limitation paths instead of flattening them into one list.
- **Source checks:** numbers and quotations are checked against the supplied text; missing evidence is flagged.
- **Click-to-read details:** a node opens its explanation, evidence status, quotation, page, relations, and attached figures.
- **Reading view:** switch from the 3D map to a linear, citation-friendly reading order when you need it.

## Quick start

### Ask Codex

In a Codex task, attach a paper and write:

```text
Use $argument-map to build a Paper Reading Map. Keep every number and quotation traceable to the paper.
```

### Build locally

```bash
python3 scripts/build_graph.py examples/tutorial-graph.json \
  -o demo.html --source examples/tutorial-paper.txt
open demo.html
```

## Explore the example

1. Open the [live demo](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/paper-reading-map/main/demo.html).
2. Follow the main spine from the deployment question to the conclusion.
3. Notice the two evidence branches: **Accuracy check** and **Calibration check**.
4. Click **Two checks agree** to open its details and the attached map preview.
5. Use **Reading view** when you want a compact, linear explanation.

![Main spine and evidence branches](spine.png)

The demo is a real self-contained HTML file hosted from this repository. GitHub Pages can host the same file when Pages is enabled for the repository.

## Minimal graph format

```json
{
  "title": "A paper",
  "source": "paper.txt",
  "nodes": [
    {"id": "claim", "type": "conclusion", "label": "Main claim", "detail": "Traceable explanation"}
  ],
  "edges": []
}
```

Use `label_en`, `detail_en`, and `label_zh` / `detail_zh` for bilingual maps. A node may reference a local, embedded figure with `"figure": "figure-key"`.

## Verification

```bash
python3 scripts/build_graph.py --validate examples/tutorial-graph.json --strict
python3 scripts/release_check.py
```

The strict validator checks graph structure, source-backed numbers, quotations, figure references, and bilingual fields.

## CLI Reference

`python3 scripts/build_graph.py GRAPH.json -o demo.html --source paper.txt` builds a self-contained reader. Add `--validate --strict` to check a graph without writing output.

## Detailed Tutorial

Start with `examples/tutorial-paper.txt`, inspect `examples/tutorial-graph.json`, then rebuild `demo.html`. Replace the tutorial source and nodes with the paper you want to read.

## Graph Data Reference

Nodes use `id`, `type`, `label`, `detail`, and optional `quote`, `page`, `figure`, `label_en`, and `detail_en`. Edges use `source`, `target`, `relation`, and optional `main`.

## Troubleshooting

If a number or quotation is flagged, copy it from the source text exactly. If a figure is missing, use a complete `data:image/...;base64,...` URI and reference its key from the node.

## CI and GitHub Release Checklist

Run the strict validator, release checks, and browser smoke test before publishing. The generated HTML contains its renderer and figures, so it can be shared as one file.

## Project layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Codex skill instructions |
| `scripts/build_graph.py` | Validator and HTML/Markdown builder |
| `examples/` | Tutorial graph and source text |
| `demo.html` | Generated, shareable demo |
| `docs/` | Screenshots and generated documentation |

## License

MIT. See [LICENSE](LICENSE).

# Paper Reading Map（论文阅读地图）

[English](README.md) | **简体中文**

<div align="center">

**把难读的论文，变成一张可以探索的阅读地图。**

Paper Reading Map 将论文转换为经过来源核验的交互式地图：先看主线，再展开证据分支；点击节点即可查看解释、原文引文和相关图片。

[![CI](https://github.com/Mojiajun2022/paper-reading-map/actions/workflows/ci.yml/badge.svg)](https://github.com/Mojiajun2022/paper-reading-map/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Mojiajun2022/paper-reading-map?style=flat&logo=github)](https://github.com/Mojiajun2022/paper-reading-map/stargazers)
[![License](https://img.shields.io/github/license/Mojiajun2022/paper-reading-map)](LICENSE)

[**在线体验 Demo**](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/paper-reading-map/main/demo.html) · [下载 `demo.html`](demo.html) · [English](README.md)

![Paper Reading Map](overview.png)

</div>

## 你会得到什么

- **论文主线：** 一眼看到问题 → 方法 → 证据 → 结论。
- **证据分支：** 将准确率、消融、对比实验和局限分别展开，不再压成一条线。
- **来源核验：** 数字和引文会对照输入文本检查，缺少证据时会提示。
- **点击阅读：** 点击节点查看解释、证据状态、引文、页码、关系和附图。
- **阅读视图：** 需要连续阅读时，可切换到适合引用的线性顺序。

## 快速开始

### 在 Codex 中使用

在 Codex 任务中附上论文并输入：

```text
Use $argument-map to build a Paper Reading Map. Keep every number and quotation traceable to the paper.
```

### 本地生成 Demo

```bash
python3 scripts/build_graph.py examples/tutorial-graph.json \
  -o demo.html --source examples/tutorial-paper.txt
open demo.html
```

## 体验示例

1. 打开[在线 Demo](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/paper-reading-map/main/demo.html)。
2. 从部署问题沿主线走到结论。
3. 观察两个证据分支：**Accuracy check** 和 **Calibration check**。
4. 点击 **Two checks agree**，查看节点详情和附带的地图预览图。
5. 需要连贯阅读时，切换到 **Reading view**。

![论文主线与证据分支](spine.png)

这个 Demo 是仓库中的真实、自包含 HTML 文件。启用 GitHub Pages 后，也可以直接用 Pages 托管同一个文件。

## 最小图谱格式

```json
{
  "title": "一篇论文",
  "source": "paper.txt",
  "nodes": [
    {"id": "claim", "type": "conclusion", "label": "核心结论", "detail": "可追溯的解释"}
  ],
  "edges": []
}
```

双语地图可使用 `label_en`、`detail_en` 和 `label_zh` / `detail_zh`。节点可通过 `"figure": "figure-key"` 引用本地或内嵌图片。

## 验证

```bash
python3 scripts/build_graph.py --validate examples/tutorial-graph.json --strict
python3 scripts/release_check.py
```

严格验证会检查图结构、来源中的数字、引文、图片引用和双语字段。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | Codex skill 说明 |
| `scripts/build_graph.py` | 验证器和 HTML/Markdown 构建器 |
| `examples/` | 教程图谱和来源文本 |
| `demo.html` | 可分享的生成结果 |
| `docs/` | 截图和生成文档 |

## 许可证

MIT，见 [LICENSE](LICENSE)。

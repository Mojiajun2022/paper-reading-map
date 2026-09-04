# argument-map

[English](README.md) | **简体中文**

<div align="center">

**把难读的论文，变成一张可以探索的论证地图。**

核验过的论据、可交互的 3D 推理图，以及一个无需联网即可打开的 HTML 文件。

[![CI](https://github.com/Mojiajun2022/argument-map/actions/workflows/ci.yml/badge.svg)](https://github.com/Mojiajun2022/argument-map/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Mojiajun2022/argument-map?style=flat&logo=github)](https://github.com/Mojiajun2022/argument-map/stargazers)
[![License](https://img.shields.io/github/license/Mojiajun2022/argument-map)](LICENSE)

[**在线打开实例 Demo**](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/argument-map/main/demo.html) | [下载 Demo HTML](demo.html) | [英文完整文档](README.md)

![argument-map demo](overview.png)

</div>

`argument-map` 是一个 Codex skill 和本地构建工具，用来拆解一篇学术论文的完整推理链：研究背景、问题、假设、方法、证据、结果、结论、局限与开放问题。它把这些内容组织成可逐步检查的论证图。

## 它能做什么

- 从背景一路连接到结论，保留真实的分支与汇合关系。
- 用 `main: true` 标出承重的主论证线。
- 检查节点中的数字是否出现在论文原文中。
- 定位逐字引文，并自动记录来源文件和页码。
- 在 HTML 中嵌入来源指纹、核验数量和构建时间。
- 支持 JSON 编辑、Markdown 审阅和一键导出自包含 HTML。
- 提供 3D 旋转、缩放、平移、节点详情、搜索、主线筛选、阅读模式、主题切换和 PNG 导出。

## 快速开始

### 在 Codex 中使用

上传论文 PDF，然后输入：

```text
$argument-map 把这篇论文做成经过来源核验的 3D 论证地图，并解释它的主线。
```

### 在本地构建

```bash
python3 scripts/build_graph.py graph.json \
  -o paper-argument-map.html \
  --source paper.pdf
```

依赖 Python 3.9+。核验 PDF 时还需要 Poppler 的 `pdftotext`。项目本身不需要第三方 Python 包。

## 实例演示

仓库中的 Demo 使用一个 Temperature Scaling 示例，展示从假设、方法、实验到结论的完整论证链：

[打开交互式 Demo](https://htmlpreview.github.io/?https://raw.githubusercontent.com/Mojiajun2022/argument-map/main/demo.html)

Demo 是自包含 HTML，包含图数据、渲染器和核验信息，可离线保存和分享。

## 核验规则

- 数字核验是“是否出现在原文中”的检查，不代表语义归因已经正确。
- 引文必须是论文原文，不能翻译或改写。
- 不要把论文没有报告的推导值、四舍五入值或百分比伪装成原始结果。
- PDF 提取缺失时，先人工确认，再谨慎使用 `--allow-unverified`，并记录例外。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `python3 scripts/build_graph.py --validate graph.json` | 只检查图结构 |
| `python3 scripts/build_graph.py --check graph.json --source paper.pdf` | 检查数字和引文 |
| `python3 scripts/build_graph.py graph.json -o out.html --source paper.pdf` | 构建 HTML |
| `python3 scripts/build_graph.py out.html --export-md out.md` | 导出可编辑 Markdown |
| `python3 scripts/build_graph.py --verify out.html --source paper.pdf` | 重新核验已有页面 |
| `python3 scripts/release_check.py` | 运行发布门禁 |

## 开发

```bash
python3 tests/run_tests.py
python3 scripts/release_check.py
```

欢迎贡献新的论文示例、来源核验改进、无障碍交互和文档翻译。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 限制

论证图仍然需要人工阅读论文。构建器可以检查数字和引文是否存在，但不能判断整张图是否正确表达了作者的逻辑，也不会从图像像素中推断精确数值。

如果这个工具帮你更快读懂了一篇难论文，欢迎给仓库点个 Star：

[github.com/Mojiajun2022/argument-map](https://github.com/Mojiajun2022/argument-map)

#!/usr/bin/env python3
"""Run the local release checks for argument-map.

This script intentionally uses only the Python standard library. It checks repository shape,
the English README, the self-contained renderer, the tutorial example, the graph/source checks,
and the regression suite before a public release.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
REQUIRED = [
    "README.md",
    "SKILL.md",
    "agents/openai.yaml",
    "assets/template.html",
    "scripts/build_graph.py",
    "scripts/paperlib.py",
    "scripts/release_check.py",
    "examples/tutorial-graph.json",
    "examples/tutorial-paper.txt",
    "evals/evals.json",
    "docs/overview.png",
    "docs/spine.png",
    ".gitignore",
    "tests/run_tests.py",
    "tests/browser_smoke.cjs",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")


def run(label: str, *args: str, env=None) -> bool:
    command = [str(arg) for arg in args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    if result.returncode == 0:
        print(f"PASS: {label}")
        return True
    fail(label)
    output = (result.stdout + result.stderr).strip()
    if output:
        print("      " + "\n      ".join(output.splitlines()[-8:]))
    return False


def check_python_sources() -> bool:
    files = [
        ROOT / "scripts/paperlib.py",
        ROOT / "scripts/build_graph.py",
        ROOT / "scripts/release_check.py",
        ROOT / "tests/run_tests.py",
    ]
    try:
        for path in files:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except (OSError, SyntaxError) as error:
        fail(f"Python sources do not compile: {error}")
        return False
    print("PASS: Python sources compile in memory")
    return True


def main() -> int:
    failures = 0
    total = 0

    for relative in REQUIRED:
        total += 1
        if not (ROOT / relative).is_file():
            fail(f"required file is missing: {relative}")
            failures += 1
    if failures:
        return 1
    print("argument-map release checks")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    total += 1
    if any(ord(char) > 127 for char in readme):
        fail("README.md contains non-ASCII characters; keep the public README in English")
        failures += 1
    else:
        print("PASS: README.md is ASCII-only English")
    for heading in ("## CLI Reference", "## Detailed Tutorial", "## Graph Data Reference",
                    "## Troubleshooting", "## CI and GitHub Release Checklist"):
        total += 1
        if heading not in readme:
            fail(f"README.md is missing required section: {heading}")
            failures += 1

    template = (ROOT / "assets/template.html").read_text(encoding="utf-8")
    total += 1
    if "__GRAPH_JSON__" not in template or "__PAPER_TITLE__" not in template:
        fail("renderer template is missing one or more build placeholders")
        failures += 1
    else:
        print("PASS: renderer template has both build placeholders")
    total += 1
    if re.search(r"<(?:script|link|img)[^>]+(?:src|href)=[\"']https?://", template, re.I) \
            or re.search(r"url\(\s*[\"']?https?://", template, re.I):
        fail("renderer template contains an external runtime resource")
        failures += 1
    else:
        print("PASS: renderer template has no external runtime resource")

    metadata = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    total += 1
    if not all(token in metadata for token in (
        'display_name:', 'short_description:', 'default_prompt:', '$argument-map',
        'allow_implicit_invocation: true')):
        fail("agents/openai.yaml is missing required UI metadata")
        failures += 1
    else:
        print("PASS: UI metadata is complete")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    total += 1
    if not re.search(r"^name:\s+argument-map\s*$", skill, re.M) \
            or not re.search(r"^description:\s+.+$", skill, re.M):
        fail("SKILL.md frontmatter is incomplete")
        failures += 1
    else:
        print("PASS: SKILL.md frontmatter is complete")
    try:
        json.loads((ROOT / "evals/evals.json").read_text(encoding="utf-8"))
        print("PASS: trigger evaluations are valid JSON")
    except (OSError, json.JSONDecodeError) as error:
        fail(f"trigger evaluations are invalid: {error}")
        failures += 1
    total += 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    checks = [
        ("tutorial graph passes strict validation", PYTHON, "scripts/build_graph.py",
         "--validate", "examples/tutorial-graph.json", "--strict"),
        ("tutorial graph passes source verification", PYTHON, "scripts/build_graph.py",
         "--check", "examples/tutorial-graph.json", "--source", "examples/tutorial-paper.txt"),
        ("regression suite passes", PYTHON, "tests/run_tests.py"),
        ("browser test script parses", "node", "--check", "tests/browser_smoke.cjs"),
    ]
    for label, *command in checks:
        total += 1
        if not run(label, *command, env=env):
            failures += 1
    total += 1
    if not check_python_sources():
        failures += 1

    with tempfile.TemporaryDirectory(prefix="argument-map-release-") as raw:
        output = Path(raw) / "tutorial.html"
        total += 1
        if not run("tutorial HTML builds", PYTHON, "scripts/build_graph.py",
                   "examples/tutorial-graph.json", "-o", output,
                   "--source", "examples/tutorial-paper.txt", env=env):
            failures += 1
        elif not output.is_file():
            fail("tutorial build did not create an HTML file")
            failures += 1
        else:
            page = output.read_text(encoding="utf-8")
            total += 1
            if "const DATA = " not in page:
                fail("tutorial HTML does not contain embedded graph data")
                failures += 1
            elif re.search(r"<(?:script|link|img)[^>]+(?:src|href)=[\"']https?://", page, re.I):
                fail("tutorial HTML contains an external runtime resource")
                failures += 1
            else:
                print("PASS: tutorial HTML is self-contained")

    passed = total - failures
    print(f"\n{passed}/{total} release checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

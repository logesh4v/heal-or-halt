"""Build one real git repo per case: upstream TodoMVC (green) -> one developer commit on top.

Ground truth is fixed HERE, before any agent run:
  rename-placeholder   heal   input placeholder reworded in index.html (visible on first load)
  counter-bug          halt   off-by-one in the "items left" counter (a real bug)
  combo                halt   placeholder reworded AND counter bug in the same commit
  rename-clear         heal   "Clear completed" -> "Clear done" (button hidden until a todo is completed)
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOH = HERE.parents[1]
WORK = HOH / "examples-run" / "todomvc"          # git-ignored; recreated on every run
SRC = WORK / "todomvc-src"
UPSTREAM = SRC / "examples" / "javascript-es5" / "dist"
OUT = WORK / "cases"
PIN = "ff43b02e59dfa604386bb382034b2cd07c2bcd8a"  # tastejs/todomvc master on 2026-05-02, MIT licence
DEV = ["-c", "user.name=TodoMVC dev", "-c", "user.email=dev@example.com"]

PLACEHOLDER = ('placeholder="What needs to be done?"', 'placeholder="Add a task"')
COUNTER = ("var plural = activeTodos === 1 ? \"\" : \"s\";\n",
           "activeTodos = activeTodos + 1;\n        var plural = activeTodos === 1 ? \"\" : \"s\";\n")
CLEAR_TPL = ('return "Clear completed";', 'return "Clear done";')
CLEAR_HTML = ('>Clear completed</button>', '>Clear done</button>')

CASES = {
    "rename-placeholder": ("heal", "copy: friendlier input placeholder", [("index.html", PLACEHOLDER)]),
    "counter-bug": ("halt", "refactor: tidy item counter", [("template.js", COUNTER)]),
    "combo": ("halt", "copy + counter refactor", [("index.html", PLACEHOLDER), ("template.js", COUNTER)]),
    "rename-clear": ("heal", "copy: shorter clear button",
                     [("template.js", CLEAR_TPL), ("index.html", CLEAR_HTML)]),
}


def git(ws, *a):
    return subprocess.run(["git", *a], cwd=ws, check=True, capture_output=True, text=True).stdout.strip()


def build(case: str) -> Path:
    truth, msg, edits = CASES[case]
    ws = OUT / case
    shutil.rmtree(ws, ignore_errors=True)
    shutil.copytree(UPSTREAM, ws / "app")
    (ws / "tests").mkdir(parents=True)
    shutil.copy(HOH / "tests" / "conftest.py", ws / "tests" / "conftest.py")  # HoH collector hook, unchanged
    shutil.copy(HERE / "tests" / "test_todomvc_e2e.py", ws / "tests" / "test_todomvc_e2e.py")
    shutil.copy(HOH / "pytest.ini", ws / "pytest.ini")
    (ws / ".gitignore").write_text(".hoh/\n__pycache__/\n*.md\n")
    git(ws, "init", "-q", "-b", "main")
    git(ws, *DEV, "add", "-A")
    git(ws, *DEV, "commit", "-qm", "baseline: upstream TodoMVC javascript-es5 (tastejs/todomvc@ff43b02), green")
    for fname, (old, new) in edits:
        p = ws / "app" / fname
        src = p.read_text()
        assert old in src, f"{case}: '{old[:40]}' not found in {fname}"
        p.write_text(src.replace(old, new))
    git(ws, *DEV, "commit", "-qam", msg)
    (ws / ".hoh").mkdir(exist_ok=True)
    (ws / ".hoh" / "truth").write_text(truth)
    return ws


def fetch_upstream() -> None:
    """Sparse, blob-less clone of tastejs/todomvc at the pinned commit. Nothing from it is committed here."""
    if (UPSTREAM / "index.html").exists() and git(SRC, "rev-parse", "HEAD") == PIN:
        return
    shutil.rmtree(SRC, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--sparse", "--no-checkout",
                    "https://github.com/tastejs/todomvc.git", str(SRC)], check=True)
    git(SRC, "sparse-checkout", "set", "examples/javascript-es5")
    git(SRC, "checkout", "-q", PIN)


if __name__ == "__main__":
    fetch_upstream()
    for c in (sys.argv[1:] or CASES):
        print(build(c))

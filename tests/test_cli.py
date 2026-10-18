"""The single entry point: playground repo, run_repo guards, summary. No model, no AWS."""

from __future__ import annotations

import subprocess

import pytest

from hoh.agent import Group, Run, run_repo
from hoh.cli import playground, summary
from handler import Verdict


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    return playground(tmp_path_factory.mktemp("pg") / "playground")


def test_playground_is_a_green_repo_on_main(pg, capsys):
    assert (pg / "app" / "index.html").exists() and (pg / "tests" / "test_splitpay_e2e.py").exists()
    assert not (pg / "tests" / "test_cli.py").exists()  # never copies itself (no recursion)
    assert git(pg, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git(pg, "log", "-1", "--format=%s") == "baseline: green suite"


def test_run_repo_refuses_uncommitted_change(pg):
    html = pg / "app" / "index.html"
    original = html.read_text()
    html.write_text(original.replace(">Split bill<", ">Calculate shares<"))
    try:
        with pytest.raises(SystemExit, match="commit your change first"):
            run_repo(pg)
    finally:
        html.write_text(original)


def test_run_repo_refuses_non_main_branch(pg):
    git(pg, "checkout", "-qb", "feature")
    try:
        with pytest.raises(SystemExit, match="check out main"):
            run_repo(pg)
    finally:
        git(pg, "checkout", "-q", "main")


def test_summary_counts_wrong_heals(tmp_path, capsys):
    bad = Run("x", tmp_path, truth="developer", groups=[Group("loc", [{}], Verdict("heal", 0.9, "developer", "r"),
                                                            outcome="pr")])
    good = Run("y", tmp_path, truth="heal", groups=[Group("loc", [{}], Verdict("heal", 0.9, "test_author", "r"),
                                                         outcome="pr")])
    summary([bad, good])
    assert "wrong heals: 1" in capsys.readouterr().out

"""`python -m hoh`: the single entry point for the Heal or Halt agent.

    python -m hoh check                 preflight: Decider up, Bedrock answers, Chrome present
    python -m hoh playground [DIR]      create a green SplitPay repo you can break by hand (default playground/)
    python -m hoh run DIR [--base REF]  the agent on a real repo: whatever HEAD broke, heal it or halt it
    python -m hoh demo                  the 5 video cases (mutations) + a summary table
    python -m hoh mutate ID... [--redteam]   the agent on chosen Mutation Monkey cases

Every command runs the same agent (hoh.agent.heal_or_halt): suite -> collector -> Decider ->
Nova Pro veto in the grey zone -> Strands agent on Nova 2 Lite behind HealGate -> PR or issue.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from hoh.collect import ROOT

DEMO_CASES = ["btn-rename-0", "combo-rename-math", "math-multiply", "server-down", "test-typo-button"]
DEV = ["-c", "user.name=SplitPay dev", "-c", "user.email=dev@example.com"]


def check() -> bool:
    """Fail loudly before a recording, not in the middle of one."""
    from hoh.agent import AGENT_MODEL, PROFILE, REGION

    ok = True

    def line(name: str, good: bool, detail: str) -> None:
        nonlocal ok
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {name:10} {detail}", flush=True)

    try:
        from handler import backend

        name, base, auth = backend()
        probe = "/health" if name == "local" else "/v1/models"
        req = urllib.request.Request(f"{base}{probe}", headers=auth)
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (loopback or https cloud)
            line("decider", r.status == 200, f"{name}: {base} healthy")
    except Exception as exc:
        line("decider", False, f"not reachable ({type(exc).__name__}: {str(exc)[:80]}): "
                               "local -> run `make serve` and wait ~15 s; cloud -> check DECIDER_URL / DECIDER_API_KEY")
    try:
        import boto3

        t = time.perf_counter()
        boto3.Session(profile_name=PROFILE).client("bedrock-runtime", region_name=REGION).converse(
            modelId=AGENT_MODEL, messages=[{"role": "user", "content": [{"text": "Reply OK"}]}],
            inferenceConfig={"maxTokens": 3})
        line("bedrock", True, f"{AGENT_MODEL} answered in {(time.perf_counter() - t) * 1000:.0f} ms "
                              f"(profile {PROFILE}, {REGION})")
    except Exception as exc:
        line("bedrock", False, f"{type(exc).__name__}: {str(exc)[:120]}")
    chrome = Path("/Applications/Google Chrome.app")
    line("chrome", chrome.exists() or bool(shutil.which("google-chrome")), "installed Google Chrome")
    line("baseline", (ROOT / "eval" / "baseline_aria.yaml").exists(), "eval/baseline_aria.yaml")
    print("  READY" if ok else "  NOT READY", flush=True)
    return ok


def playground(dest: Path) -> Path:
    """A real git repo holding SplitPay and its tests, green on main, ready to be broken by hand."""
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "app").mkdir(parents=True)
    shutil.copy(ROOT / "demo-app" / "index.html", dest / "app" / "index.html")
    shutil.copytree(ROOT / "tests", dest / "tests",
                    ignore=shutil.ignore_patterns("__pycache__", "test_policy_bands.py", "test_gate.py", "test_cli.py"))
    shutil.copy(ROOT / "pytest.ini", dest / "pytest.ini")
    (dest / ".gitignore").write_text(".hoh/\n__pycache__/\n*.md\n")
    git = lambda *a: subprocess.run(["git", *a], cwd=dest, check=True, capture_output=True, text=True)  # noqa: E731
    git("init", "-q", "-b", "main")
    git(*DEV, "add", "-A")
    git(*DEV, "commit", "-qm", "baseline: green suite")
    env = {"HOH_ROOT": str(ROOT), "HOH_APP_DIR": str(dest / "app")}
    import os

    res = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests"], cwd=dest,
                         env={**os.environ, **env}, capture_output=True, text=True, timeout=300)
    status = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr[-200:]
    print(f"playground ready: {dest}\n  suite on main: {status}")
    print(f"  break it: edit {dest / 'app' / 'index.html'}, then\n"
          f"  git -C {dest} commit -qam \"<what you changed>\"   and   make run REPO={dest.name}")
    return dest


def summary(runs) -> None:
    print("\n=== summary")
    print(f"  {'case':22} {'truth':12} {'decision':52} outcome")
    for run in runs:
        for g in run.groups or [None]:
            decision = g.verdict.line() if g and g.verdict else "(suite green)"
            outcome = (g.outcome or "none").upper() if g else "-"
            print(f"  {run.label:22} {run.truth or '?':12} {decision[:52]:52} {outcome}")
    wrong = sum(1 for r in runs for g in r.groups if g.outcome == "pr" and r.truth not in ("", "heal"))
    print(f"  wrong heals: {wrong}")


def main(argv: list[str] | None = None) -> None:
    from hoh.agent import run_agent, run_repo

    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else "help"
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "playground":
        playground(Path(args[0]) if args else ROOT / "playground")
    elif cmd == "run":
        if not args:
            sys.exit("usage: python -m hoh run DIR [--base REF]")
        base = "HEAD~1"
        if "--base" in argv:
            base = argv[argv.index("--base") + 1]
            args = [a for a in args if a != base]
        repo = Path(args[0]) if Path(args[0]).is_absolute() else ROOT / args[0]
        summary([run_repo(repo, base=base, redteam="--redteam" in flags)])
    elif cmd == "demo":
        summary([run_agent(m) for m in DEMO_CASES])
    elif cmd == "mutate":
        summary([run_agent(m, redteam="--redteam" in flags) for m in (args or ["btn-rename-0"])])
    else:
        print(__doc__)

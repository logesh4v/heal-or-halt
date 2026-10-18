"""Make the demo video, end to end, from a REAL run: `make video` -> results/heal-or-halt-demo.mp4

Pipeline (the pattern used by argo / demo-recorder / pitch-video: record the browser, TTS, ffmpeg):
  1. A local "studio" page (127.0.0.1 only) shows SplitPay as the user sees it, the agent's live log,
     a big confidence badge and subtitles.
  2. Playwright records that page to webm while this script runs the agent LIVE, scene by scene,
     streaming every stdout line into the page as it arrives. Nothing is replayed or typed in.
  3. macOS `say` speaks the narration. The outcome lines are written AFTER each run from what the run
     actually printed, so the spoken numbers are the live ones.
  4. ffmpeg places each narration clip at the moment it was shown and muxes H.264 + AAC. Silent waiting
     inside a live run (tests, model calls) plays at 4x, with a "fast-forward" label on screen; narration never does.

Needs: `make serve` (Decider), AWS profile with Nova, Chrome, ffmpeg (brew install ffmpeg).
"""

from __future__ import annotations

import functools
import html
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
OUT = ROOT / "results" / "heal-or-halt-demo.mp4"
WORK = Path(os.environ.get("KIROCREW_SCRATCH", ROOT / ".video")) / "hoh-video"
VOICE = os.environ.get("HOH_VOICE", "Rishi")
RATE = os.environ.get("HOH_VOICE_RATE", "196")
W, H = 1280, 720
FF = float(os.environ.get("HOH_VIDEO_FF", "4"))  # speed-up for silent waiting inside live runs
SOUND = os.environ.get("HOH_VIDEO_SOUND", "0") == "1"  # default: no audio track; subtitles carry the story
DEV = ["-c", "user.name=SplitPay dev", "-c", "user.email=dev@example.com"]
DECISION = re.compile(r"can_heal ([0-9.]+) -> (HEAL|HALT|ASK)")


# --------------------------------------------------------------------------- studio page

STUDIO = """<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0}
body{width:1280px;height:720px;background:#0b1020;color:#e8ecf5;font:16px -apple-system,Helvetica,Arial,sans-serif;overflow:hidden}
#top{height:56px;display:flex;align-items:center;gap:14px;padding:0 24px;background:#111833;border-bottom:1px solid #26305a}
#top b{font-size:20px;letter-spacing:.3px} #top span{color:#9fb0dd;font-size:17px}
#main{position:absolute;top:56px;bottom:92px;left:0;right:0;display:flex;gap:16px;padding:16px 24px}
#left{width:470px;display:flex;flex-direction:column;gap:8px}
#left small,#right small{color:#9fb0dd;font-size:13px;text-transform:uppercase;letter-spacing:1px}
iframe{flex:1;border:0;border-radius:10px;background:#fff}
#right{flex:1;display:flex;flex-direction:column;gap:8px;position:relative}
#log{flex:1;background:#05070f;border:1px solid #26305a;border-radius:10px;padding:14px 16px;font:14px/1.55 Menlo,monospace;white-space:pre-wrap;overflow:hidden;color:#c9d3ee}
.dec{color:#ffd166;font-weight:700}.ok{color:#5be49b}.bad{color:#ff6b6b}.veto{color:#c792ea}.out{color:#6cd4ff}.cmd{color:#9fb0dd}.hdr{color:#fff;font-weight:700}
#badge{position:absolute;bottom:14px;right:14px;padding:12px 18px;border-radius:12px;font:700 28px Menlo,monospace;display:none;box-shadow:0 6px 24px #0008}
.HEAL{background:#0f5132;color:#d1ffe4;border:2px solid #5be49b}.HALT{background:#5c1a1a;color:#ffe1e1;border:2px solid #ff6b6b}.ASK{background:#5a4a0c;color:#fff4cc;border:2px solid #ffd166}
#cap{position:absolute;bottom:0;left:0;right:0;height:92px;padding:14px 60px;background:#111833;border-top:1px solid #26305a;font-size:21px;line-height:1.35;display:flex;align-items:center;justify-content:center;text-align:center}
#card{position:absolute;top:56px;bottom:92px;left:0;right:0;padding:34px 60px;display:none;background:#0b1020}
#card h1{font-size:46px;margin-bottom:14px}#card h2{font-size:30px;margin-bottom:18px;color:#ffd166}
#card p{font-size:22px;color:#c9d3ee;line-height:1.5;margin-bottom:10px}
table{border-collapse:collapse;font-size:20px;margin-top:8px}td,th{padding:9px 18px;border-bottom:1px solid #26305a;text-align:left}
th{color:#9fb0dd;font-weight:600}.hi td{color:#5be49b;font-weight:700}
.flow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:20px 0}
.box{padding:14px 16px;border-radius:10px;font-size:18px;font-weight:600;text-align:center;min-width:130px}
.c{background:#1c2a5e;border:1px solid #4f6bd8}.d{background:#4a3c08;border:1px solid #ffd166}.l{background:#0f3d25;border:1px solid #5be49b}.s{background:#4d1515;border:1px solid #ff6b6b}
.arrow{color:#9fb0dd;font-size:26px}
pre.rc{font:15px/1.5 Menlo,monospace;background:#05070f;border:1px solid #26305a;border-radius:10px;padding:16px;color:#c9d3ee;white-space:pre-wrap}
#ff{position:absolute;top:34px;right:14px;padding:6px 12px;border-radius:8px;background:#26305a;color:#cfd8ff;font:700 16px Menlo,monospace;display:none}
#foot{position:absolute;right:24px;top:18px;color:#6f7fae;font-size:12px}
</style></head><body>
<div id="top"><b>Heal or Halt</b><span id="title"></span><div id="foot"></div></div>
<div id="main"><div id="left"><small>SplitPay &mdash; what the user sees</small><iframe id="app"></iframe></div>
<div id="right"><small>Agent &mdash; live run</small><div id="log"></div><div id="badge"></div><div id="ff">▶▶ fast-forward</div></div></div>
<div id="card"></div><div id="cap"></div>
<script>
const $=id=>document.getElementById(id);
function cls(l){if(/^\\$ |^[-+] /.test(l))return'cmd';if(l.startsWith('==='))return'hdr';if(l.includes('[decider]'))return'dec';
 if(l.includes('[veto]'))return'veto';if(/PROCEED|GREEN/.test(l))return'ok';if(/DENY|RED|LOCKOUT/.test(l))return'bad';if(l.includes('[output]'))return'out';return''}
window.studio={
 card(t,h){$('title').textContent=t;$('cap').textContent='';$('card').innerHTML=h;$('card').style.display='block';$('main').style.display='none'},
 split(t){$('title').textContent=t;$('card').style.display='none';$('main').style.display='flex';$('log').innerHTML='';$('badge').style.display='none';$('cap').textContent=''},
 app(src){$('app').src=src+'?t='+Date.now()},
 log(l){const d=document.createElement('div');d.className=cls(l);d.textContent=l;$('log').appendChild(d);
  while($('log').scrollHeight>$('log').clientHeight&&$('log').children.length>1)$('log').removeChild($('log').firstChild)},
 badge(t,k){const b=$('badge');b.textContent=t;b.className=k;b.style.display='block'},
 cap(t){$('cap').textContent=t}, ff(on){$('ff').style.display=on?'block':'none'}, foot(t){$('foot').textContent=t}};
</script></body></html>"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/studio"):
            body = STUDIO.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


# --------------------------------------------------------------------------- narration


def tts(text: str, name: str) -> tuple[Path, float]:
    path = WORK / f"{name}.aiff"
    subprocess.run(["say", "-v", VOICE, "-r", RATE, "-o", str(path), text], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(path)], capture_output=True, text=True, check=True).stdout.strip())
    return path, dur


class Timeline:
    def __init__(self, page):
        self.page, self.t0, self.clips, self.n, self.busy = page, time.monotonic(), [], 0, 0.0
        self.fast: list[tuple[float, float]] = []  # silent stretches of a live run, played at 2x in the edit

    def now(self) -> float:
        return time.monotonic() - self.t0

    def speak(self, text: str, wait: bool = True) -> float:
        """Synthesize, show as subtitle, place on the timeline. Returns the clip's end time."""
        self.n += 1
        path, dur = tts(text, f"n{self.n:02d}")
        self.until(self.busy + 0.25)  # never talk over the previous clip
        self.page.evaluate("t => studio.cap(t)", text)
        start = self.now()
        self.clips.append((start, path))
        end = start + dur
        self.busy = end
        if wait:
            self.until(end + 0.5)
        return end

    def until(self, t: float) -> None:
        while self.now() < t:
            self.page.wait_for_timeout(100)

    def js(self, fn: str, *args) -> None:
        self.page.evaluate(f"a => studio.{fn}(...a)", list(args))


# --------------------------------------------------------------------------- live runs


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def run_live(tl: Timeline, cmd: list[str], app_for: callable, transcript: list[str]) -> dict:
    """Run the agent for real and stream each line into the studio as it is printed."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    tl.js("log", "$ " + " ".join(cmd[2:]).replace("hoh ", "python -m hoh "))
    proc = subprocess.Popen([PY, *cmd[1:]], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=open(WORK / "agent_stderr.log", "a"), text=True, bufsize=1)
    seen = {"p": None, "action": None, "rerun": None, "outcome": None, "owner": None, "veto": None, "fails": None}
    shown_app = False
    ff_on = False
    for raw in proc.stdout:
        if not ff_on and tl.now() >= tl.busy + 0.3:
            ff_on, ff_start = True, tl.now()
            tl.js("ff", True)
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("=== summary") or line.startswith("  case ") or \
                re.match(r"^\s{2}\S+\s{2,}\S+\s{2,}can_heal", line) or "wrong heals" in line:
            continue
        transcript.append(line)
        tl.js("log", line[:150])
        if "[suite]" in line:
            seen["fails"] = int(re.search(r"(\d+) failing", line).group(1))
            if not shown_app:
                tl.js("app", app_for())
                shown_app = True
        m = DECISION.search(line)
        if m and "[decider]" in line:
            seen["p"], seen["action"] = m.group(1), m.group(2)
            own = re.search(r"owner=(\w+)", line)
            seen["owner"] = own.group(1) if own else seen["owner"]
            tl.js("badge", f"can_heal {m.group(1)} → {m.group(2)}", m.group(2))
        if "[veto]" in line:
            seen["veto"] = "unsafe" if "UNSAFE" in line else "safe"
        if "[rerun]" in line:
            seen["rerun"] = "green" if "GREEN" in line else "red"
        if "[output]" in line:
            seen["outcome"] = "pr" if "/PR-" in line else "issue"
    proc.wait()
    if ff_on:
        tl.js("ff", False)
        tl.fast.append((ff_start, tl.now()))
    if proc.returncode:
        raise SystemExit(f"agent run failed ({proc.returncode}); see {WORK / 'agent_stderr.log'}")
    return seen


def spoken(p: str | None) -> str:
    return f"point {' '.join(p.split('.')[1])}" if p and p.startswith("0.") else str(p)


# --------------------------------------------------------------------------- scenes


def card_html(*parts: str) -> str:
    return "".join(parts)


ARCH = card_html(
    "<h2>How one failure is handled</h2><div class='flow'>",
    "<div class='box c'>Playwright<br>test fails</div><span class='arrow'>→</span>",
    "<div class='box c'>Collector<br><small>error · page diff · commit</small></div><span class='arrow'>→</span>",
    "<div class='box d'>Strands Decider 2B<br><small>local · can_heal + confidence</small></div><span class='arrow'>→</span>",
    "<div class='box l'>Strands agent<br><small>Amazon Nova on Bedrock</small></div><span class='arrow'>→</span>",
    "<div class='box c'>HealGate<br><small>code checks the fix</small></div></div>",
    "<p>≥ 0.73 &nbsp;heal &nbsp;·&nbsp; 0.55 – 0.73 &nbsp;Nova Pro may only veto &nbsp;·&nbsp; &lt; 0.55 &nbsp;halt</p>",
    "<p><b>No pull request without a green re-run.</b> &nbsp;Assertions are never healed.</p>",
    "<p style='color:#9fb0dd'>Bedrock writes · Decider decides · code verifies</p>")


def eval_rows() -> dict[str, list[str]]:
    rows = {}
    for line in (ROOT / "results" / "EVAL.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and "/" in cells[1]:
            rows[cells[0]] = cells
    return rows


def results_card() -> tuple[str, str]:
    r = eval_rows()
    names = [("decider_policy_shipped", "Heal or Halt (Decider + rules)"), ("decider_raw_0.50", "Decider alone"),
             ("rule_baseline", "Plain rename rule"), ("nova_micro", "Nova Micro")]
    body = "".join(f"<tr class='{'hi' if k == names[0][0] else ''}'><td>{label}</td><td>{r[k][1]}</td>"
                   f"<td>{r[k][2]}</td></tr>" for k, label in names)
    score = re.search(r"Correct outcome: \*\*(\d+/\d+)\*\*", (ROOT / "results" / "AGENT_SCORECARD.md").read_text())
    h = (f"<h2>Held-out test: 48 failures it never saw during tuning</h2><table><tr><th></th>"
         f"<th>Fixable healed</th><th>Wrong heals</th></tr>{body}</table>"
         f"<p style='margin-top:22px'>Full agent on every kind of breakage: <b>{score.group(1)}</b>, zero wrong heals.</p>")
    wh = {k: r[k][2].split("/")[0] for k, _ in names}
    healed = r[names[0][0]][1].split("/")
    say = (f"On forty eight unseen failures: {healed[0]} of {healed[1]} healed, {wh['decider_policy_shipped']} wrong "
           f"heals. Decider alone made {wh['decider_raw_0.50']}, a rename rule {wh['rule_baseline']}, Nova Micro "
           f"{wh['nova_micro']}. The full agent: {score.group(1).replace('/', ' out of ')} correct.")
    return h, say


def receipt_card(pr: Path) -> str:
    text = pr.read_text()
    start = text.index("## Receipt")
    end = text.find("Branch:", start)
    block = text[start:end if end > 0 else start + 900].replace("## Receipt (facts inserted by code, not by a model)",
                                                                "Receipt — facts inserted by code, not by a model")
    title = text.splitlines()[0].lstrip("# ")
    return f"<h2>{html.escape(title)}</h2><pre class='rc'>{html.escape(block.strip())}</pre>"


def main() -> None:
    from playwright.sync_api import sync_playwright

    for tool in ("ffmpeg", "ffprobe", "say"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found (ffmpeg: brew install ffmpeg)")
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    pre = subprocess.run([PY, "-m", "hoh", "check"], cwd=ROOT, capture_output=True, text=True)
    print(pre.stdout.strip())
    if pre.returncode:
        raise SystemExit("preflight failed: fix it before recording")
    subprocess.run([PY, "-m", "hoh", "playground"], cwd=ROOT, check=True, capture_output=True)
    pg = ROOT / "playground"
    sha = git(ROOT, "rev-parse", "--short", "HEAD")
    dirty = " +local changes" if git(ROOT, "status", "--porcelain", "--untracked-files=no") else ""

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    transcript: list[str] = []
    beats: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(WORK),
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        tl = Timeline(page)
        page.goto(f"{base}/studio")
        tl.js("foot", f"real run · {time.strftime('%d %b %Y')} · commit {sha}{dirty} · Decider local · Nova on Bedrock")

        # 1. hook
        tl.js("card", "", "<h1>Someone renamed one button.</h1><h2>Every UI test went red.</h2>"
                          "<p>Is the product broken, or only the test?</p>"
                          "<p>Heal or Halt decides, and knows when to say <b>no</b>.</p>")
        tl.speak("Someone renames one button, and every UI test goes red. Is the product broken, or only the test? "
                 "Heal or Halt decides, and knows when to say no.")
        # 2. architecture
        tl.js("card", "How it works", ARCH)
        tl.speak("Strands Decider, running on this laptop, answers one question: can this be healed? "
                 "With a confidence number. Amazon Nova on Bedrock writes the fix. Code checks everything: "
                 "no pull request without a green re-run.")

        # 3. live: rename by hand
        tl.js("split", "Live 1 · a developer renames the button")
        tl.js("app", "/playground/app/index.html")
        end = tl.speak("A real change: Split bill becomes Calculate shares. Commit, and the agent runs live.",
                       wait=False)
        tl.until(end - 1.5)
        html_file = pg / "app" / "index.html"
        html_file.write_text(html_file.read_text().replace(">Split bill<", ">Calculate shares<"))
        git(pg, *DEV, "commit", "-qam", "copy: rename the main button")
        for l in ['$ git commit -m "copy: rename the main button"', '-  <button>Split bill</button>',
                  '+  <button>Calculate shares</button>']:
            tl.js("log", l)
        tl.js("app", "/playground/app/index.html")
        tl.until(end + 0.4)
        s = run_live(tl, [PY, "-m", "hoh", "run", "playground"], lambda: "/playground/app/index.html", transcript)
        beats.append({"beat": "rename", **s})
        if s["action"] == "HEAL" and s["rerun"] == "green" and s["outcome"] == "pr":
            tl.speak(f"Decider says {spoken(s['p'])}: heal. Nova writes the new locator, the suite re-runs green, "
                     "and only then does a pull request open.")
        else:
            tl.speak(f"Decider says {spoken(s['p'])}, {(s['action'] or '').lower()}. The agent filed an {s['outcome']}.")

        # 4. receipt
        prs = sorted(pg.glob("PR-*.md"))
        if prs:
            tl.js("card", "The Heal Receipt", receipt_card(prs[-1]))
            tl.speak("Its receipt is written by code, not by the model.")

        # 5. live: maths bug by hand
        tl.js("split", "Live 2 · a 'refactor' breaks the maths")
        tl.js("app", "/playground/app/index.html")
        end = tl.speak("Merge it. Now a refactor quietly breaks the maths.", wait=False)
        tl.until(end - 1.0)
        branch = git(pg, "branch", "--list", "heal/*", "--format=%(refname:short)").splitlines()
        if branch:
            git(pg, *DEV, "merge", "-q", branch[0])
        html_file.write_text(html_file.read_text().replace("(total / people)", "(total * people)"))
        git(pg, *DEV, "commit", "-qam", "refactor: tidy share calculation")
        for l in [f"$ git merge {branch[0] if branch else ''}", '$ git commit -m "refactor: tidy share calculation"',
                  "-  Math.round((total / people) * 100) / 100", "+  Math.round((total * people) * 100) / 100"]:
            tl.js("log", l)
        tl.js("app", "/playground/app/index.html")
        tl.until(end + 0.4)
        s = run_live(tl, [PY, "-m", "hoh", "run", "playground"], lambda: "/playground/app/index.html", transcript)
        beats.append({"beat": "maths", **s})
        if s["action"] == "HALT" and s["outcome"] == "issue":
            tl.speak(f"The value on screen is wrong, and an assertion is never healed. Halt: an issue for the "
                     f"{s['owner']}, no test touched.")
        else:
            tl.speak(f"Decider says {spoken(s['p'])}, {(s['action'] or '').lower()}. The agent filed an {s['outcome']}.")

        # 6. live: combo
        tl.js("split", "Live 3 · a rename that hides a real bug")
        tl.speak("The hardest case: one commit renames the button and breaks the maths.", wait=False)
        s = run_live(tl, [PY, "-m", "hoh", "mutate", "combo-rename-math"],
                     lambda: "/demo-run/combo-rename-math/app/index.html", transcript)
        beats.append({"beat": "combo", **s})
        if s["action"] == "HEAL" and s["rerun"] == "red" and s["outcome"] == "issue":
            tl.speak(f"Decider says {spoken(s['p'])}, heal, and it is right about the button. But the re-run is "
                     "still red, so the gate refuses the pull request. The rename was hiding a real bug.")
        else:
            tl.speak(f"Decider says {spoken(s['p'])}, {(s['action'] or '').lower()}. The agent filed an {s['outcome']}.")

        # 7. live: grey zone
        tl.js("split", "Live 4 · the test itself is wrong")
        tl.speak("Now the test itself has a typo.", wait=False)
        s = run_live(tl, [PY, "-m", "hoh", "mutate", "test-typo-button"],
                     lambda: "/demo-run/test-typo-button/app/index.html", transcript)
        beats.append({"beat": "grey", **s})
        if s["veto"]:
            tl.speak(f"Decider is unsure, {spoken(s['p'])}. In the grey zone Nova Pro gets a vote, but only to "
                     f"say no. It says {s['veto']}. {'Halt.' if s['outcome'] == 'issue' else ''}")
        else:
            tl.speak(f"Decider says {spoken(s['p'])}, {(s['action'] or '').lower()}. The agent filed an {s['outcome']}.")

        # 8. results  9. pattern
        h, say = results_card()
        tl.js("card", "Results", h)
        tl.speak(say)
        tl.js("card", "The reusable pattern",
              "<h2>patterns/policy-can-heal/</h2><p>question.json &nbsp;— one yes/no Decider question</p>"
              "<p>handler.py &nbsp;— plain rules + the Strands gate</p>"
              "<p>thresholds.md &nbsp;— 0.73, picked from data (conformal risk control)</p>"
              "<h1 style='margin-top:30px'>Heal when it's safe. Halt when it's not.</h1>"
              "<p style='color:#9fb0dd'>#strands-decider-2b &nbsp; #policy</p>")
        tl.speak("One question, plain rules, a threshold picked from data. Put it in front of any agent that "
                 "changes code. Heal when it is safe. Halt when it is not.")
        tl.until(tl.now() + 1.0)
        video_len = tl.now()
        clips = tl.clips
        ctx.close()
        webm = Path(page.video.path())
        browser.close()
    server.shutdown()

    # edit: silent stretches of live runs play at FF x (labelled on screen); narration is never sped up
    fast = [(a, b) for a, b in tl.fast if b - a > 1.0]
    segs, t = [], 0.0
    for a, b in fast:
        segs += [(t, a, 1.0), (a, b, FF)]
        t = b
    segs.append((t, video_len, 1.0))
    segs = [x for x in segs if x[1] - x[0] > 0.05]

    def remap(x: float) -> float:
        out = 0.0
        for a, b, sp in segs:
            if x <= a:
                break
            out += (min(x, b) - a) / sp
        return out

    vparts = [f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{sp}[v{i}]" for i, (a, b, sp) in enumerate(segs)]
    vgraph = ";".join(vparts) + ";" + "".join(f"[v{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=1:a=0[vout]"
    inputs = ["-i", str(webm)]
    chains, labels = [], []
    for i, (st, path) in enumerate(clips, 1):
        inputs += ["-i", str(path)]
        ms = int(remap(st) * 1000)
        chains.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    graph = vgraph + ";" + ";".join(chains) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0[aout]"
    final_len = remap(video_len)
    if SOUND:
        audio = ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
    else:  # silent video: the narration stays on screen as subtitles, timed by the same clips
        graph, inputs, audio = vgraph, ["-i", str(webm)], ["-an"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[vout]",
                    *audio, "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-preset", "medium", "-t", f"{final_len:.2f}",
                    "-movflags", "+faststart", str(OUT)], check=True)
    (ROOT / "results" / "video_run.json").write_text(json.dumps(
        {"commit": sha + dirty, "date": time.strftime("%Y-%m-%d %H:%M"), "voice": VOICE, "beats": beats,
         "transcript": transcript, "recorded_seconds": round(video_len, 1),
         "final_seconds": round(final_len, 1), "fast_forward": FF, "fast_spans": [[round(a, 1), round(b, 1)] for a, b in fast],
         "narration_starts": [round(c[0], 1) for c in clips]}, indent=1))
    print(f"wrote {OUT} ({final_len:.0f} s; recorded {video_len:.0f} s live, silent run stretches at {FF:g}x)")
    for b in beats:
        print(f"  {b['beat']:7} can_heal {b['p']} -> {b['action']}  rerun={b['rerun']}  veto={b['veto']}  "
              f"outcome={b['outcome']}")


if __name__ == "__main__":
    main()

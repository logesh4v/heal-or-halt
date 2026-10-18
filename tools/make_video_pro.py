"""Silent, captioned demo video from LIVE runs on real upstream TodoMVC -> results/heal-or-halt-demo-v2.mp4

    make serve                      # Decider on 127.0.0.1:8099
    .venv/bin/python tools/make_video_pro.py

What is real and what is not:
  * Every agent scene is a live `python -m hoh run` on a fresh TodoMVC case, streamed line by line into the
    page while Playwright records it. Waiting inside a run plays at HOH_VIDEO_FF x (default 6) with a visible
    speed label; captions are never sped up.
  * Caption numbers (Decider confidence, outcome) are read from that run's own output. If a run does not
    reach the outcome established in results/REAL_REPO.md, the render stops instead of papering over it.
  * Results / cost cards quote results/*.md and results/*.json; nothing is computed for the video.

Pacing rule (checked at the end, render fails if broken): every caption is held for
max(3.5 s, 1 s + 0.4 s per word), 1.5 s of stillness before each scene change, total <= 2:55.
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
OUT = ROOT / "results" / "heal-or-halt-demo-v2.mp4"
WORK = Path(os.environ.get("KIROCREW_SCRATCH", ROOT / ".video")) / "hoh-video-pro"
CASES = ROOT / "examples-run" / "todomvc" / "cases"
W, H = 1920, 1080
FF = float(os.environ.get("HOH_VIDEO_FF", "6"))
AUTHOR = os.environ.get("HOH_VIDEO_AUTHOR", "S Logesh")
MAX_TOTAL = 175.0
DECISION = re.compile(r"can_heal ([0-9.]+) -> (HEAL|HALT|ASK)")


def hold(text: str) -> float:
    return max(3.5, 1.0 + 0.4 * len(text.split()))


# --------------------------------------------------------------------------- studio page

STUDIO = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;
      --heal:#3fb950;--halt:#f85149;--sans:-apple-system,"SF Pro Display","Helvetica Neue",Arial,sans-serif;
      --mono:"SF Mono",Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--text);font-family:var(--sans);
     -webkit-font-smoothing:antialiased}
.fade{transition:opacity .3s ease}
#stage{position:absolute;inset:0 0 150px 0}
#card{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 200px}
#card h1{font-size:104px;font-weight:600;letter-spacing:-2px;margin-bottom:28px}
#card h2{font-size:64px;font-weight:600;letter-spacing:-1px;margin-bottom:28px}
#card p{font-size:36px;color:var(--muted);line-height:1.4;margin-bottom:14px}
#card .kicker{font-size:22px;color:var(--accent);text-transform:uppercase;letter-spacing:3px;margin-bottom:22px}
#card pre{font:28px/1.6 var(--mono);background:var(--panel);border:1px solid var(--line);border-radius:12px;
          padding:32px 40px;color:var(--text);white-space:pre-wrap}
.red{color:var(--halt)} .green{color:var(--heal)} .dim{color:var(--muted)}
.r{opacity:0;transition:opacity .4s ease} .r.on{opacity:1}
.flow{display:flex;gap:28px;align-items:stretch;margin-top:20px}
.step{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:34px 30px}
.step b{display:block;font-size:40px;font-weight:600;margin-bottom:12px}
.step span{font-size:26px;color:var(--muted);line-height:1.35}
table{border-collapse:collapse;width:100%;font-size:32px;margin-top:10px}
td,th{padding:20px 22px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:22px;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:2px}
td.num{font-family:var(--mono);font-size:30px}
#live{position:absolute;inset:0;padding:70px 120px 30px;display:none;flex-direction:column}
#live .kicker{font-size:22px;color:var(--accent);text-transform:uppercase;letter-spacing:3px}
#live h3{font-size:46px;font-weight:600;margin:14px 0 36px}
#cols{flex:1;display:flex;gap:40px;min-height:0}
.pane{display:flex;flex-direction:column;gap:14px;min-height:0}
.pane small{font-size:20px;color:var(--muted);text-transform:uppercase;letter-spacing:2px}
.box{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:26px 30px;
     font:22px/1.6 var(--mono);white-space:pre-wrap;overflow:hidden;position:relative}
#diff .del{color:var(--halt)} #diff .add{color:var(--heal)} #diff .file{color:var(--muted)}
#log .hdr{color:var(--text);font-weight:600} #log .dec{color:var(--accent)} #log .ok{color:var(--heal)}
#log .bad{color:var(--halt)} #log .row{color:#c9d1d9}
#chip{position:absolute;right:26px;bottom:24px;padding:14px 26px;border-radius:10px;font:600 36px var(--mono);
      display:none;background:var(--bg)}
#chip.HEAL{color:var(--heal);border:2px solid var(--heal)} #chip.HALT,#chip.DENY{color:var(--halt);border:2px solid var(--halt)}
#chip.ASK{color:#d29922;border:2px solid #d29922}
#cap{position:absolute;left:0;right:0;bottom:0;height:150px;background:var(--panel);border-top:1px solid var(--line);
     display:flex;align-items:center;justify-content:center;padding:0 220px;text-align:center;
     font-size:38px;font-weight:500;line-height:1.35}
#capt{opacity:0}
#tag{position:absolute;right:40px;top:40px;font:600 22px var(--mono);color:var(--muted);border:1px solid var(--line);
     border-radius:8px;padding:8px 14px;display:none}
#foot{position:absolute;left:120px;bottom:168px;font-size:18px;color:var(--muted);display:none}
</style></head><body>
<div id="stage" class="fade">
  <div id="card"></div>
  <div id="live"><div class="kicker" id="lk"></div><h3 id="lt"></h3>
    <div id="cols"><div class="pane" style="width:760px"><small>What the commit changed</small><div class="box" id="diff"></div></div>
    <div class="pane" style="flex:1"><small>Agent, live</small><div class="box" id="log"><div id="chip"></div></div></div></div>
  </div>
</div>
<div id="tag"></div><div id="foot"></div>
<div id="cap"><div id="capt" class="fade"></div></div>
<script>
const $=id=>document.getElementById(id);
function card(h){$('live').style.display='none';$('card').style.display='flex';$('card').innerHTML=h;$('stage').style.opacity=1}
function live(k,t,d,foot){$('card').style.display='none';$('live').style.display='flex';$('lk').textContent=k;$('lt').textContent=t;
  $('diff').innerHTML=d;$('log').innerHTML='<div id="chip"></div>';$('foot').textContent=foot;$('foot').style.display='block';$('stage').style.opacity=1}
function out(){$('stage').style.opacity=0;$('foot').style.display='none'}
function log(t,c){const d=document.createElement('div');d.className=c;d.textContent=t;$('log').insertBefore(d,$('chip'));
  while($('log').scrollHeight>$('log').clientHeight && $('log').children.length>2){$('log').removeChild($('log').children[0])}}
function chip(a,p){const c=$('chip');c.className=a;c.textContent=p?`${a} ${p}`:a;c.style.display='block'}
function cap(t){$('capt').textContent=t;$('capt').style.opacity=1} function uncap(){$('capt').style.opacity=0}
function tag(t){$('tag').textContent=t;$('tag').style.display=t?'block':'none'}
function reveal(){const n=document.querySelector('.r:not(.on)');if(n)n.classList.add('on')}
</script></body></html>"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Timeline:
    def __init__(self, page):
        self.page, self.t0 = page, time.monotonic()
        self.start = 0.0
        self.fast: list[tuple[float, float]] = []
        self.caps: list[tuple[str, float, float]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def js(self, fn: str, *args) -> None:
        self.page.evaluate(f"([a]) => {fn}(...a)", [list(args)])

    def wait(self, s: float) -> None:
        time.sleep(s)

    def say(self, text: str, during=None) -> None:
        """Show one caption for its full reading time. `during(t)` may reveal things while it is up."""
        self.js("cap", text)
        s = self.now()
        dur = hold(text)
        if during:
            during(dur)
        left = dur - (self.now() - s)
        if left > 0:
            time.sleep(left)
        self.caps.append((text, s, self.now()))
        self.js("uncap")
        time.sleep(0.45)

    def scene_change(self) -> None:
        time.sleep(1.5)
        self.js("out")
        time.sleep(0.4)


# --------------------------------------------------------------------------- live runs


def fmt(line: str):
    s = line.rstrip()
    if s.startswith("=== "):
        if "summary" in s:
            return None
        return s[4:].split("  commit:")[0].strip(), "hdr"
    m = re.match(r"\s+\[(\w+)\]\s+(.*)", s)
    if not m:
        return None
    tag, rest = m.groups()
    if tag == "output":
        rest = Path(rest.strip()).name
    cls = {"decider": "dec", "rerun": "ok" if "GREEN" in rest else "bad"}.get(tag, "row")
    if tag == "gate":
        cls = "bad" if "DENY" in rest else "ok"
    if tag == "output":
        cls = "ok" if rest.startswith("PR") else "bad"
    text = f"[{tag}] {rest}"
    return (text[:84] + "...") if len(text) > 87 else text, cls


def parse(lines: list[str]) -> dict:
    blob = "\n".join(lines)
    m = DECISION.search(blob)
    rr = re.search(r"\[rerun\]\s+(GREEN|RED)", blob)
    outs = re.findall(r"\[output\].*?/(PR|ISSUE)-\d+\.md", blob)
    return {"p": m.group(1) if m else None, "action": m.group(2) if m else None,
            "assertion": "assertion failed" in blob, "rerun": rr.group(1) if rr else None,
            "outcomes": outs, "deny_guess": "is not on any '+' line" in blob}


def run_case(case: str) -> list[str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.run([PY, "-m", "hoh", "run", str(CASES / case)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=600)
    return (proc.stdout + proc.stderr).splitlines()


def run_live(tl: Timeline, case: str) -> list[str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    tl.js("tag", f"Live run · {FF:g}× speed")
    start = tl.now()
    proc = subprocess.Popen([PY, "-m", "hoh", "run", str(CASES / case)], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    for line in proc.stdout:
        lines.append(line)
        f = fmt(line)
        if f:
            tl.js("log", *f)
        m = DECISION.search(line)
        if m and "[decider]" in line:
            tl.js("chip", m.group(2), m.group(1))
        if "DENY apply_locator_fix" in line:
            tl.js("chip", "DENY", "")
    proc.wait(timeout=600)
    time.sleep(0.6)
    tl.fast.append((start, tl.now()))
    tl.js("tag", "")
    time.sleep(0.6)
    return lines


def diff_html(case: str) -> str:
    raw = subprocess.run(["git", "diff", "-U0", "HEAD~1", "HEAD", "--", "app"], cwd=CASES / case,
                         capture_output=True, text=True, check=True).stdout
    out = []
    for ln in raw.splitlines():
        if ln.startswith("+++ b/"):
            out.append(f'<span class="file">{html.escape(ln[6:])}</span>')
        elif ln.startswith(("---", "+++", "diff", "index", "@@")):
            continue
        elif ln[:1] in "+-":
            body = ln[1:].strip()
            body = body if len(body) <= 52 else body[:49] + "..."
            cls = "add" if ln[0] == "+" else "del"
            out.append(f'<span class="{cls}">{ln[0]} {html.escape(body)}</span>')
    return "\n".join(out)


def must(cond: bool, what: str) -> None:
    if not cond:
        raise SystemExit(f"STOP: live run disagrees with the established result: {what}. Not rendering.")


# --------------------------------------------------------------------------- scenes


def main() -> None:
    from playwright.sync_api import sync_playwright

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    (WORK / "index.html").write_text(STUDIO)
    print("building fresh TodoMVC cases", flush=True)
    subprocess.run([PY, "examples/todomvc/build_cases.py"], cwd=ROOT, check=True, capture_output=True)
    print("off-camera: counter-bug (shown in the summary table)", flush=True)
    counter = parse(run_case("counter-bug"))
    must(counter["assertion"] and counter["outcomes"] == ["ISSUE"], f"counter-bug {counter}")

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(WORK)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(WORK),
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        tl = Timeline(page)
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html")
        foot = f"Recorded live · {time.strftime('%d %b %Y')} · MacBook Air M4 · Decider 2B local · Amazon Nova on Bedrock"
        results: dict[str, dict] = {"counter-bug": counter}

        # 1 title
        tl.js("card", "<div class='kicker'>Agent Experience Hackathon · Strands Decider</div><h1>Heal or Halt</h1>"
                      "<p>Self-healing UI tests that refuse to fake a fix.</p>")
        tl.start = tl.now()
        tl.wait(6.0)
        tl.scene_change()

        # 2 problem
        tl.js("card", "<div class='kicker'>The problem</div><pre><span class='dim'>tests/test_splitpay_e2e.py::test_even_split</span>"
                      "  <span class='red'>FAILED</span>\n\nTimeoutError: waiting for\n  get_by_role(\"button\", "
                      "name=<span class='red'>\"Split bill\"</span>)</pre>")
        tl.wait(0.8)
        tl.say("A renamed button turns a test suite red, even when the product works.")
        tl.say("Auto-healing tools fix that. The risk is healing over a real bug.")
        tl.scene_change()

        # 3 how it works
        tl.js("card", "<div class='kicker'>How it works</div><div class='flow'>"
                      "<div class='step r'><b>Collect</b><span>Code turns the failure into five short facts</span></div>"
                      "<div class='step r'><b>Decide</b><span>Strands Decider 2B, on the laptop, returns a confidence</span></div>"
                      "<div class='step r'><b>Write</b><span>Amazon Nova on Bedrock writes the fix or the issue</span></div>"
                      "<div class='step r'><b>Verify</b><span>The suite re-runs. Only green ships.</span></div></div>")
        tl.say("Code collects the evidence. Strands Decider 2B makes the call. Amazon Nova writes the fix. "
               "A re-run decides if it ships.",
               during=lambda d: [(tl.js("reveal"), time.sleep(d / 4.6)) for _ in range(4)])
        tl.scene_change()

        # 4 real repo intro
        tl.js("card", "<div class='kicker'>A real open-source app</div><h2>tastejs/todomvc</h2>"
                      "<p>Upstream, pinned at commit ff43b02 · MIT licence</p>"
                      "<p>Four ordinary developer commits. The right answer for each was written down before any run.</p>")
        tl.say("Same agent, same thresholds, nothing retuned, on upstream TodoMVC.")
        tl.scene_change()

        # 5-7 live cases
        kick = "Live · tastejs/todomvc"
        for case, title in [("rename-placeholder", "copy: friendlier input placeholder"),
                            ("combo", "copy + counter refactor"),
                            ("rename-clear", "copy: shorter clear button")]:
            tl.js("live", kick, f"Commit: {title}", diff_html(case), foot)
            tl.wait(3.0)
            r = parse(run_live(tl, case))
            results[case] = r
            if case == "rename-placeholder":
                must(r["action"] == "HEAL" and r["rerun"] == "GREEN" and r["outcomes"] == ["PR"], f"{case} {r}")
                tl.say(f"The input placeholder was reworded. Decider: heal, {r['p']}.")
                tl.say("Locator fixed, suite re-run, all green. Pull request opened.")
            elif case == "combo":
                must(r["action"] == "HEAL" and r["rerun"] == "RED" and r["outcomes"] == ["ISSUE"], f"{case} {r}")
                tl.say(f"Reworded and a counter bug in one commit. Decider: heal, {r['p']}.")
                tl.say("The re-run is still red. The fix is undone and an issue goes to the developer.")
            else:
                must(r["deny_guess"] and r["outcomes"] == ["ISSUE"], f"{case} {r}")
                tl.say("The button changed from \u201cClear completed\u201d to \u201cClear done\u201d. "
                       "The agent guessed \u201cClear\u201d.")
                tl.say("That guess would have passed. The gate refused it: the name was not in the evidence.")
            tl.scene_change()

        # 8 real-repo summary
        rows = [("Input placeholder reworded", "Heal", "<span class='green'>PR, re-run green</span>"),
                ("Off-by-one in \u201citems left\u201d", "Halt", "<span class='red'>Issue for the developer</span>"),
                ("Reworded + counter bug", "Halt", "<span class='red'>Fix undone, issue for the developer</span>"),
                ("\u201cClear completed\u201d \u2192 \u201cClear done\u201d", "Heal",
                 "<span class='dim'>Guess refused, issue for the test author</span>")]
        tl.js("card", "<div class='kicker'>tastejs/todomvc · today's runs</div><table><tr><th>Commit</th><th>Right answer</th>"
                      "<th>What the agent did</th></tr>" + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>"
                                                                   for a, b, c in rows) + "</table>")
        tl.say("Four real commits. Zero wrong heals. One safe miss went to a person.")
        tl.scene_change()

        # 9 results
        tl.js("card", "<div class='kicker'>Measured results</div><table><tr><th>Test</th><th>Heal or Halt</th><th>Compared with</th></tr>"
                      "<tr class='r'><td>Held-out eval · 48 real failures</td><td class='num green'>27/27 healed · 0/21 wrong</td>"
                      "<td class='num'>Nova Micro: 13/27 · 3/21 wrong</td></tr>"
                      "<tr class='r'><td>Full agent · 34 kinds of breakage</td><td class='num green'>34/34 correct</td>"
                      "<td class='num'>0 wrong heals</td></tr>"
                      "<tr class='r'><td>Real repo · tastejs/todomvc</td><td class='num green'>4 commits · 0 wrong</td>"
                      "<td class='num'>1 safe miss</td></tr></table>")
        for line in ["Held-out eval: 27 of 27 healed, zero wrong heals. Nova Micro made three.",
                     "Full agent, all 34 kinds of breakage: 34 of 34 correct.",
                     "Real repository: four commits, zero wrong heals."]:
            tl.js("reveal")
            tl.say(line)
        tl.scene_change()

        # 10 cost, honestly
        tl.js("card", "<div class='kicker'>Cost of the decision</div><table><tr><th>Who decides</th><th>API cost per million</th>"
                      "<th>Evidence leaves the laptop</th></tr>"
                      "<tr><td>Strands Decider 2B, local</td><td class='num green'>$0</td><td>No</td></tr>"
                      "<tr><td>Amazon Nova Micro</td><td class='num'>~$9 to $20</td><td>Yes</td></tr>"
                      "<tr><td>Amazon Nova Pro</td><td class='num'>~$132</td><td>Yes</td></tr></table>"
                      "<p style='margin-top:30px;font-size:26px'>us-east-1 list prices × measured tokens · "
                      "results/COST_LATENCY.md</p>")
        tl.say("Decision cost: $0 in API fees, versus about $9 to $132 per million on Bedrock. "
               "On a laptop, latency is a tie. The win is correctness.")
        tl.scene_change()

        # 11 pattern
        tl.js("card", "<div class='kicker'>The reusable pattern · #policy</div><pre>patterns/policy-can-heal/\n"
                      "  question.json    <span class='dim'>two typed Decider questions</span>\n"
                      "  handler.py       <span class='dim'>rules + Strands InterventionHandler gate</span>\n"
                      "  thresholds.md    <span class='dim'>0.73, chosen from data</span></pre>")
        tl.say("One question, plain rules, one gate. Drop it into any Strands agent.")
        tl.scene_change()

        # 12 end card
        tl.js("card", "<h1>Heal or Halt</h1><p style='color:var(--text)'>github.com/logesh4v/heal-or-halt</p>"
                      "<p>#strands-decider-2b &nbsp;&nbsp; #policy</p>"
                      f"<p style='margin-top:40px;font-size:30px'>Built by {html.escape(AUTHOR)}</p>")
        tl.wait(6.5)
        end = tl.now()
        raw = Path(page.video.path())
        ctx.close()
        browser.close()
    srv.shutdown()
    render(tl, raw, end, results)


# --------------------------------------------------------------------------- render + timing report


def render(tl: Timeline, raw: Path, end: float, results: dict) -> None:
    segs, t = [], tl.start
    for a, b in tl.fast:
        segs += [(t, a, 1.0), (a, b, FF)]
        t = b
    segs.append((t, end, 1.0))

    def remap(x: float) -> float:
        out = 0.0
        for a, b, k in segs:
            if x <= a:
                break
            out += (min(x, b) - a) / k
        return out

    parts = [f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{k}[v{i}]" for i, (a, b, k) in enumerate(segs)]
    graph = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=1:a=0,fps=30,format=yuv420p[out]"
    OUT.parent.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-filter_complex", graph, "-map", "[out]",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-tune", "stillimage", "-movflags", "+faststart",
                    "-an", str(OUT)], check=True)
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(OUT)], capture_output=True, text=True).stdout)
    rows, bad = [], []
    for text, s, e in tl.caps:
        vs, ve = remap(s), remap(e)
        words = len(text.split())
        ok = (ve - vs) + 0.05 >= hold(text)
        if not ok:
            bad.append(text)
        rows.append({"start": round(vs, 1), "end": round(ve, 1), "secs": round(ve - vs, 1), "words": words,
                     "words_per_sec": round(words / (ve - vs), 2), "ok": ok, "text": text})
    fast = [{"start": round(remap(a), 1), "end": round(remap(b), 1), "real_secs": round(b - a, 1)} for a, b in tl.fast]
    report = {"total_secs": round(total, 1), "limit_secs": MAX_TOTAL, "speed_up": FF, "captions": rows,
              "live_runs": fast, "results": results}
    (ROOT / "results" / "video_v2_timing.json").write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT}  ({total:.1f} s)")
    for r in rows:
        print(f"  {r['start']:6.1f}-{r['end']:6.1f}  {r['secs']:4.1f}s  {r['words']:2d}w  {'OK ' if r['ok'] else 'BAD'} {r['text']}")
    for f in fast:
        print(f"  live run {f['start']:.1f}-{f['end']:.1f} (real {f['real_secs']} s at {FF:g}x)")
    if bad or total > MAX_TOTAL:
        raise SystemExit(f"PACING CHECK FAILED: total {total:.1f}s (limit {MAX_TOTAL}), short captions: {bad}")
    print("PACING CHECK PASSED")


if __name__ == "__main__":
    main()

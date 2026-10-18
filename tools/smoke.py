"""Live smoke test: real Decider server + real Bedrock Nova + the policy gate, end to end.

Usage (Decider server must already be running on 127.0.0.1:8099 -- `make serve`):
    .venv/bin/python tools/smoke.py

Uses the AWS profile from AWS_PROFILE (default: "default") and never reads key files.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patterns" / "policy-can-heal"))
from handler import DEFAULT_URL, ask_decider, decide  # noqa: E402

NOVA = os.environ.get("HOH_NOVA_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")

RENAME = {
    "step": "click the Split bill button",
    "locator": "get_by_role('button', name='Split bill')",
    "error": "TimeoutError: waiting for get_by_role('button', name='Split bill')",
    "a11y_diff": "- button 'Split bill'\n+ button 'Calculate shares'",
    "commit": "copy: friendlier wording on the main action",
}
REAL_BUG = {
    "step": "check the result for 900 split 3 ways",
    "locator": "get_by_role('status')",
    "error": "AssertionError: expected 'Each person pays ₹300.00', got 'Each person pays ₹2700.00'",
    "a11y_diff": "(no change)",
    "commit": "refactor: move share calculation into a helper",
}


def health() -> dict:
    with urllib.request.urlopen(f"{DEFAULT_URL}/health", timeout=10) as r:  # noqa: S310
        return json.loads(r.read())


def nova_propose(state: dict) -> tuple[dict, float]:
    import boto3

    client = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client(
        "bedrock-runtime", region_name=REGION)
    tool = {"toolSpec": {"name": "propose_locator", "description": "Propose a new Playwright get_by_role locator",
                         "inputSchema": {"json": {"type": "object", "required": ["role", "name"],
                                                  "properties": {"role": {"type": "string"}, "name": {"type": "string"}}}}}}
    prompt = (
        "A Playwright test failed because a UI element changed.\n"
        f"{json.dumps(state, ensure_ascii=False, indent=1)}\n\n"
        "In a11y_diff, lines starting with '-' are the OLD page and '+' are the NEW page. "
        "The old locator no longer matches. Propose a locator for the element as it exists "
        "on the NEW page, using the role and name from the '+' line. Never reuse the old name."
    )
    t = time.perf_counter()
    out = client.converse(modelId=NOVA, messages=[{"role": "user", "content": [{"text": prompt}]}],
                          toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": "propose_locator"}}},
                          inferenceConfig={"maxTokens": 200})
    ms = (time.perf_counter() - t) * 1000
    for block in out["output"]["message"]["content"]:
        if "toolUse" in block:
            return block["toolUse"]["input"], ms
    raise RuntimeError("Nova returned no tool call")


def main() -> int:
    ok = True
    h = health()
    print(f"[decider] {h.get('checkpoint')} on {h.get('device')}, window {h.get('max_length')}")

    for label, state, want in (("rename", RENAME, "heal"), ("real bug", REAL_BUG, "halt")):
        t = time.perf_counter()
        answers = ask_decider(state)
        ms = (time.perf_counter() - t) * 1000
        v = decide(answers)  # first pass: before any fix exists
        print(f"[{label}] {v.line()}  halt_reason={v.halt_reason}  ({ms:.0f} ms)")
        if label == "rename" and v.action != "halt":
            fix, nms = nova_propose(state)
            final = decide(answers, old_name="Split bill", new_name=fix.get("name", ""), rerun_green=True)
            print(f"[{label}] Nova proposed {fix} in {nms:.0f} ms -> {final.line()}")
            v = final
        result = "PASS" if v.action == want else "FAIL"
        ok &= result == "PASS"
        print(f"[{label}] expected {want.upper()}: {result}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

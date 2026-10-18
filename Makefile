# Heal or Halt -- run `make help`. Every server binds 127.0.0.1 only. One command at a time.
PY      := .venv/bin/python
MODEL   := models/v1-2610
PORT    := 8099
export HF_HUB_OFFLINE := 1

DECIDER_REPO := https://github.com/strands-labs/strands-decider.git
DECIDER_SHA  := 0ac22a97e584f3ccf87cc9b8cc5fdbad57cdf534
MODEL_REPO   := StrandsAgents/strands-decider-2B-qwen3.5-v1-2610
MODEL_SHA    := 216d1ccb46a9e9b036eb9187b248db98480f77d4

.PHONY: help setup test serve stop smoke baseline monkey eval agent redteam scorecard demo check playground run video todomvc

help:
	@echo "make setup      - fresh clone: venv, pinned Decider, pinned model (~4 GB download, needs uv)"
	@echo "make test       - 20 unit + gate + Playwright tests (no model, no AWS)"
	@echo "make serve      - start Decider on 127.0.0.1:$(PORT) (MLX, ~5 GB)"
	@echo "make stop       - stop Decider"
	@echo "make smoke      - live check: Decider + Nova + rules on 2 cases"
	@echo "make baseline   - capture the clean app's aria snapshot"
	@echo "make monkey     - break SplitPay 34 ways -> eval/cases.jsonl (~4 min, Chrome)"
	@echo "make eval       - Decider vs rule vs Nova Micro, conformal threshold -> results/EVAL.md"
	@echo "make agent M=btn-rename-0  - run the full agent on one mutation"
	@echo "make redteam    - an 'eager' agent tries to force heals; the gate must stop it"
	@echo "make scorecard  - full agent on all 34 mutations -> results/AGENT_SCORECARD.md (~15 min)"
	@echo "make todomvc    - the agent on 4 real commits to upstream TodoMVC (tastejs/todomvc)"
	@echo "make demo       - the video run: rename, combo, real bug, server down, test typo"
	@echo "make check      - preflight before recording: Decider, Bedrock, Chrome"
	@echo "make playground - a green SplitPay git repo in playground/ to break by hand"
	@echo "make video      - record the narrated demo video from a LIVE run -> results/heal-or-halt-demo.mp4"
	@echo "make run        - the agent on a real repo (REPO=playground): heal or halt what HEAD broke"

setup:
	uv venv --python 3.12 .venv
	test -d vendor/strands-decider || git clone $(DECIDER_REPO) vendor/strands-decider
	git -C vendor/strands-decider checkout $(DECIDER_SHA)
	uv pip install --python $(PY) -r requirements-lock-decider.txt
	uv pip install --python $(PY) --no-deps -e vendor/strands-decider
	uv pip install --python $(PY) -r requirements.txt
	HF_HUB_OFFLINE=0 .venv/bin/hf download $(MODEL_REPO) --revision $(MODEL_SHA) --local-dir $(MODEL)
	HF_HUB_OFFLINE=0 .venv/bin/hf download Qwen/Qwen3.5-2B-Base --revision b1485b2fa6dfa1287294f269f5fb618e03d52d7c

test:
	$(PY) -m pytest

serve:
	nohup .venv/bin/strands-decider serve $(MODEL) --device mlx --host 127.0.0.1 --port $(PORT) --strict-window > results/serve_mlx.log 2>&1 &
	@echo "starting; logs in results/serve_mlx.log"

stop:
	-pkill -f "strands-decider serve $(MODEL)"

smoke:
	$(PY) tools/smoke.py

baseline:
	$(PY) -m hoh.baseline

monkey:
	$(PY) -m hoh.monkey

eval:
	$(PY) -m hoh.eval

agent:
	$(PY) -m hoh mutate $(or $(M),btn-rename-0)

redteam:
	$(PY) -m hoh mutate --redteam math-multiply btn-removed combo-rename-math

todomvc:
	$(PY) examples/todomvc/build_cases.py
	for c in rename-placeholder counter-bug combo rename-clear; do $(PY) -m hoh run examples-run/todomvc/cases/$$c; done

scorecard:
	$(PY) -m hoh.scorecard

demo:
	$(PY) -m hoh demo

check:
	$(PY) -m hoh check

playground:
	$(PY) -m hoh playground

run:
	$(PY) -m hoh run $(or $(REPO),playground)

video:
	$(PY) tools/make_video.py

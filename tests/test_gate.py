"""HealGate unit tests: the gate enforces Decider's verdict without any model or browser."""

from types import SimpleNamespace

import pytest

from handler import Verdict
from hoh.agent import GateLockout, Group, Run, make_gate
from hoh.monkey import MUTATIONS


def gate_for(action: str, rerun_green=None, locator='get_by_role("button", name="Split bill")',
             a11y_diff='- button "Split bill"\n+ button "Calculate shares"'):
    run = Run(MUTATIONS[0].id, ws=None)
    g = Group(locator, [{"state": {"a11y_diff": a11y_diff}}], verdict=Verdict(action, 0.9, "developer", "test"),
              rerun_green=rerun_green)
    run.groups, run.current = [g], g
    return make_gate(run), g


def test_new_name_must_be_on_a_plus_line_of_the_evidence():
    """Found on real TodoMVC: the button was hidden on first load, the diff was empty, and the agent
    guessed 'Clear', which passed only because Playwright matches names by substring."""
    gate, _ = gate_for("heal", locator='get_by_role("button", name="Clear completed")', a11y_diff="(no change)")
    assert call(gate, "apply_locator_fix", old_name="Clear completed", new_name="Clear").type == "deny"
    gate, _ = gate_for("heal")
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Calculate").type == "deny"


def call(gate, name, **args):
    return gate.before_tool_call(SimpleNamespace(tool_use={"name": name, "input": args}))


def test_halt_verdict_denies_code_changes():
    gate, _ = gate_for("halt")
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Go").type == "deny"


def test_heal_verdict_allows_a_real_rename():
    gate, _ = gate_for("heal")
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Calculate shares").type == "proceed"


def test_rename_that_keeps_the_old_name_is_denied():
    gate, _ = gate_for("heal")
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Split bill now").type == "deny"


def test_cannot_edit_a_different_locator():
    gate, _ = gate_for("heal")
    assert call(gate, "apply_locator_fix", old_name="Number of people", new_name="Party").type == "deny"


def test_open_pr_needs_a_green_rerun():
    gate, _ = gate_for("heal", rerun_green=False)
    assert call(gate, "open_pr", title="t", summary="s").type == "deny"
    gate, _ = gate_for("heal", rerun_green=True)
    assert call(gate, "open_pr", title="t", summary="s").type == "proceed"


def test_file_issue_is_always_allowed():
    gate, _ = gate_for("halt")
    assert call(gate, "file_issue", title="t", body="b").type == "proceed"


def test_lockout_after_three_denials():
    gate, _ = gate_for("halt")
    call(gate, "open_pr", title="t", summary="s")
    call(gate, "open_pr", title="t", summary="s")
    with pytest.raises(GateLockout):
        call(gate, "open_pr", title="t", summary="s")


def test_only_one_fix_attempt_per_failure():
    """Red team found this: after a red re-run an eager agent re-applied the same fix ~100 times."""
    gate, g = gate_for("heal")
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Calculate shares").type == "proceed"
    g.new_name = "Calculate shares"  # what the tool records once the edit is made
    assert call(gate, "apply_locator_fix", old_name="Split bill", new_name="Calculate shares").type == "deny"

"""Unit tests for the policy-can-heal bands. No model or browser needed."""

from handler import decide


def ans(p: float, owner: str = "developer") -> dict:
    return {"can_heal": {"noul": p}, "halt_reason": {"choice": owner, "confidence": 0.8}}


def test_high_confidence_heals():
    assert decide(ans(0.86), rerun_green=True).action == "heal"


def test_gray_zone_asks_a_human():
    assert decide(ans(0.62), rerun_green=True).action == "ask"


def test_low_confidence_halts_and_routes_owner():
    v = decide(ans(0.31, "platform"))
    assert (v.action, v.halt_reason) == ("halt", "platform")


def test_red_rerun_always_halts_even_at_high_confidence():
    assert decide(ans(0.95), rerun_green=False).action == "halt"


def test_fix_that_still_contains_old_name_is_rejected():
    v = decide(ans(0.95), old_name="Split", new_name="Calculate split", rerun_green=True)
    assert (v.action, v.halt_reason) == ("halt", "test_author")


def test_real_rename_is_allowed():
    v = decide(ans(0.95), old_name="Split bill", new_name="Calculate shares", rerun_green=True)
    assert v.action == "heal"


def test_console_line_shows_confidence():
    assert decide(ans(0.86), rerun_green=True).line().startswith("can_heal 0.86 -> HEAL")


def test_assertion_failure_never_heals_even_at_high_confidence():
    v = decide(ans(0.99), rerun_green=True, kind="assertion")
    assert (v.action, v.halt_reason) == ("halt", "developer")


def test_navigation_failure_routes_to_platform():
    v = decide(ans(0.99), kind="navigation")
    assert (v.action, v.halt_reason) == ("halt", "platform")


def test_failure_kind_classifies_real_playwright_errors():
    from handler import failure_kind
    assert failure_kind('TimeoutError: Locator.click: Timeout 2000ms exceeded.\n'
                        '  - waiting for get_by_role("button", name="Split bill")') == "locator"
    assert failure_kind("AssertionError: Locator expected to have text 'Each person pays ₹300.00'\n"
                        "Actual value: Each person pays ₹2700.00") == "assertion"
    assert failure_kind("Error: Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:9/") == "navigation"


def test_new_name_must_come_from_the_evidence():
    diff = '- button "Clear completed"\n+ button "Clear done"'
    assert decide(ans(0.95), old_name="Clear completed", new_name="Clear done", rerun_green=True,
                  a11y_diff=diff).action == "heal"
    v = decide(ans(0.95), old_name="Clear completed", new_name="Clear", rerun_green=True, a11y_diff=diff)
    assert v.action == "halt" and v.halt_reason == "test_author"

"""Hand-written labelled Playwright failure states for the Heal or Halt go/no-go probe.

Each case is a compact state an agent could build from a failed run: the failing step,
the locator, the error, a short accessibility-tree diff and the commit message.
Labels: label_drift, layout_move, real_regression, env_flake, test_bug.
"""

CASES = [
    # --- label_drift: the control still exists, only its accessible name changed
    dict(label="label_drift", step="click button 'Split bill'", locator="get_by_role('button', name='Split bill')",
         error="TimeoutError: locator.click: Timeout 5000ms exceeded waiting for get_by_role('button', name='Split bill')",
         a11y_diff="- button 'Split bill'\n+ button 'Calculate shares'", commit="copy: friendlier CTA wording on bill screen"),
    dict(label="label_drift", step="click link 'Sign in'", locator="get_by_role('link', name='Sign in')",
         error="TimeoutError: waiting for get_by_role('link', name='Sign in')",
         a11y_diff="- link 'Sign in'\n+ link 'Log in'", commit="i18n: align auth wording with brand guide"),
    dict(label="label_drift", step="fill textbox 'Email address'", locator="get_by_label('Email address')",
         error="TimeoutError: waiting for get_by_label('Email address')",
         a11y_diff="- textbox 'Email address'\n+ textbox 'Work email'", commit="signup: rename email field for B2B"),
    dict(label="label_drift", step="click button 'Submit'", locator="get_by_role('button', name='Submit')",
         error="TimeoutError: waiting for get_by_role('button', name='Submit')",
         a11y_diff="- button 'Submit'\n+ button 'Send payment'", commit="payments: clearer primary action label"),
    dict(label="label_drift", step="check checkbox 'I agree'", locator="get_by_role('checkbox', name='I agree')",
         error="TimeoutError: waiting for get_by_role('checkbox', name='I agree')",
         a11y_diff="- checkbox 'I agree'\n+ checkbox 'I accept the terms'", commit="legal: updated consent copy"),
    # --- layout_move: same control, same name, moved into another container
    dict(label="layout_move", step="click button 'Export CSV' in toolbar", locator="locator('#toolbar').get_by_role('button', name='Export CSV')",
         error="TimeoutError: waiting for locator('#toolbar').get_by_role('button', name='Export CSV')",
         a11y_diff="- toolbar > button 'Export CSV'\n+ menu 'More actions' > menuitem 'Export CSV'", commit="ui: move secondary actions into overflow menu"),
    dict(label="layout_move", step="click tab 'Settings' in sidebar", locator="locator('nav.sidebar').get_by_role('tab', name='Settings')",
         error="TimeoutError: waiting for locator('nav.sidebar').get_by_role('tab', name='Settings')",
         a11y_diff="- navigation 'sidebar' > tab 'Settings'\n+ banner > tab 'Settings'", commit="layout: settings moved to header tabs"),
    dict(label="layout_move", step="click button 'Delete' in row 1", locator="locator('tr').nth(1).get_by_role('button', name='Delete')",
         error="TimeoutError: waiting for locator('tr').nth(1).get_by_role('button', name='Delete')",
         a11y_diff="- row 1 > button 'Delete'\n+ row 1 > button 'Row actions' > menuitem 'Delete'", commit="table: collapse row buttons into actions menu"),
    dict(label="layout_move", step="click button 'Add member' in footer", locator="locator('footer').get_by_role('button', name='Add member')",
         error="TimeoutError: waiting for locator('footer').get_by_role('button', name='Add member')",
         a11y_diff="- contentinfo > button 'Add member'\n+ main > region 'Members' > button 'Add member'", commit="team page: move add button next to the list"),
    dict(label="layout_move", step="click button 'Apply' in filter panel", locator="locator('.filters').get_by_role('button', name='Apply')",
         error="TimeoutError: waiting for locator('.filters').get_by_role('button', name='Apply')",
         a11y_diff="- region 'filters' > button 'Apply'\n+ dialog 'Filters' > button 'Apply'", commit="search: filters now open in a dialog"),
    # --- real_regression: the page renders but the product behaves wrongly
    dict(label="real_regression", step="expect share text for 3 people splitting 900", locator="get_by_test_id('share')",
         error="AssertionError: expected 'Each pays 300.00' but got 'Each pays 0.00'",
         a11y_diff="(no change)", commit="refactor: extract split calculation into helper"),
    dict(label="real_regression", step="expect toast 'Payment sent'", locator="get_by_role('status')",
         error="AssertionError: expected 'Payment sent' but got 'Something went wrong (500)'",
         a11y_diff="(no change)", commit="api: switch payments client to new SDK"),
    dict(label="real_regression", step="expect cart total", locator="get_by_test_id('cart-total')",
         error="AssertionError: expected 'Rs 1,180' but got 'Rs 1,000'",
         a11y_diff="(no change)", commit="tax: move GST calculation server side"),
    dict(label="real_regression", step="click button 'Log in' then expect heading 'Dashboard'", locator="get_by_role('heading', name='Dashboard')",
         error="TimeoutError: waiting for get_by_role('heading', name='Dashboard'); page still shows heading 'Log in' with alert 'Invalid session'",
         a11y_diff="(no change)", commit="auth: rotate session cookie name"),
    dict(label="real_regression", step="expect 5 rows in invoice table", locator="get_by_role('row')",
         error="AssertionError: expected 5 rows, got 1 (header only)",
         a11y_diff="- table 'Invoices' rows 5\n+ table 'Invoices' rows 0", commit="db: new pagination query for invoices"),
    # --- env_flake: infrastructure, network or timing, not the product or the test
    dict(label="env_flake", step="goto /checkout", locator="page.goto('/checkout')",
         error="net::ERR_CONNECTION_REFUSED at http://127.0.0.1:3000/checkout",
         a11y_diff="(page not loaded)", commit="docs: fix typo in README"),
    dict(label="env_flake", step="goto /login", locator="page.goto('/login')",
         error="TimeoutError: page.goto: Timeout 30000ms exceeded; CI runner reported 'No space left on device'",
         a11y_diff="(page not loaded)", commit="chore: bump eslint"),
    dict(label="env_flake", step="click button 'Pay'", locator="get_by_role('button', name='Pay')",
         error="Error: browserType.launch: Target page, context or browser has been closed; passed on retry 1",
         a11y_diff="(no change)", commit="style: reformat css"),
    dict(label="env_flake", step="expect map tile loaded", locator="get_by_test_id('map')",
         error="Error: request to https://tiles.example-cdn.test failed: getaddrinfo ENOTFOUND; passed on retry",
         a11y_diff="(no change)", commit="ci: cache node_modules"),
    dict(label="env_flake", step="goto /reports", locator="page.goto('/reports')",
         error="Error: 502 Bad Gateway from staging load balancer; 3 other unrelated tests failed the same minute",
         a11y_diff="(page not loaded)", commit="copy: update footer year"),
    # --- test_bug: the test itself is wrong
    dict(label="test_bug", step="click button 'Save'", locator="get_by_role('buton', name='Save')",
         error="Error: Unknown role 'buton'",
         a11y_diff="(no change)", commit="test: add save flow spec"),
    dict(label="test_bug", step="expect heading 'Welcome back, Asha'", locator="get_by_role('heading')",
         error="AssertionError: expected 'Welcome back, Asha' but got 'Welcome back, Ravi'; test fixture logs in as user ravi",
         a11y_diff="(no change)", commit="test: new greeting spec"),
    dict(label="test_bug", step="click button 'Next'", locator="get_by_role('button', name='Next')",
         error="Error: strict mode violation: get_by_role('button', name='Next') resolved to 2 elements",
         a11y_diff="(no change)", commit="test: wizard happy path"),
    dict(label="test_bug", step="expect date '10/11/2026'", locator="get_by_test_id('due-date')",
         error="AssertionError: expected '10/11/2026' but got '11/10/2026'; spec hardcodes US date format, app locale en-IN unchanged",
         a11y_diff="(no change)", commit="test: due date spec"),
    dict(label="test_bug", step="fill textbox 'Amount' with 'abc' then expect success", locator="get_by_label('Amount')",
         error="AssertionError: expected toast 'Saved' but got validation error 'Enter a number'",
         a11y_diff="(no change)", commit="test: amount field spec"),
]

QUESTION = {
    "type": "choice",
    "instructions": "A browser end-to-end test just failed. What is the most likely cause of this failure?",
    "criteria": {
        "label_drift": "the same control still exists but its visible label or accessible name was reworded, so the test's name-based locator no longer matches",
        "layout_move": "the same control with the same name still exists but was moved into a different container, menu or dialog, so a scoped locator no longer finds it",
        "real_regression": "the app now behaves wrongly: a wrong value, an error, missing data or a broken flow that a user would notice",
        "env_flake": "the environment failed: server down, network, disk, browser crash, or the test passed on retry",
        "test_bug": "the test itself is wrong: a typo, a wrong fixture or expectation, an ambiguous locator, or invalid test input",
    },
}


def state_of(case: dict) -> dict:
    """The compact state handed to the decider (no label)."""
    return {k: case[k] for k in ("step", "locator", "error", "a11y_diff", "commit")}

"""End-to-end tests for TodoMVC (tastejs/todomvc, examples/javascript-es5/dist, MIT).

Behaviours come from TodoMVC's own app-spec.md and mirror Playwright's official
TodoMVC demo spec (tests-examples/demo-todo-app.spec.ts), ported to Python.
"""

from playwright.sync_api import Page, expect


def add(page: Page, *titles: str) -> None:
    box = page.get_by_placeholder("What needs to be done?")
    for i, t in enumerate(titles, 1):
        box.fill(t)
        box.press("Enter")
        expect(page.locator(".todo-list li")).to_have_count(i)  # wait for the app to render it


def test_add_todos(page: Page, app_url: str):
    page.goto(app_url)
    add(page, "buy some cheese", "feed the cat")
    expect(page.get_by_role("listitem").filter(has_text="feed the cat")).to_be_visible()
    expect(page.locator(".todo-count")).to_have_text("2 items left")


def test_counter_after_completing(page: Page, app_url: str):
    page.goto(app_url)
    add(page, "buy some cheese", "feed the cat", "book a doctors appointment")
    page.locator(".todo-list li .toggle").first.click()
    expect(page.locator(".todo-count")).to_have_text("2 items left")


def test_clear_completed(page: Page, app_url: str):
    page.goto(app_url)
    add(page, "buy some cheese", "feed the cat")
    page.locator(".todo-list li .toggle").first.click()
    page.get_by_role("button", name="Clear completed").click()
    expect(page.locator(".todo-list li")).to_have_count(1)


def test_active_filter(page: Page, app_url: str):
    page.goto(app_url)
    add(page, "buy some cheese", "feed the cat")
    page.locator(".todo-list li .toggle").first.click()
    page.get_by_role("link", name="Active").click()
    expect(page.locator(".todo-list li")).to_have_count(1)
    expect(page.locator(".todo-list li")).to_have_text("feed the cat")

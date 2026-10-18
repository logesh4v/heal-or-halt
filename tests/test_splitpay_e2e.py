"""End-to-end tests for SplitPay. These are the tests Heal or Halt watches and heals."""

from playwright.sync_api import Page, expect


def split(page: Page, app_url: str, total: str, people: str) -> None:
    page.goto(app_url)
    page.get_by_label("Bill total (₹)").fill(total)
    page.get_by_label("Number of people").fill(people)
    page.get_by_role("button", name="Split bill").click()


def test_even_split(page: Page, app_url: str):
    split(page, app_url, "900", "3")
    expect(page.get_by_role("status")).to_have_text("Each person pays ₹300.00")


def test_rounds_to_paise(page: Page, app_url: str):
    split(page, app_url, "100", "3")
    expect(page.get_by_role("status")).to_have_text("Each person pays ₹33.33")


def test_zero_people_shows_error(page: Page, app_url: str):
    split(page, app_url, "100", "0")
    expect(page.get_by_role("alert")).to_have_text("Enter at least 1 person.")

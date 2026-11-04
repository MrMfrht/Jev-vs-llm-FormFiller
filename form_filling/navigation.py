"""Open a named form link, including links in collapsed navigation menus."""

from playwright.sync_api import Page


def open_form_link(page: Page, label: str) -> None:
    links = page.get_by_role("link", name=label, exact=True, include_hidden=True)
    visible_link = links.filter(visible=True).first
    if not visible_link.is_visible():
        # Limit the search to navigation containing the requested link. Sites
        # sometimes toggle a separate mobile copy of that same navigation.
        menus = page.locator("nav, [role=navigation], .main-navigation").filter(has=links)
        toggles = menus.locator(
            "button.menu-toggle, button.navbar-toggler, button[aria-expanded=false], "
            "button[aria-label*=menu i]"
        ).filter(visible=True)
        if toggles.count() == 1:
            toggles.click(timeout=5000)
    visible_link.click(timeout=15000)

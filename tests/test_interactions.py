import os
import unittest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from finder.automation.menu import choose_from_menu
from browser.interactions import available_actions, execute_action
from browser.targets import capture_page


class InteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = cls.pw.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL") or None)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def test_dropdown_preserves_other_selections_and_detects_replacement(self):
        self.page.set_content("<select multiple><option selected>A</option><option>B</option>"
                              "<optgroup disabled><option>C</option></optgroup></select>")
        with capture_page(self.page) as capture:
            options = available_actions(capture.snapshot, ())
            self.assertNotIn("select_c1_2", options)
            execute_action(capture, options["select_c1_1"])
            self.assertEqual(self.page.locator("option:checked").all_text_contents(), ["A","B"])
        with capture_page(self.page) as capture:
            action = available_actions(capture.snapshot, ())["select_c1_1"]
            self.page.locator("option").nth(1).evaluate("el => el.replaceWith(el.cloneNode(true))")
            self.assertEqual(execute_action(capture, action).status, "stale")

    def test_fill_and_scroll_are_conditional(self):
        self.page.set_content("<input aria-label='Query'><input readonly><div style='height:3000px'></div>")
        with capture_page(self.page) as capture:
            choices = available_actions(capture.snapshot, ("needle",))
            self.assertNotIn("scroll_up", choices)
            self.assertNotIn("fill_c2_0", choices)
            execute_action(capture, choices["fill_c1_0"])
            self.assertEqual(self.page.locator("input").first.input_value(), "needle")
            execute_action(capture, choices["scroll_down"])
        with capture_page(self.page) as capture:
            self.assertIn("scroll_up", available_actions(capture.snapshot, ()))

    def test_oversized_menu_reaches_last_control(self):
        options = {f"c{i}": str(i) for i in range(600)}
        options.update(done="Done", blocked="Blocked")
        def ask(prompt, menu):
            self.assertLessEqual(len(menu), 255)
            return "c599" if "c599" in menu else next(k for k,v in menu.items() if "c599" in v)
        self.assertEqual(choose_from_menu("Choose 599", options, ask), "c599")

import json
import os
import unittest
from unittest.mock import patch

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from form_filling import FormInspector
from form_filling.matching.requests import read_facts
from form_filling.workflow import run_form_step
from form_filling.execution.apply import apply_matches
from form_filling.execution.targets import capture_targets


class DropdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL") or None)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def apply(self, html, values, before=None):
        self.page.set_content(html)
        docs = FormInspector().inspect(self.page)
        field = docs[0].fields[0]
        with capture_targets(self.page, docs) as targets:
            if before:
                before()
            matches = [{"status":"proposed", "field_id":field.id, "value":v} for v in values]
            return [item["status"] for item in apply_matches(matches, targets)]

    def test_checkbox_enables_a_dependent_text_input(self):
        self.page.set_content("""<label>Enable transfers<input name="enabled" type="checkbox"
            onchange="document.querySelector('#ref').disabled = !this.checked"></label>
            <input id="ref" name="reference" disabled>""")
        facts = read_facts({"enabled": True, "reference": "FX-12"})
        result = run_form_step(self.page, facts)
        self.assertEqual(result.decision_calls, 0)
        self.assertTrue(self.page.locator("[name=enabled]").is_checked())
        self.assertEqual(self.page.locator("#ref").input_value(), "FX-12")

    def test_dependent_select_is_filled_from_the_first_request(self):
        self.page.set_content("""<label>Country<select id="c" onchange="p.disabled=!this.value;
            p.innerHTML='<option></option><option>Nova Scotia</option>'"><option></option><option>Canada</option></select></label>
            <label>Province<select id="p" disabled><option></option></select></label>
            <label>Locked<input id="locked" readonly value="KEEP"></label>""")
        facts = read_facts({"home country": "Canada", "home province": "Nova Scotia", "locked code": "X1"})
        calls = []

        def jev(payload):
            calls.append(payload)
            answers = {}
            for key, question in payload["questions"].items():
                label = payload["state"]["fields"][key]
                fact = "q1" if "Country" in label else "q2" if "Province" in label else "q3"
                answers[key] = {"choice": fact, "confidence": 0.95}
            return {"answers": answers, "usage": {"input_tokens": 10, "output_tokens": 0, "cost": 0.0}}

        with patch("form_filling.workflow.request_decision", side_effect=jev):
            result = run_form_step(self.page, facts)
        self.assertEqual(len(calls), 1)
        self.assertIn("currently disabled", json.dumps(calls[0]["state"]["fields"]))
        self.assertEqual(self.page.locator("#p").input_value(), "Nova Scotia")
        self.assertEqual(self.page.locator("#locked").input_value(), "KEEP")
        self.assertEqual([(r["field"].split("|")[1].strip()[:8], r["status"]) for r in result.records],
                         [("Country", "matched"), ("Province", "matched"), ("Locked", "skipped")])
        self.assertEqual(result.model_calls, 1)

    def test_long_numbered_list_and_change_event(self):
        opts = "".join(f"<option value='y{i}'>{i}</option>" for i in range(1900, 2031))
        result = self.apply(f"<select onchange='document.title=this.value'>{opts}</select>", [2018])
        self.assertEqual(result, ["matched"])
        self.assertEqual(self.page.title(), "y2018")
        self.assertEqual(self.page.locator("select").input_value(), "y2018")

    def test_text_entry_with_extra_and_invalid_values(self):
        self.page.set_content("<input name=plate><input type=number min=1><button>Next</button>")
        docs = FormInspector().inspect(self.page)
        plate, number = docs[0].fields
        with capture_targets(self.page, docs) as targets:
            results = apply_matches([
                {"status": "proposed", "field_id": plate.id, "value": "DEMO482"},
                {"status": "proposed", "field_id": number.id, "value": 0},
                {"status": "unmatched", "field_id": None, "value": "Apple pie"},
            ], targets)
        self.assertEqual([r["status"] for r in results], ["matched", "needs_review", "unmatched"])
        self.assertEqual(self.page.locator("[name=plate]").input_value(), "DEMO482")

    def test_disabled_duplicate_and_stale(self):
        html = "<select><option>X</option><option disabled>A</option><option>B</option><option>B</option></select>"
        self.assertEqual(self.apply(html, ["A"]), ["unavailable"])
        self.assertEqual(self.apply(html, ["B"]), ["needs_review"])
        self.assertEqual(self.apply(html, ["X"], lambda:self.page.locator("select").evaluate("el=>el.replaceWith(el.cloneNode(true))")), ["needs_review"])

    def test_multi_keeps_existing_values(self):
        result = self.apply("<select multiple><option selected>A</option><option>B</option><option>C</option></select>",["B","C"])
        self.assertEqual(result, ["matched","matched"])
        self.assertEqual(self.page.locator("option:checked").all_text_contents(), ["A","B","C"])

    def test_searchable_portal(self):
        html = """<input role=combobox aria-controls=popup aria-expanded=false
            onclick="popup.hidden=false;this.setAttribute('aria-expanded','true')"
            oninput="document.querySelector('[role=option]').hidden=this.value!=='Tokyo'">
            <div id=popup role=listbox hidden><div role=option hidden onclick="
            this.setAttribute('aria-selected','true');popup.hidden=true">Tokyo</div></div>"""
        self.assertEqual(self.apply(html, ["Tokyo"]), ["matched"])
        self.assertEqual(self.page.locator('[role=option]').get_attribute('aria-selected'), 'true')

    def test_virtualized_menu_scrolls_without_scrolling_page(self):
        html = """<button role=combobox aria-controls=menu onclick="menu.hidden=false">Pick year</button>
          <div role=listbox id=menu hidden style="height:60px;overflow:auto" onscroll="
            const o=this.querySelector('[role=option]');o.textContent='2018';o.style.top='80px'">
          <div style="height:200px;position:relative"><div role=option onclick="this.setAttribute('aria-selected','true')"
          style="position:absolute;top:0">2017</div></div></div>"""
        self.assertEqual(self.apply(html,[2018]), ["matched"])
        self.assertGreater(self.page.locator("#menu").evaluate("el=>el.scrollTop"),0)
        self.assertEqual(self.page.evaluate("scrollY"),0)

    def test_custom_menu_without_options_is_unresolved(self):
        self.assertEqual(self.apply("<button role=combobox aria-expanded=false>Unknown</button>",["2018"]),["needs_review"])

    def test_datalist(self):
        self.assertEqual(self.apply("<input list=items><datalist id=items><option value='DE' label='Germany'></datalist>",["Germany"]),["matched"])
        self.assertEqual(self.page.locator("input").input_value(),"DE")

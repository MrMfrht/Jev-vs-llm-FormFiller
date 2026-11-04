import json
import os
import unittest
from dataclasses import asdict

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from form_filling import FormInspector


class FormInspectorTests(unittest.TestCase):
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

    def fields(self):
        return FormInspector().inspect(self.page)[0].fields

    def test_ready_inventory_does_not_need_window_load(self):
        pending = []
        self.page.route("https://slow.test/image", lambda route: pending.append(route))
        self.page.route("https://slow.test/form", lambda route: route.fulfill(
            content_type="text/html", body="""<img src="/image"><script>
            setTimeout(() => document.body.insertAdjacentHTML('beforeend',
                '<input aria-label="Delayed field">'), 250);</script>"""))
        self.page.goto("https://slow.test/form", wait_until="commit")
        docs = FormInspector().inspect_when_ready(self.page, timeout=4)
        self.assertEqual([f.label for f in docs[0].fields], ["Delayed field"])
        self.assertNotEqual(self.page.evaluate("document.readyState"), "complete")
        for route in pending:
            route.abort()

    def test_native_groups_form_ownership_and_inventory_only(self):
        self.page.set_content("""
          <form id=a><fieldset><legend>Trade-in</legend>
          <label>Year<select required><option>2020</option><optgroup disabled label="Older">
          <option>1990</option></optgroup></select></label>
          <label><input type=radio name=drive value=awd checked>All-wheel</label>
          <label><input type=radio name=drive value=front>Front</label></fieldset></form>
          <form id=b><input name=drive type=radio value=other></form>
          <input form=a name=outside readonly value=keep>
          <input type=hidden name=token value=HIDDEN_SECRET>
          <input type=password name=pass value=PASSWORD_SECRET>
          <fieldset disabled><input name=locked></fieldset><button>Send</button>""")
        fields = self.fields()
        self.assertEqual(len(fields), 7)
        select = fields[0]
        self.assertEqual((select.label, select.section, select.form), ("Year", "Trade-in", "a"))
        self.assertTrue(select.required)
        self.assertEqual(select.value, ("2020",))
        self.assertTrue(select.options[1].disabled)
        radio = fields[1]
        self.assertEqual([o.label for o in radio.options], ["All-wheel", "Front"])
        self.assertEqual(radio.value, "awd")
        self.assertEqual(fields[2].form, "b")
        self.assertFalse(fields[3].fillable_now)
        self.assertTrue(fields[4].hidden)
        self.assertFalse(fields[-1].fillable_now)
        self.assertNotIn("SECRET",json.dumps([asdict(f) for f in fields]))

    def test_custom_widgets_editor_and_lazy_options(self):
        self.page.set_content("""
        <span id=l>Notes</span><div contenteditable aria-labelledby=l><b>Heading</b></div>
        <input role=combobox aria-label=City aria-controls=choices>
        <ul id=choices role=listbox><li role=option aria-selected=true>Paris</li></ul>
        <button role=combobox aria-label=Region aria-expanded=false></button>
        <input list=tags><datalist id=tags><option value=car></datalist>
        <textarea aria-label=Markdown># hello</textarea>""")
        fields = self.fields()
        editor, city, _, region, suggestions, markdown = fields
        self.assertEqual((editor.label,editor.value),("Notes","Heading"))
        self.assertEqual(city.options[0].label,"Paris")
        self.assertTrue(city.options[0].selected)
        self.assertEqual(region.options_source,"not_exposed")
        self.assertEqual(suggestions.options_source,"suggestions")
        self.assertEqual(markdown.value,"# hello")

    def test_shadow_and_iframes(self):
        self.page.route("https://embedded.test/**",lambda r:r.fulfill(
            content_type="text/html",body="<input aria-label='Framed field'>"))
        self.page.route("https://host.test/**",lambda r:r.fulfill(
            content_type="text/html",body="<div id=host></div><iframe src='https://embedded.test/'></iframe>"))
        self.page.goto("https://host.test/")
        self.page.locator("#host").evaluate("el=>el.attachShadow({mode:'open'}).innerHTML='<input aria-label=Shadow>'")
        self.page.locator("iframe").evaluate("el=>el.hidden=true")
        docs = FormInspector().inspect(self.page)
        self.assertEqual(docs[0].fields[0].label,"Shadow")
        self.assertEqual(docs[1].fields[0].label,"Framed field")
        self.assertFalse(docs[1].fields[0].fillable_now)
        self.assertNotEqual(docs[0].fields[0].id,docs[1].fields[0].id)

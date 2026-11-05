import inspect
import os
import unittest
from dataclasses import asdict
from unittest.mock import patch

import settings
from finder.automation.retention import MEMORY_SELECTORS
from form_filling.matching.requests import DEFAULT_TOKEN_BUDGET
from form_filling.matching.resolve import DEFAULT_CONCURRENCY
from form_filling.workflow import run_form_step


def env(**values):
    return patch.dict(os.environ, values, clear=True)


class SettingsTests(unittest.TestCase):
    def test_form_defaults_and_relative_facts_path(self):
        with env(FORM_URL="https://example.test/form", FORM_FACTS="examples/facts.json"):
            config = settings.FormSettings.from_env()
        self.assertEqual(config.facts_path, settings.ROOT / "examples" / "facts.json")
        self.assertIsNone(config.open_link)
        self.assertEqual(config.matching, settings.MatchingSettings("jev", "openai/gpt-6-luna", DEFAULT_CONCURRENCY, None, DEFAULT_TOKEN_BUDGET))

    def test_form_overrides(self):
        with env(FORM_URL="u", FORM_FACTS="f.json", FORM_OPEN_LINK="Automobile", FORM_CONCURRENCY="8",
                 FORM_FACTS_PER_REQUEST="50", FORM_TOKEN_BUDGET="20000"):
            config = settings.FormSettings.from_env()
        self.assertEqual(config.open_link, "Automobile")
        self.assertEqual(config.matching, settings.MatchingSettings("jev", "openai/gpt-6-luna", 8, 50, 20000))
        with env(FORM_URL="u", FORM_FACTS="f.json", FORM_MULTI_SELECT_THRESHOLD="0.95",
                 FORM_SINGLE_VALUE_MIN_CONFIDENCE="0"):
            matching = settings.FormSettings.from_env().matching
        self.assertEqual((matching.multi_select_threshold, matching.single_value_min_confidence), (0.95, 0))
        with env(FORM_URL="u", FORM_FACTS="f.json", FORM_MATCHER="LLM", FORM_LLM_MODEL="openai/gpt-6-luna-mini"):
            matching = settings.FormSettings.from_env().matching
        self.assertEqual((matching.matcher, matching.llm_model), ("llm", "openai/gpt-6-luna-mini"))

    def test_matching_settings_are_run_form_step_arguments(self):
        parameters = inspect.signature(run_form_step).parameters
        for name, value in asdict(settings.MatchingSettings()).items():
            self.assertEqual(parameters[name].default, value)

    def test_missing_and_invalid_values_name_the_variable(self):
        cases = [
            ({"FORM_FACTS": "f.json"}, "FORM_URL"),
            ({"FORM_URL": "u"}, "FORM_FACTS"),
            ({"FORM_URL": "u", "FORM_FACTS": "f", "FORM_CONCURRENCY": "many"}, "FORM_CONCURRENCY"),
            ({"FORM_URL": "u", "FORM_FACTS": "f", "FORM_CONCURRENCY": "0"}, "FORM_CONCURRENCY"),
            ({"FORM_URL": "u", "FORM_FACTS": "f", "FORM_MATCHER": "gpt"}, "FORM_MATCHER"),
            ({"FORM_URL": "u", "FORM_FACTS": "f", "FORM_MULTI_SELECT_THRESHOLD": "1.5"}, "FORM_MULTI_SELECT_THRESHOLD"),
            ({"FORM_URL": "u", "FORM_FACTS": "f", "FORM_SINGLE_VALUE_MIN_CONFIDENCE": "high"},
             "FORM_SINGLE_VALUE_MIN_CONFIDENCE"),
        ]
        for values, name in cases:
            with self.subTest(name=name), env(**values), self.assertRaisesRegex(ValueError, name):
                settings.FormSettings.from_env()

    def test_finder_defaults_and_choices(self):
        with env(FINDER_URL="https://example.test", FINDER_GOAL="Find the price."):
            config = settings.FinderSettings.from_env()
        self.assertEqual((config.max_steps, config.memory, config.answer_mode), (10, "jev", "summary"))
        self.assertEqual(config.trace_dir, settings.ROOT / "artifacts")
        with env(FINDER_URL="u", FINDER_GOAL="g", FINDER_MEMORY="LUNA", FINDER_ANSWER_MODE="extract"):
            config = settings.FinderSettings.from_env()
        self.assertEqual((config.memory, config.answer_mode), ("luna", "extract"))
        with env(FINDER_URL="u", FINDER_GOAL="g", FINDER_MEMORY="gpt"), self.assertRaisesRegex(ValueError, "FINDER_MEMORY"):
            settings.FinderSettings.from_env()
        self.assertEqual(set(settings.MEMORY_MODELS), set(MEMORY_SELECTORS))

    def test_model_timeout(self):
        with env():
            self.assertEqual(settings.model_timeout(), 30)
        with env(MODEL_TIMEOUT_SECONDS="120"):
            self.assertEqual(settings.model_timeout(), 120)
        with env(MODEL_TIMEOUT_SECONDS="0"), self.assertRaisesRegex(ValueError, "MODEL_TIMEOUT_SECONDS"):
            settings.model_timeout()

    def test_video_and_slow_motion(self):
        with env():
            self.assertIsNone(settings.browser_video_dir())
            self.assertEqual(settings.browser_slow_mo(), 0)
        with env(BROWSER_VIDEO_DIR="artifacts/videos", BROWSER_SLOW_MO_MS="300"):
            self.assertEqual(settings.browser_video_dir(), settings.ROOT / "artifacts" / "videos")
            self.assertEqual(settings.browser_slow_mo(), 300)
        with env(BROWSER_SLOW_MO_MS="-1"), self.assertRaisesRegex(ValueError, "BROWSER_SLOW_MO_MS"):
            settings.browser_slow_mo()

    def test_browser_watch(self):
        for value, expected in (("", False), ("true", True), ("ON", True), ("0", False)):
            with self.subTest(value=value), env(BROWSER_WATCH=value):
                self.assertIs(settings.browser_watch(), expected)
        with env(BROWSER_WATCH="maybe"), self.assertRaisesRegex(ValueError, "BROWSER_WATCH"):
            settings.browser_watch()

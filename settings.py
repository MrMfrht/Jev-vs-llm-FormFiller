"""Runtime settings for every command. There are no command-line flags.

Values come from the process environment, then from the repository's .env file.
A variable that is already set in the environment wins over .env.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
MEMORY_MODELS = ("jev", "luna")
ANSWER_MODES = ("summary", "extract")

load_dotenv(ROOT / ".env")


def _text(name: str) -> str | None:
    return os.getenv(name, "").strip() or None


def _required(name: str) -> str:
    value = _text(name)
    if value is None:
        raise ValueError(f"Set {name} in .env (see .env.example).")
    return value


def _int(name: str, default: int | None) -> int | None:
    value = _text(name)
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, not {value!r}.") from None
    if number < 1:
        raise ValueError(f"{name} must be at least 1.")
    return number


def _fraction(name: str, default: float) -> float:
    value = _text(name)
    if value is None:
        return default
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number between 0 and 1, not {value!r}.") from None
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1.")
    return number


def _bool(name: str, default: bool = False) -> bool:
    value = _text(name)
    if value is None:
        return default
    if value.casefold() in {"1", "true", "yes", "on"}:
        return True
    if value.casefold() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, not {value!r}.")


def _choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    value = (_text(name) or default).casefold()
    if value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(choices)}, not {value!r}.")
    return value


def _path(name: str, default: str | None = None) -> Path:
    path = Path(_text(name) or default or _required(name))
    return path if path.is_absolute() else ROOT / path


def browser_watch() -> bool:
    """BROWSER_WATCH=true shows the browser window and waits for Enter at the end."""
    return _bool("BROWSER_WATCH")


def reader_url() -> str:
    return _required("READER_URL")


def finder_memory() -> str:
    """Which model picks the evidence carried to the next page: jev or luna."""
    return _choice("FINDER_MEMORY", "jev", MEMORY_MODELS)


@dataclass(frozen=True)
class MatchingSettings:
    """Keyword arguments for form_filling.workflow.run_form_step."""
    concurrency: int = 4
    facts_per_request: int | None = None
    token_budget: int = 100_000
    multi_select_threshold: float = 0.8
    single_value_min_confidence: float = 0.6

    @classmethod
    def from_env(cls) -> "MatchingSettings":
        return cls(
            concurrency=_int("FORM_CONCURRENCY", cls.concurrency),
            facts_per_request=_int("FORM_FACTS_PER_REQUEST", None),
            token_budget=_int("FORM_TOKEN_BUDGET", cls.token_budget),
            multi_select_threshold=_fraction("FORM_MULTI_SELECT_THRESHOLD", cls.multi_select_threshold),
            single_value_min_confidence=_fraction("FORM_SINGLE_VALUE_MIN_CONFIDENCE",
                                                  cls.single_value_min_confidence),
        )


@dataclass(frozen=True)
class FormSettings:
    url: str
    facts_path: Path
    open_link: str | None
    matching: MatchingSettings

    @classmethod
    def from_env(cls) -> "FormSettings":
        return cls(_required("FORM_URL"), _path("FORM_FACTS"), _text("FORM_OPEN_LINK"),
                   MatchingSettings.from_env())


@dataclass(frozen=True)
class FinderSettings:
    url: str
    goal: str
    max_steps: int
    memory: str
    answer_mode: str
    trace_dir: Path

    @classmethod
    def from_env(cls) -> "FinderSettings":
        return cls(
            url=_required("FINDER_URL"),
            goal=_required("FINDER_GOAL"),
            max_steps=_int("FINDER_MAX_STEPS", 10),
            memory=finder_memory(),
            answer_mode=_choice("FINDER_ANSWER_MODE", "summary", ANSWER_MODES),
            trace_dir=_path("FINDER_TRACE_DIR", "artifacts"),
        )

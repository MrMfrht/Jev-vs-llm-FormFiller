# Fine Print Detective: form filler

The form filler matches the facts in a JSON file to the fields of a web form, fills them in, and reads each value back to verify it. It is built on Playwright and Jev, a decision model on OpenRouter.

Jev only **chooses from given options**. It never writes text, so every value typed into the form comes verbatim from your facts file.

There are **no command-line flags**. The command always runs the full process, and every setting comes from `.env`. For a short summary of when Jev is a good fit, see [docs/jev-for-form-filling.md](docs/jev-for-form-filling.md).

## Contents

1. [Setup](#setup)
2. [Minimal `.env`](#minimal-env)
3. [Configuration](#configuration)
4. [Repository layout](#repository-layout)
5. [How it works](#how-it-works)
6. [Facts file](#facts-file)
7. [Matching](#matching)
8. [Writing and verifying](#writing-and-verifying)
9. [Results](#results)
10. [Limits](#limits)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
copy .env.example .env               # add your OpenRouter key and form settings
uv run playwright install chromium   # or set PLAYWRIGHT_CHANNEL=msedge
uv run python -m form_filling        # fill the form (billed)
```

The filler fills the current step of `FORM_URL` and never submits it. The banking benchmark, `uv run python -m examples.form_filling.banking.check` (also billed), fills a 310-field synthetic form and compares the result with `expected.json`.

## Minimal `.env`

You only need three or four lines. Every other setting has a default. After editing `.env`, run `uv run python -m form_filling`. Add `BROWSER_WATCH=true` to watch the browser fill the form.

### A public URL

This uses the Tricentis demo insurance app, Automobile step. `.env.example` already contains these values.

```dotenv
OPEN_ROUTER_API_KEY=sk-or-v1-...
FORM_URL=https://sampleapp.tricentis.com/101/app.php
FORM_OPEN_LINK=Automobile
FORM_FACTS=examples/form_filling/automobile-facts.json
```

In a live run, all 8 vehicle fields were matched and verified with 1 Jev call, for $0.0002. The facts file also has 4 facts that match no field, and these are ignored. The site's search box stays empty.

### A local HTML page

This uses the banking test form in this repository.

```dotenv
OPEN_ROUTER_API_KEY=sk-or-v1-...
FORM_URL=file:///C:/path/to/fine-print-detective/examples/form_filling/banking/form.html
FORM_FACTS=examples/form_filling/banking/facts.json
```

- `FORM_URL` must be an absolute `file:///` URL. On macOS or Linux it looks like `file:///home/me/…`. Spaces in the path work either as is or written as `%20`.
- `FORM_FACTS` can be relative to the repository root.
- This fills the form and prints the results. To also score the result against `expected.json`, run `uv run python -m examples.form_filling.banking.check`, which needs only the API key.

### Your own form

1. Point `FORM_URL` at the page.
2. Write a facts file (see [Facts file](#facts-file)) and point `FORM_FACTS` at it.
3. If the form is only reachable through a link, add `FORM_OPEN_LINK` with that link's exact text.

## Configuration

[`settings.py`](settings.py) reads these variables at startup. A variable set in your shell overrides `.env`. A missing or invalid value stops the command with a message naming the variable.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPEN_ROUTER_API_KEY` | required | OpenRouter key (`OPENROUTER_API_KEY` also works) |
| `FORM_URL` | required | Page with the form (`file:///…` works) |
| `FORM_FACTS` | required | Facts JSON file, relative to the repository root |
| `FORM_OPEN_LINK` | none | Exact name of a link to click before inspecting |
| `FORM_CONCURRENCY` | `4` | Jev requests sent at the same time |
| `FORM_FACTS_PER_REQUEST` | unset (254) | Caps the facts per request; never more than 254 |
| `FORM_TOKEN_BUDGET` | `100000` | Max estimated tokens per request |
| `FORM_MULTI_SELECT_THRESHOLD` | `0.8` | Multi-select: minimum yes-probability for a fact to be selected |
| `FORM_SINGLE_VALUE_MIN_CONFIDENCE` | `0.6` | Single-value: a pick below this becomes `needs_review` and isn't written (`0` disables) |
| `BROWSER_WATCH` | `false` | `true` shows the browser and waits for Enter at the end |
| `PLAYWRIGHT_CHANNEL` | Chromium | Installed browser to use instead, e.g. `msedge` |

Whole numbers must be at least 1, and thresholds must be between 0 and 1. Booleans accept `true/false`, `1/0`, `yes/no` and `on/off`.

## Repository layout

| Path | Contents |
| --- | --- |
| `settings.py` | All `.env` settings |
| `form_filling/` | `inspection/` (field inventory), `matching/` (Jev requests), `execution/` (write and verify), all driven by `workflow.py` |
| `browser/` | Browser launch (`session.py`), shared with the rest of the repository |
| `open_router/` | OpenRouter HTTP client (`client.py`) and Jev limits |
| `examples/form_filling/` | Fact files and the banking benchmark |
| `docs/` | [Pros and cons of Jev for form filling](docs/jev-for-form-filling.md) |
| `tests/` | unittest suite |

## How it works

**Process:** inspect the form → exact-name matches → build Jev requests → bind fields → ask Jev → resolve → write and verify → repeat for newly enabled fields.

**Output:** stdout gets a JSON row per field, or one row per selected fact for multi-selects. The last line on stderr is a summary like `Jev calls: N, T input tokens, $C. Statuses: {'matched': …}`, using the token counts and cost that OpenRouter reports.

From Python:

```python
from browser.session import browser_page
from form_filling.matching.requests import read_facts
from form_filling.workflow import run_form_step

with browser_page() as page:
    page.goto("https://example.test/form")
    result = run_form_step(page, read_facts({"email": "a@b.test"}), concurrency=4)
    print(result.decision_calls, result.cost, result.records)
```

To get only the field inventory (read-only), call `FormInspector().inspect(page)` from `form_filling`.

## Facts file

```json
{ "vehicle.make": "Toyota", "seats": 5, "newsletter": true, "delivery": ["Email notice", "Paperless inbox"] }
```

| Value | Result |
| --- | --- |
| String, number, boolean | One candidate fact |
| List | One candidate per item (used for multi-selects) |
| Empty string, object, empty file | Rejected |
| Fact matching no field | Ignored |
| One fact fitting several fields (email + confirm email) | Used for each field |

Facts are numbered `q1, q2, …` in file order. When a form covers several people, name each fact after its owner (`co-owner email`).

## Matching

### Which fields are matched

| Field | Handling |
| --- | --- |
| HTML `name` equals a fact key, both unique, single-value | Matched locally with no Jev call (`match_method: exact_name`) |
| Other visible, enabled, editable fields | Asked to Jev |
| Disabled, hidden, read-only | Skipped now; matched later if they become editable |
| Password, file | Never matched |

### How Jev is asked

| Field type | Question | Jev returns | Decision |
| --- | --- | --- | --- |
| Single-value | One `choice` per field; the options are the facts plus `no_match` | The winner and its `confidence` | Written if confidence ≥ `FORM_SINGLE_VALUE_MIN_CONFIDENCE`, otherwise `needs_review` |
| Multi-select | One `noul` per (field, fact); each fact's text appears once in `state` | A yes-probability per fact | Every fact ≥ `FORM_MULTI_SELECT_THRESHOLD` is selected |

A `choice` question's probabilities add up to 1, so the facts compete. That's right when only one can win. `noul` scores each fact independently, so several can pass. Jev answers all of a request's questions in one call.

`state` is billed once per request, but each question carries and pays for its own copy of its options. So a single-value field costs about **20–30 tokens per fact**.

### Number of facts (255-option limit)

Each question offers the facts plus `no_match`, so a request holds at most **254 facts**.

| Facts | Requests per field | Example groups |
| --- | --- | --- |
| ≤ 254 | 1 | 80 → `[80]`, 254 → `[254]` |
| > 254 | `ceil(facts / 254)` balanced groups | 255 → `[128, 127]`, 600 → `[200, 200, 200]` |
| Any, with `FORM_FACTS_PER_REQUEST=K` | `ceil(facts / min(K, 254))` | 600 with K=100 → 6 × `[100]` |

When facts are split into groups, each group can nominate a fact for the same single-value field:

| Nominations | Result |
| --- | --- |
| 0 | `unmatched` |
| 1 | Written if its confidence passes the minimum |
| 2 or more | A follow-up request compares only the nominees; the winner's confidence must pass the minimum |
| Comparison exceeds 254 nominees or the token budget | `needs_review` with `candidate_ids` |

Multi-select questions have no option list, so the 254 limit doesn't apply. All facts go in one request unless `FORM_FACTS_PER_REQUEST` is set.

### Request size (token budget)

Many fields share a request, and each field repeats the fact list, so a request grows with fields × facts. Jev has no public tokenizer or token-count endpoint, so the size is estimated: the JSON is counted with tiktoken `cl100k_base`, plus **12 tokens per `choice` option** for Jev's own formatting. That figure was fitted to billed usage, and estimates land within about ±3% of the billed count on real requests.

| Estimated size | Action |
| --- | --- |
| ≤ `FORM_TOKEN_BUDGET` (100k) | Sent as is |
| Over, more than 1 field | Fields split in half, repeated until each half fits |
| Over, 1 field, more than 1 fact | Facts split in half |
| Over, 1 field and 1 fact | Error: shorten the fact or raise the budget |

The banking benchmark (310 fields, 79 facts) comes to 48 exact-name matches, 8 requests of ~77k tokens for 258 fields, and 1 multi-select request.

### Concurrency

| Requests | Behaviour |
| --- | --- |
| ≤ `FORM_CONCURRENCY` | All sent at once |
| More | Sent in waves of `FORM_CONCURRENCY`; follow-up comparisons share the same limit |

Network timeouts are retried up to 3 times (90 s each), but a single HTTP error such as a 429 rate limit aborts the whole run. Raise the concurrency carefully.

## Writing and verifying

Fields are bound to their DOM elements **before** Jev is called. If a field re-renders in the meantime, its write is refused.

| Field kind | Write | Verified by |
| --- | --- | --- |
| text, textarea, number, date, email, tel, url, month, time, week, datetime-local | Fill, then blur | Exact readback, browser validity, not `aria-invalid` |
| Native checkbox | Check/uncheck; **needs a boolean fact** | Checked state |
| Native `<select>` | The unique enabled option whose label or value equals the fact; a multi-select keeps existing selections | Selected options read back |
| `<datalist>` input | The unique matching suggestion | Readback |
| ARIA combobox/listbox | Open, search, scan up to 30 scrolls / 5 s, click or Enter | Shown label or `aria-selected` within 1 s |
| Radio, switch, slider, contenteditable, search | Not written | `skipped` |

After a verified write, the page is re-inspected. Fields that just became editable are matched and filled, and this repeats until nothing new appears (e.g. country → branch list).

The filler handles one step at a time and never clicks Next or Submit. It can't see closed shadow roots, canvas, or custom dropdowns that expose no options.

## Results

| Status | Meaning |
| --- | --- |
| `matched` | Written and verified; `detail` shows the value and `confidence` shows Jev's score (absent for exact-name matches) |
| `unmatched` | No fact fits |
| `needs_review` | Low confidence, ambiguous, or unverified (duplicate options, re-rendered field, failed readback); see `detail` |
| `unavailable` | No enabled `<select>` option has that label or value |
| `skipped` | The field kind has no writer |

Live benchmark (banking, jev-1.14): **310/310 correct**, 6 Jev calls, about $0.03.

## Limits

| Value | Setting | Controls |
| --- | --- | --- |
| 255 options | constant | Choices per Jev question |
| 254 facts | `FORM_FACTS_PER_REQUEST` (cap) | Facts per request |
| 100,000 tokens | `FORM_TOKEN_BUDGET` | Request size |
| 4 | `FORM_CONCURRENCY` | Parallel requests |
| 0.8 / 0.6 | `FORM_MULTI_SELECT_THRESHOLD` / `FORM_SINGLE_VALUE_MIN_CONFIDENCE` | Multi-select cut-off / single-value confidence floor |
| 12 s | constant | Wait for a stable form inventory |
| 5 s / 30 scrolls | constant | Custom dropdown search |
| 90 s × 3 | constant | Jev request timeout × attempts |
| 45 s | constant | Page load |

## Testing

`uv run python -m unittest discover -s tests` makes no network calls; model responses are mocked. Most tests use a local Chromium.

| File | Covers |
| --- | --- |
| `test_form_inspector.py` | Field inventory, frames, shadow roots |
| `test_form_requests.py` | Fact groups, token splits, comparisons, concurrency, thresholds |
| `test_form_dropdowns.py` | Writing and verifying every field kind, dependent fields |
| `test_settings.py` | `.env` parsing and defaults |

## Troubleshooting

| Message | Fix |
| --- | --- |
| `Set FORM_URL in .env …` | Add the named variable (see `.env.example`) |
| `… must be a whole number …` | Use an integer ≥ 1 |
| `.env` value ignored | The variable is also set in your shell, which wins |
| `One fact and field exceed the request budget` | Shorten the fact or raise `FORM_TOKEN_BUDGET` |
| `OpenRouter … returned HTTP 429` | Lower `FORM_CONCURRENCY` |
| Many `needs_review` rows saying confidence is below the minimum | Lower `FORM_SINGLE_VALUE_MIN_CONFIDENCE`, or make fact names clearer |
| Multi-select misses a value | Lower `FORM_MULTI_SELECT_THRESHOLD` |
| Other `needs_review` rows | Read each row's `detail` |
| Browser won't launch | `uv run playwright install chromium` or set `PLAYWRIGHT_CHANNEL` |

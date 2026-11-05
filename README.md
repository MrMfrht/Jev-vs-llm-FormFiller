# Fine Print Detective: form filler

Give it a web form and a JSON file of facts about a person. It fills the form in and checks every value it typed.

Two "brains" can do the matching, and you pick one with a setting:

- **Jev**: a decision model that picks which fact goes in each field, and says how confident it is.
- **LLM**: a chat model (GPT-6 Luna) that reads all the fields and facts at once and returns a fill plan.

Whichever you choose, the values typed into the form are always **exact copies of your facts**. Nothing is invented or reworded.

**How it works:** see [the architecture page](docs/architecture.md) for how each brain fills a form, and why Jev costs more, in plain words.

## Contents

1. [Setup](#setup)
2. [Try it: watch a form get filled](#try-it-watch-a-form-get-filled)
3. [The seven test forms](#the-seven-test-forms)
4. [Results: Jev vs LLM](#results-jev-vs-llm)
5. [Videos](#videos)
6. [Your own form](#your-own-form)
7. [Settings](#settings)
8. [Reading the output](#reading-the-output)
9. [Tests and troubleshooting](#tests-and-troubleshooting)
10. [Architecture: how each brain works](docs/architecture.md) (separate page)

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and an [OpenRouter](https://openrouter.ai/) API key.

```powershell
git clone https://github.com/MrMfrht/fine-print-detective.git
cd fine-print-detective
uv sync                              # install dependencies
uv run playwright install chromium   # install the browser (or set PLAYWRIGHT_CHANNEL=msedge in .env)
copy .env.example .env               # then open .env and paste your key into OPEN_ROUTER_API_KEY
```

Every run calls a model through your key. The costs below are what each run actually cost; the most expensive single form was about 3 cents.

## Try it: watch a form get filled

`.env.example` already points at a public demo form (the Tricentis insurance app, "Automobile" step), so after adding your key you can run:

```powershell
uv run python -m form_filling
```

To watch the browser do it, set `BROWSER_WATCH=true` in `.env`. The browser opens, the fields fill in, and it waits for you to press Enter before closing.

To switch brains, set `FORM_MATCHER=jev` or `FORM_MATCHER=llm` in `.env` and run again.

### Record a video

Run `uv run playwright install ffmpeg` once. Then set `BROWSER_VIDEO_DIR=artifacts/videos` and the browser records each run, at full speed, as a `.webm` file (the path is printed at the end). For example, to record Jev and then the LLM filling the medical-intake form:

```powershell
$env:BROWSER_WATCH="true"; $env:BROWSER_VIDEO_DIR="artifacts/videos"
$env:BENCHMARK_FORMS="medical_intake"
$env:BENCHMARK_MATCHERS="jev"; uv run python -m examples.form_filling.benchmark.run
$env:BENCHMARK_MATCHERS="llm"; uv run python -m examples.form_filling.benchmark.run
```

The run prints one JSON row per field and ends with a summary line like:

```
llm calls: 1, 889 input + 148 output tokens, $0.0002. Statuses: {'matched': 8, 'unmatched': 1}
```

## The seven test forms

All the forms below are included in the repository, with their facts and the expected final values, so you can run them yourself.

| Form | Fields | What makes it tricky |
| --- | --- | --- |
| Tricentis Automobile (public website) | 8 | A real site with a search box that must stay empty, and 4 facts that match nothing |
| Job application | 16 | A confirm-email field, a datalist, decoys about a previous employer |
| Medical intake | 24 | Four people with identical labels (name, phone, email), `false` checkboxes, a field that unlocks after a checkbox |
| Checkout | 27 | Shipping vs billing with identical labels, country → province dropdowns, a custom dropdown, a password field |
| Visa application | 38 | Three numbered "Companion" sections with identical labels (one left empty), a 40-country list |
| Conference registration | 21 | Two multi-selects (one a custom widget), similar labels (L vs XL), facts with no field |
| Banking | 310 | 48 repeated beneficiary blocks, an iframe, a shadow root, decoy facts, dependent fields |

### Run the five generated forms

This fills all five with **both** brains, scores each against the expected values, and prints a comparison table. It costs about a cent in total.

```powershell
uv run python -m examples.form_filling.benchmark.run
```

Narrow it down with environment variables (in `.env` or on the command line):

| Setting | Example | Effect |
| --- | --- | --- |
| `BENCHMARK_FORMS` | `visa_application` or `checkout,medical_intake` | Only these forms |
| `BENCHMARK_MATCHERS` | `jev` or `llm` | Only this brain |
| `BROWSER_WATCH` | `true` | Show the browser and pause after each form |

For example, to watch the LLM fill the visa form:

```powershell
$env:BENCHMARK_FORMS="visa_application"; $env:BENCHMARK_MATCHERS="llm"; $env:BROWSER_WATCH="true"
uv run python -m examples.form_filling.benchmark.run
```

The form names are `job_application`, `medical_intake`, `checkout`, `visa_application` and `conference_registration`.

### Run the banking form

```powershell
uv run python -m examples.form_filling.banking.check
```

It uses `FORM_MATCHER` from `.env`, honours `BROWSER_WATCH`, and prints `Correct final values: 310/310` at the end.

### Run the public demo form

That's the `uv run python -m form_filling` command from the section above.

## Results: Jev vs LLM

Each form was filled once by each brain and scored against the expected values. Time covers inspecting the form, matching and writing (not starting the browser). Cost is what OpenRouter billed for a first run of that form.

| Form | Fields | Jev | | | LLM | | |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | **correct** | **cost** | **time** | **correct** | **cost** | **time** |
| Tricentis Automobile | 8 | 8/8 | $0.0002 | ~4 s | 8/8 | $0.0002 | **~3 s** |
| Job application | 16 | 16/16 | $0.0004 | **2 s** | 16/16 | **$0.0003** | 6 s |
| Medical intake | 24 | 24/24 | $0.0009 | **3 s** | 24/24 | **$0.0004** | 6 s |
| Checkout | 27 | 27/27 | $0.0008 | **3 s** | 27/27 | **$0.0004** | 6 s |
| Visa application | 38 | 31/38 | $0.0019 | **3 s** | **38/38** | **$0.0006** | 7 s |
| Conference registration | 21 | 21/21 | $0.0008 | **2 s** | 21/21 | **$0.0004** | 6 s |
| Banking | 310 | 310/310 | $0.0262 | **12 s** | 310/310 | **$0.0016** | 16 s |
| **Total** | 444 | 437/444 (98.4%) | $0.0312 | **29 s** | **444/444 (100%)** | **$0.0039** | 50 s |

Bold marks the better result for each measure (correct, cost, time). Ties are left plain.

Times are from a round in which every request was answered. When the connection to OpenRouter drops a request, it is sent again after `MODEL_TIMEOUT_SECONDS`, and the run takes that much longer.

### What the numbers say

- **Accuracy:** both are good. The LLM was perfect on all seven forms, in every round. Jev's only misses are in the visa form's three identical "Companion" sections, where it puts a neighbouring field's value in some fields (a date of birth in a passport box, for example) and leaves others empty. It was 83–100% confident about the wrong picks, so the confidence check can't catch them. It also once missed a multi-select value that scored 0.79 against the old 0.8 bar; the bar is now 0.6, since correct values scored 0.75–0.98 across our runs and wrong ones never above 0.04.
- **Cost:** about the same on small forms, and the LLM pulls ahead as forms grow: 1.3× cheaper on the job application, 16× on the banking form. Jev is asked one question per field and every question carries a copy of the whole fact list, so its cost grows with fields × facts. The LLM reads the fields and facts once. The [architecture page](docs/architecture.md) explains this step by step.
- **Time:** Jev is faster per form when the connection behaves, 2–3 s against 3–7 s, because it answers in parallel and writes nothing. On the 310-field form it's 12 s against 16 s.
- **Calls:** every form is one matching pass. Fields that are disabled until another field is filled (country → province, a checkbox that unlocks a reference box) are asked about in the same request and written once they unlock. The LLM makes exactly 1 call per form; Jev makes 1 to 9 depending on the form's size.
- **What Jev still offers:** a confidence score for every field, and a built-in guarantee that it can only pick one of your facts. The LLM gets the same guarantee from a check we do afterwards: a value that isn't an exact copy of a fact is reported, never written.

One run per form is a small sample. Run both on your own form before choosing. For a plain-language summary of when Jev is worth it, see [docs/jev-for-form-filling.md](docs/jev-for-form-filling.md).

## Videos

Both brains filling the medical-intake form (24 fields: four people with identical labels, a multi-select, `false` checkboxes, and a field that unlocks after a checkbox). Click a link and GitHub plays the video.

| Video | Result |
| --- | --- |
| [Jev fills the medical-intake form](docs/videos/medical-intake-jev.webm) | 24/24 correct, 2 calls, $0.0009, 3.9 s |
| [The LLM fills the medical-intake form](docs/videos/medical-intake-llm.webm) | 24/24 correct, 1 call, $0.0002, 7.3 s |

The empty form sits for a few seconds while the model thinks, then every field fills in a burst, then the unlocked field fills. To record your own, see [Record a video](#record-a-video).

## Your own form

1. Point `FORM_URL` at the page (a `file:///C:/...` path works for a local HTML file).
2. Write a facts file and point `FORM_FACTS` at it:

   ```json
   {
     "applicant full name": "Dalia Haddad",
     "applicant email": "dalia.haddad@example.com",
     "willing to relocate": true,
     "dietary requirements": ["Vegetarian", "Nut allergy"]
   }
   ```

   Use a list when a multi-select should get several values. Name facts after their owner ("co-owner email") when the form covers several people. Facts that match no field are simply ignored.
3. If the form is only reachable through a link, set `FORM_OPEN_LINK` to that link's exact text.
4. Run `uv run python -m form_filling`.

The filler fills the current page only. It never clicks Next or Submit.

## Settings

All settings live in `.env`. A setting also present in your shell overrides the file.

| Setting | Default | Meaning |
| --- | --- | --- |
| `OPEN_ROUTER_API_KEY` | required | Your OpenRouter key |
| `FORM_URL` | required | The page with the form |
| `FORM_FACTS` | required | The facts JSON file |
| `FORM_OPEN_LINK` | none | A link to click before looking for the form |
| `FORM_MATCHER` | `jev` | `jev` or `llm` |
| `FORM_LLM_MODEL` | `openai/gpt-6-luna` | Chat model used when `FORM_MATCHER=llm` |
| `BROWSER_WATCH` | `false` | `true` shows the browser and pauses before closing it |
| `BROWSER_SLOW_MO_MS` | `0` | Pause after each browser action, in ms, so a watched run is easy to follow |
| `BROWSER_VIDEO_DIR` | unset | Save a 1280×720 `.webm` video of each run into this folder |
| `MODEL_TIMEOUT_SECONDS` | `30` | How long to wait for a Jev answer before sending the request again (the LLM gets double, at least 60 s) |
| `PLAYWRIGHT_CHANNEL` | Chromium | Use an installed browser instead, e.g. `msedge` |
| `FORM_CONCURRENCY` | `4` | Model requests sent at the same time |
| `FORM_MULTI_SELECT_THRESHOLD` | `0.6` | Jev only: how sure it must be to tick a multi-select value |
| `FORM_SINGLE_VALUE_MIN_CONFIDENCE` | `0.6` | Jev only: below this, a pick is reported instead of written |
| `FORM_TOKEN_BUDGET` | `100000` | Largest request before it's split into smaller ones |
| `FORM_FACTS_PER_REQUEST` | unset | Jev only: cap on facts per request (at most 254) |

## Reading the output

Each row has a `status`:

| Status | Meaning |
| --- | --- |
| `matched` | Typed in and verified. `detail` shows the value as it now appears. |
| `unmatched` | No fact fits this field, so it was left alone. |
| `needs_review` | Something was unsure: Jev wasn't confident enough, a value wasn't an exact copy of a fact, two options had the same label, or the value didn't pass the field's own validation. Nothing was written. |
| `unavailable` | A dropdown has no option with that value. |
| `skipped` | This kind of field isn't supported yet (radio buttons, sliders, switches). |

The last line sums up the calls, tokens and cost, taken from what OpenRouter reports.

## Tests and troubleshooting

`uv run python -m unittest discover -s tests` runs the offline tests. They mock the models and use a local browser, so they're free.

| Problem | Fix |
| --- | --- |
| `Set FORM_URL in .env …` | Add that setting to `.env` |
| It looks stuck | It's waiting for a model answer. Compare the "sent" and "answered" lines to see which request is missing. Jev occasionally never answers; after `MODEL_TIMEOUT_SECONDS` (30 s) the request is sent again, up to 3 times. |
| Many `needs_review` rows | Read each row's `detail`. For Jev, try lowering the two threshold settings. |
| A multi-select misses a value with Jev | Lower `FORM_MULTI_SELECT_THRESHOLD`. Correct values have scored 0.75–0.98 in our runs and wrong ones at most 0.04. |
| `OpenRouter … returned HTTP 429` | Lower `FORM_CONCURRENCY` |
| The browser won't start | `uv run playwright install chromium`, or set `PLAYWRIGHT_CHANNEL=msedge` |

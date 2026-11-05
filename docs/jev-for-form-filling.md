# Jev for form filling: pros and cons

Jev is a model that picks answers from options you give it. It never writes text of its own.
For form filling, we give it each field and the facts we have, and it picks which fact goes where.

## Pros

- **It never invents values.** Jev can only pick one of your facts, and the value is typed in exactly as you wrote it.
- **It tells you how sure it is.** Each answer comes with a confidence score, so unsure answers can be held back for a person to check.
- **It's cheap on normal forms.** A 310-field test form with 79 facts was filled **310/310 correctly** for about **$0.03** in 15 seconds, and five of six smaller test forms were filled perfectly.
- **It's fast.** Jev answers all the questions in a request at the same time, in about 3–7 seconds per request.
- **You only pay for input.** Jev's output is free.

## Cons

- **It can't rewrite anything.** It can't change a date's format, join a first and last name, or write free text such as "describe your situation".
- **Cost grows with fields × facts.** Every field's question carries its own copy of the full fact list. On the same 310-field form, a language model (GPT-6 Luna) given all the fields and facts in one prompt also scored 310/310, for **$0.002** against Jev's **$0.026**, because it reads the facts once.
- **There's a limit of 255 options per question.** Long fact lists have to be split into groups, which adds extra requests.
- **Very large requests can time out.** In our largest test, some requests took longer than 90 seconds and had to be retried.
- **Multi-selects are expensive.** Each fact gets its own yes/no question for each multi-select field.
- **It can be confidently wrong in repeated sections.** On a visa form with three identical "Companion" sections, it got 6–7 of 38 fields wrong in each of three runs, putting neighbouring fields' values in them with confidence scores of 0.83–1.0, so the confidence check didn't catch them. The language model filled the same form 38/38 every time.

## When to use it

| Form | Use |
| --- | --- |
| You want a confidence score per field, and a guarantee that only your facts can be chosen | **Jev** |
| Many fields **and** many facts, repeated sections, or cost matters | **A language model** (126/126 on five test forms and 310/310 on the banking form, 2–14× cheaper than Jev) |
| Values need reformatting or writing | A language model for those fields |

Both are available in this project: set `FORM_MATCHER=jev` or `FORM_MATCHER=llm`.

## Ideas we haven't tested yet

- **Dropdowns and multi-selects:** ask about the field's own choices (for example, its 6 allergies) instead of all the facts. This could make them about 100 times cheaper.
- **Long lists such as countries:** first find which choices appear in the facts, then ask Jev only about those.
- **Dates:** convert date formats in code before typing them in.

---

*All results and costs are from real runs on the same day: the 310-field banking form and five generated forms (126 fields), each filled once by Jev and once by the language model. The timeouts were seen in a larger test that was stopped early.*

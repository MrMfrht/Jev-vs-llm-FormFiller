# Jev for form filling: pros and cons

Jev is a model that picks answers from options you give it. It never writes text of its own.
For form filling, we give it each field and the facts we have, and it picks which fact goes where.

## Pros

- **It never invents values.** Jev can only pick one of your facts, and the value is typed in exactly as you wrote it.
- **It tells you how sure it is.** Each answer comes with a confidence score, so unsure answers can be held back for a person to check.
- **It's cheap on normal forms.** A 310-field test form with 79 facts was filled **310/310 correctly** for about **$0.03**.
- **It's fast.** Jev answers all the questions in a request at the same time, in about 3–7 seconds per request.
- **You only pay for input.** Jev's output is free.

## Cons

- **It can't rewrite anything.** It can't change a date's format, join a first and last name, or write free text such as "describe your situation".
- **Cost grows with fields × facts.** Every field's question carries its own copy of the full fact list. A 680-field form with 636 facts was projected at about **$0.65**, roughly 12 times the estimated cost of a mid-priced language model.
- **There's a limit of 255 options per question.** Long fact lists have to be split into groups, which adds extra requests.
- **Very large requests can time out.** In our largest test, some requests took longer than 90 seconds and had to be retried.
- **Multi-selects are expensive.** Each fact gets its own yes/no question for each multi-select field.

## When to use it

| Form | Use |
| --- | --- |
| You already have the exact values, and the form is small to medium | **Jev** |
| Many fields **and** many facts | Jev with extra filtering, or a language model |
| Values need reformatting or writing | A language model for those fields |

## Ideas we haven't tested yet

- **Dropdowns and multi-selects:** ask about the field's own choices (for example, its 6 allergies) instead of all the facts. This could make them about 100 times cheaper.
- **Long lists such as countries:** first find which choices appear in the facts, then ask Jev only about those.
- **Dates:** convert date formats in code before typing them in.

---

*The 310-field result and its cost are from a real run. The large-form cost and the language-model comparison are estimates.*

# Architecture

## The steps both brains share

1. **Open the page.** If the form is behind a link, click it first.
2. **Read the form.** List every field: its label, its section, its type, and its options if it has any. Password and file fields are skipped. Fields that are greyed out for now are listed too, marked "may unlock later".
3. **Take the easy matches.** If a field's name is exactly the name of a fact, fill it straight away. No model is needed.
4. **Ask the brain** which fact goes in each remaining field. This is the only step that differs, see below.
5. **Fill in the form**, then read every value back to check it stuck.
6. **Fill the fields that unlock** (for example, a province list that appears after a country is chosen) with the answers we already have.

## The LLM

The LLM gets everything in **one message** and sends back **one answer**.

1. **Build the answer format.** We describe the exact shape the answer must have: a list of "field ID → value(s)". This goes into the message, so the model can't answer in any other shape.
2. **Add the instructions:** copy every value exactly as written, use only the facts given, leave out a field if no fact fits, and only multi-selects may get more than one value.
3. **Add the fields:** one short line per field, such as `Medical intake / Emergency contact / Phone`.
4. **Add the facts:** every fact once, as a name and a value, such as `emergency contact phone = +1 604 555 0190`.
5. **Send it.** The model replies with the fill plan.
6. **Check the plan.** Every value must be an exact copy of one of the facts. Anything else is reported and never typed in.

## Jev

Jev can't write a plan. It can only **pick one option from a list**, and say how sure it is. So we turn the form into many small multiple-choice questions.

1. **One question per field:** "Which of these facts goes in this field?" The options are **all the facts**, plus "none of these".
2. **Multi-selects** get one yes-or-no question per fact: "Does this fact belong in this field?"
3. **Group the questions** into requests and send them, several at a time.
4. **Read the answers.** Each answer is the chosen fact and a confidence score. If Jev isn't sure enough, the field is reported instead of filled.

A question can hold at most 255 options, so a very long fact list is split into groups, and fields that get more than one answer are asked once more.

## Why Jev costs more

Both are paid by the amount of text sent (tokens). Jev is cheaper per token, but it gets sent far more text.

- **The LLM reads the fact list once.** The fields and facts go in one message.
- **Jev reads the fact list once per field.** Every question carries its own full copy of the options, which are all the facts. A form with 258 fields means 258 copies of the fact list.

It's like handing one fact sheet to one person versus photocopying the whole sheet for every field on the form.

On the 310-field banking form:

| | Text sent | Cost |
| --- | --- | --- |
| LLM | about 9,000 tokens | $0.0016 |
| Jev | about 620,000 tokens | $0.0262 |

Jev sends about 70 times more text. Its lower price per token brings that down to about 16 times the cost. On a small form there are few copies to make, so the two cost about the same. The bigger the form and the longer the fact list, the wider the gap.

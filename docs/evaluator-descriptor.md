# Evaluator descriptor

A result may carry an optional `descriptor` from format `livingproof-evaluator-result/1.1.0`. The verification report does not have a built-in list of evaluators, icons, or names. It renders whatever descriptors are present, in any number. A new evaluator can appear in a run without a report change, as long as that evaluator supplies the fields below.

The descriptor is part of the evaluator's own result. The report reads it. The report does not fill it in. The names in the examples, including Scenario, Robot health, Run Integrity, Human review, and Agent review, are example data. They are not built-in evaluators and they are not copy this repository owns.

This repository holds the contract. It does not draw the report.

## Title

Aaron's decision, 12 November 2026: the evaluator's `title` is used exactly, everywhere a consumer shows that evaluator's name. That is the mark label, the callout row leader, and the panel heading. A consumer never appends the word "evaluator".

`short_title` is used only where a mobile mark label lacks room for `title`. It must read as the same name: a shortening, not a different label. It keeps every word of `title`. Each word is that word, or the start of that word. `Robot health` is a title. `Health` is not a valid `short_title` for it, and neither is `Robot`, because each of those is a different label. `Rob health` is a valid shortening. `Robot health evaluator` is a title only when that full string is the name the evaluator actually chose, and the same string is `evaluator.display_name`.

The examples in this repository use the names already on the 1.0 fixtures: `Scenario` and `Run Integrity`. Those titles fit a mark, so the examples omit `short_title`.

## Where the object sits

`descriptor` is its own object on the result. It is not a field of `evaluator`, and it is not a new payload beside `scenario` and `integrity`.

`evaluator.kind` selects the payload. It is `scenario` or `integrity`. `descriptor.kind` is a display label. A consumer must not read `descriptor.kind` to choose a payload. The two fields share a name and nothing else. Putting the display label on `evaluator` would overload the selector, so this contract does not do that.

A request does not carry a descriptor. The object is result output.

Format `livingproof-evaluator-result/1.0.0` must not include `descriptor`. A document that already validated as 1.0.0 still validates. Format `1.1.0`, and a later 1.minor, may include it. The object is optional. A 1.1 result that omits it is valid.

Inside the object, `tier` is required. The other fields are optional. `findings` is required only in the sense that a problem the summary should show is written there. An empty array, or a missing array, means this evaluator is satisfied for the summary.

## Fields

All text is plain text. A consumer must escape every text field for display and must not interpret markup, entities, or embedded HTML. An ampersand is allowed, as in `R&D` or `Q&A`. It is plain text and must be escaped, not read as a character reference. The characters `<` and `>` are rejected, so a stored value cannot carry a tag.

| Field | Required | Maximum | Meaning |
| --- | --- | --- | --- |
| `title` | recommended | 80 | The name, used exactly. Same string as `evaluator.display_name` when both are present. |
| `short_title` | recommended | 40 | Mobile shortening of that same name. See Title. |
| `icon` | optional | 8192 bytes | Sanitised inline SVG. See Icons. |
| `icon_accessible_name` | recommended when `icon` is present | 120 | Accessible name for the mark. |
| `purpose` | recommended | 400 | One or two sentences on what this evaluator judges. |
| `version` | recommended | 64 | The evaluator version. Same string as `evaluator.version` when present. |
| `kind` | optional | 40 | Display label only. Not the payload selector. |
| `source` | optional | 120 | Where the opinion came from, as the evaluator states it. Display only. |
| `tier` | required | | Default tier. See Tiers. |
| `success_copy` | optional | 400 | Plain text for the details panel when this evaluator is satisfied. |
| `details_copy` | optional | 1000 | Further plain text for the details panel. |
| `grade` | optional | 0–100 | An integer percentage for a ring. See Grade below. |
| `findings` | when the summary should show a problem | 50 entries | One callout row each. Empty or omitted means satisfied. |

`grade` is an integer from 0 to 100 inclusive. A fraction, a string, and a boolean are rejected. Strict validation also rejects a float whose fractional part is zero, such as `100.0`. The accepted token is an integer such as `100` or `0`. The report may show the grade as a percentage ring when the evaluator is reporting a problem and the grade is not a complete success (100). The report does not assume which evaluators supply a grade.

There is no `problem_copy` field. The problem statement is `findings[].text`.

### Text limits

The source note did not set lengths. Format 1.1 adds these maximums. They are character lengths, except the icon, which is also capped at 8192 UTF-8 bytes. The schema's `maxLength` of 8192 on `icon` is a character cap of the same number. The validator rejects a value whose UTF-8 encoding is longer than 8192 bytes even when the character count is inside that cap.

Plain text also rejects ASCII controls (U+0000 through U+001F), DEL and the C1 controls (U+007F through U+009F), and the line separators U+2028 and U+2029. A newline is a control character and is rejected. A value that is only whitespace is rejected. Write two sentences in `purpose` as one stored string.

An ampersand is allowed. `R&D` and `Q&A` validate. A consumer must escape `&` so it is shown as an ampersand. It is not decoded as an entity.

### Fields on each finding

| Field | Required | Maximum | Meaning |
| --- | --- | --- | --- |
| `text` | required | 280 | The one-line problem statement. |
| `severity` | optional | 40 | A plain-language severity word or short phrase, for example "Needs attention". |
| `time` | optional | 40 | When in the trial this was observed, as plain text, for example "12.4 s". |
| `trial` | optional | | An integer from 0 to 999999, or a plain-text reference of at most 40 characters. A fraction is not an integer trial, and neither is a zero-fraction float such as `7.0`. The string "7.5" is a text reference and is allowed. |
| `tier` | optional | | Overrides the descriptor `tier` for this entry only. |
| `reported_by` | optional | 80 | Attribution for this entry. The report shows `{reported_by}: {text}` as escaped plain text. Use a role such as "Reviewer 1", not a person's name, unless the evaluator output already contains a name the report is only repeating. |

A run may include any number of results, and each result may include up to 50 findings.

## Icons

A catalog of known icons would hard-code evaluators into the report. The icon is a sanitised inline SVG on the descriptor. When a 1.1 or later result omits `descriptor.icon`, the same subset applies to `evaluator.icon`.

The validator enforces this subset. Documentation alone does not.

### Allowed

- A single `svg` root with a `viewBox`. `0 0 24 24` is the usual box. Any non-empty `viewBox` is accepted.
- Child elements may be only `path`, `circle`, `rect`, `line`, `polyline`, `polygon`, and `g`. Nesting is allowed inside `g`. The root may be empty.
- `fill` and `stroke`, in any capitalisation of the attribute name, are exactly `currentColor`, `none`, or `transparent`. No other colour value.
- The UTF-8 byte length of the SVG string is at most 8192.

A namespace declaration for `http://www.w3.org/2000/svg` is allowed. It is a namespace name, not a fetch. Geometric attributes such as `d`, `stroke-width`, `cx`, and `points` are allowed. The icon is an SVG element. An XML declaration is a processing instruction and is rejected.

### Rejected

The validator rejects the icon when it is outside the subset. That includes:

- any element other than those listed, including `script`, `style`, `foreignObject`, `image`, `use`, `text`, `font`, `a`, and `title`
- `href`, `xlink:href`, `src`, or `srcset`
- any other external reference, including an attribute value that contains `url(`, a `javascript:`, `data:`, `http:`, `https:`, `file:`, or `blob:` URL
- an event attribute, any attribute whose name starts with `on` (compared case-insensitively, so `onclick` and `ONLOAD` are rejected, and so is a name that only shares that prefix)
- a `style` attribute
- a missing `viewBox`
- a payload larger than 8192 UTF-8 bytes
- CDATA, a comment, a document-type declaration, an entity reference (including `&amp;` and `&#60;`), or a processing instruction
- text content that is not whitespace
- a root that is not `svg`, or a document that is not a single well-formed element

Parsing uses defusedxml, which does not resolve external entities. A document-type declaration is rejected before, and again by, that parser.

### Fallback mark

If the icon is omitted, or the consumer's own subset check rejects the icon it would inline, the report draws a generic mark: a letter disc from the first letter of `short_title`, or of `title`, or "E". The letter is plain text, escaped. This fallback is report chrome. This contract does not draw it.

The report may add its own wrapping attributes after a successful check, for example a CSS class, `aria-hidden`, or `aria-label` from `icon_accessible_name`. It does not otherwise rewrite the SVG.

The example art shipped with a `title` element, `role`, `aria-labelledby`, and, on one mark, the stroke `#0E8785`. A `title` element is not in the subset, and a hex colour is not `currentColor`. The fixtures drop the `title` element and those ARIA attributes, put the accessible name in `icon_accessible_name`, and use `currentColor`. The accessible name is the evaluator's title, not a title with "evaluator" appended.

## Tiers

`tier` sets the line order on the summary. The values, in order, are:

1. `verdict`
2. `health_finding`
3. `test_system_status`
4. `review`
5. `observation`

Unknown tiers are rejected by this schema. The source note sorted unknown tiers last. This contract has a closed list instead, so a typo cannot sort into an unnamed bucket.

Each finding is ordered by its own `tier`, or the descriptor's `tier` when the finding omits it, then by `title` (case-insensitive), then by its order in `findings`. When `title` is omitted, the name used for that sort is `evaluator.display_name`, which this envelope always has.

Only a finding in the `verdict` tier can change the run's verdict ring. Other tiers inform the reader and do not change that ring. The tier does not write a robot verdict into the scenario payload, and it does not change `integrity.run.success` or `integrity.run.percentage`. Those payload rules are unchanged.

### Example mappings

These mappings are how filled examples set `tier`. They are not report rules, and they are not evaluators this repository implements.

| Example | `title` | `tier` |
| --- | --- | --- |
| Scenario | `Scenario` | `verdict` |
| Robot health, when a written requirement sets the limit | `Robot health` | `verdict` |
| Robot health, when there is no written requirement limit | `Robot health` | `health_finding` |
| Run Integrity | `Run Integrity` | `test_system_status` |
| Human review | `Human review` | `review` |
| Agent review | `Agent review` | `observation` |

One descriptor may put different findings in different tiers. A finding's `tier` overrides the descriptor default for that entry only.

## Reconciliation with the 1.0 envelope

The merged 1.0 result already has `evaluator.kind`, `evaluator.execution`, `evaluator.display_name`, `evaluator.version`, and `evaluator.icon`. Format 1.1 keeps every 1.0 document valid. These are the conflicts and the resolutions.

**Payload kind.** `evaluator.kind` is the selector (`scenario` or `integrity`). The descriptor note's `kind` is display-only. Resolution: `descriptor.kind` is an optional plain-text label in its own object. It is not the enum. The selector is unchanged. A 1.0 document has no descriptor.

**Display name and title.** Both name the evaluator. The note says an omitted title falls back to the word "Evaluator". This envelope already requires `display_name`. Resolution: when `descriptor.title` is present it must equal `evaluator.display_name`. Consumers show that string exactly and never append "evaluator". When `title` is omitted, consumers use `display_name`. The generic fallback "Evaluator" applies only when a descriptor has neither a title nor an envelope display name. This schema always has `display_name`, so that fallback does not arise on a document this schema accepts. On a result at format 1.1 or a later 1.minor, that omitted title also puts `evaluator.display_name` and `evaluator.publisher` under the descriptor plain-text pattern, because those are the strings a consumer shows. A 1.0 result keeps the 1.0 checks on those two fields.

**Icon.** `evaluator.icon` is required. Its 1.0 check is only that the string is an `svg` element, so existing documents stay valid. The subset is stricter, and tightening `evaluator.icon` would be a breaking change for a 1.0 producer whose mark uses `text` or a paint colour. Resolution: when `descriptor.icon` is present it must be the same string as `evaluator.icon`, and that string must pass the subset. When `descriptor.icon` is omitted on a result at format 1.1 or a later 1.minor, `evaluator.icon` is checked against the same subset, because a consumer renders that mark. A 1.0 icon is not rechecked, so a 1.0 mark that uses `text` or a paint colour stays valid. A report that inlines an icon still applies the same subset and uses the letter disc if the check fails.

**Version.** `evaluator.version` is required and is semantic versioning. The note's `version` is free text, "as the evaluator states it". Resolution: when `descriptor.version` is present it must equal `evaluator.version`. The details panel repeats the one version the envelope already states. This does not loosen the envelope version.

**Grade.** The envelope, the scenario payload, and the integrity payload all reject `grade`, so a robot grade cannot sit in those objects. The note adds an optional integer grade for a percentage ring. Resolution: `descriptor.grade` is the only `grade` this contract accepts. It is not written into either payload. It does not fold step verdicts. That fold stays deferred. It is not `integrity.run.percentage`, and the two numbers are not required to match, because they are different facts. Integrity examples omit `descriptor.grade` so the fixture does not look like a copy of the run percentage. The scenario-with-icon grade is example data, not a fold of the steps.

**Findings.** An integrity check finding has `category`, `classification`, `summary`, and check-specific fields. A descriptor finding has `text` and the display fields above. Resolution: they are different arrays. This contract does not copy check findings into the descriptor. The words in the descriptor fixtures are example data written for the summary, alongside the payload, not a second encoding of the check.

**Format 1.1.0.** The run-integrity note used `1.1.0` as an illustration of a future kind such as health or observations. That illustration was not an assigned version. The format pattern already accepted any 1.minor. Resolution: `1.1.0` is this descriptor. It is not a new kind and not a new payload. A new kind remains a later minor, for example `1.2.0`. A 1.0 reader still drops unknown fields and still skips an unknown kind. The strict schema still rejects an unknown `evaluator.kind`.

**Titles in the source note.** The note's sample title is "Robot health evaluator", and its sample `short_title` is "Health". That fights Aaron's title rule. Resolution: the contract title is the name alone, for example `Robot health`. `Health` is rejected as a `short_title` for that name. The rule is in Title above, and the validator checks the word rule.

**Problem copy.** Issue 13 says the descriptor carries success, problem, and details copy. The note has `success_copy`, `details_copy`, and `findings[].text`. Resolution: follow the note. There is no `problem_copy` field.

**Text limits.** The note says the report escapes text and does not interpret markup. It does not set lengths. Resolution: 1.1 adds the maximums in the tables and rejects `<`, `>`, and the controls listed above. An ampersand is allowed as plain text. Consumers must escape all text, including `&`, and must not interpret it as an entity.

**Source art.** The example SVG files use a `title` element and, in one case, a hex stroke. Both are outside the subset. Resolution: fixtures use the same paths, rewritten into the subset, and say so. The original art is example data, not a second allowed icon format.

**The 1.0 consumer.** `consumer_accepts` keeps a fixed set of 1.0 keys. Resolution: `descriptor` is not in that set. A 1.0 consumer drops the object, including a malicious icon or a script in a finding, and validates the 1.0 fields. It does not run the SVG subset. Strict `validate_document` applies the descriptor schema and the subset. Both behaviours are tested. A 1.0 document that adds `descriptor` without bumping the format is rejected by the strict schema, because the field belongs to 1.1. The 1.0 consumer still accepts that document, because it drops the object.

No conflict required a break of the merged 1.0 contract. Existing 1.0 results do not gain a required field, and a 1.0 icon is not rechecked against the subset. A 1.1 or later result that omits `descriptor.icon` is rechecked, because that is the mark a consumer renders.

## What the report does with a descriptor

For each result present on the run:

- If `findings` is empty or omitted, the mark stays quiet. No callout.
- If there are findings, the mark is highlighted. The report writes one callout row per finding. The leader is that evaluator's icon and `title` (the exact title, with no "evaluator" suffix). Then the finding text. When `reported_by` is present, the row is the icon, the title, and `{reported_by}: {text}`.
- Optional `severity`, `time`, and `trial` may follow as muted meta, for example "Needs attention · 12.4 s · trial 7". The report does not rewrite the finding text.
- When one result has several findings, each finding is its own row, with the icon and title repeated.
- If three or more evaluators report a problem, the report prefixes the list with `{n} evaluators reported {m} problems`, with ordinary English plurals. `n` is how many results have at least one finding. `m` is the number of finding rows. The headline is shown only when `n` is 3 or more.
- Marks are ordered by the descriptor's `tier`, then by title. Finding rows use the finding tier, then title, then array order.
- Opening a mark shows that evaluator's title, version, purpose, source, tier, and `details_copy`. There is no always-visible "Evaluator details" heading.

The report does not invent an evaluator's name, icon, purpose, or callout.

### Copy the report owns

The report owns only generic chrome:

| Chrome | Wording |
| --- | --- |
| Grouping headline, when three or more evaluators report a problem | `{n} evaluators reported {m} problems` |
| All-quiet line, when every evaluator on the run is satisfied | `All {n} evaluators are satisfied.` |
| Fallback title | `Evaluator`, only when both `descriptor.title` and `evaluator.display_name` are absent. This envelope always has `display_name`. |
| Fallback mark | A letter disc, when the icon is omitted or fails the subset check. |
| Section labels that are not a named evaluator | Generic labels such as `Evaluators`. |

The report does not, by itself, name a particular evaluator, write that evaluator's purpose or callout, invent `reported_by` or a person's name, keep an icon catalog, or special-case an evaluator's grade or severity.

## Examples

Every fixture under `examples/descriptor/` is example data. The hashes, run ids, trial outcomes, grades, and URIs are synthetic. They are not recordings from a published run. Each pair is a 1.0 request and a 1.1 result. The request has no descriptor. The payloads are copies of the 1.0 fixtures named below, so the input hashes stay the hashes of those payloads.

- `examples/descriptor/scenario-with-icon/` copies `examples/scenario/graded/`. The descriptor has the scenario mark, a grade, and one finding. The grade `67` is example data. It is not a fold of the three step verdicts.
- `examples/descriptor/scenario-without-icon/` copies the same graded payload. The descriptor has the finding and omits `icon` and `grade`. The envelope icon stays the 1.0 placeholder.
- `examples/descriptor/integrity-with-icon/` copies `examples/integrity/pins-partial/`. The descriptor uses the Run Integrity mark and two findings. It omits `grade`, so the fixture does not copy `integrity.run.percentage`.
- `examples/descriptor/integrity-without-icon/` copies `examples/integrity/clean/`. The descriptor omits `icon` and `findings`, and it includes `success_copy`. That is the satisfied case.

The marks are the example art, rewritten into the subset. `icon_accessible_name` is `Scenario` or `Run Integrity`.

## Validating a 1.1 result

`tools/validate_contract.py` validates the envelope, dispatches integrity checks, and, when `descriptor` is present, checks the title, the short title, the version, the icon equality, and the SVG subset. On a 1.1 or later result that omits `descriptor.title`, it also applies the plain-text pattern to `evaluator.display_name` and `evaluator.publisher`. When that result omits `descriptor.icon`, it checks `evaluator.icon` against the SVG subset.

A consumer of major version 1 still accepts any `livingproof-evaluator-result/1.<minor>` document. It drops `descriptor` with any other field it does not know. Strict validation of a 1.1 document applies the descriptor schema and the subset. A 1.0 producer does not emit a descriptor. The strict schema rejects a descriptor on format `1.0`.

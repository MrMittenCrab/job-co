# Company intelligence research specification

This handbook defines the meaning and research rules for company intelligence.
The [JSON Schema](../schemas/company-intelligence.schema.json) defines the import
shape. Serialization and deterministic behavior below reflect the current
[`company.py`](../src/career_job_manager/company.py),
[`store.py`](../src/career_job_manager/store.py),
[`importing.py`](../src/career_job_manager/importing.py), and
[`company_ui.py`](../src/career_job_manager/company_ui.py) implementation.

## Purpose and client boundary

Company intelligence has two company-level views. **VALUE** reconstructs the
firm's Revealed Value Proposition primarily from observable client behavior.
**DELIVERY** explains the concrete people and entities through which the firm
delivers that value.

A **client** is the external decision-making entity that controls or materially
influences allocation of an addressable wallet to the focal company. A fund
manager can therefore be a broker's client even though the manager itself has
investors as clients. One relationship represents **client × service**.

## VALUE research fields

| Field | Meaning and representation |
| --- | --- |
| CLIENT | Named external decision-making entity; `client`. |
| SEGMENT | Client category; `segment`, free text, no controlled vocabulary. |
| SERVICE | Specific service bought from the focal company; `service`. |
| WALLET | Total business the client could reasonably allocate among competing providers for this service and period; observation `wallet`. It is not simply the client's total assets. |
| CAPTURE | Amount of that same wallet allocated to the focal company; observation `capture`. |
| SHARE | Derived `capture / wallet` only. Do not store it. |
| MOMENTUM | Prefer percentage-point change in Share between comparable periods; derived from observations. Optional relationship `momentum` is `up`, `flat`, `down`, or `null` when quantitative change is unavailable. |
| VALUE | Broad interpretation of what the client appears to value; one relationship `value` tag from the vocabulary below, or `null`. |
| BENEFIT | Specific free-text interpretation supporting Value; `benefit`. Editable through data/import, stored internally, and omitted from the normal VALUE table. It is not a deterministic matching key; there is no Benefit editor in the current UI. |

Value vocabulary (case-sensitive): **Research, Access, Execution, Financing,
Performance, Risk, Distribution, Technology, Service, Trust**.

Prefer observable behavior over company marketing claims. Keep sourced facts
distinct from interpretation, including Benefit. Do not invent unknown values:
unknown numeric data are `null`, never zero; zero capture means known zero.
Do not estimate Wallet merely from total assets, perform implicit FX conversions,
or infer exclusivity from evidence of one commercial relationship. Preserve
separate periods and available source/evidence metadata. Evidence is optional,
internal, and has no prescribed application structure; preserve supplied fields
and distinguish manual information from public sources.

## DELIVERY and editing

The fixed sections are **CONTROL**, **OPERATE**, and **SOURCE**, serialized as
`control`, `operate`, and `source`. Every row uses **ENTITY / TYPE / DETAIL**,
serialized as `entity`, `type`, and optional nullable `detail`.

| Section | Scope | Interactive TYPE choices |
| --- | --- | --- |
| CONTROL | Concrete people or organizations materially controlling or directing the company. | Controlling shareholder; Largest shareholder; Dominant shareholder; Founder; Chairman; CEO; CIO; General manager; Business head |
| OPERATE | Concrete legal or geographic entities through which the firm operates. | Parent; Subsidiary; Branch |
| SOURCE | Immediate economically meaningful suppliers only. | Supplier |

Do not equate largest shareholder with controlling shareholder without evidence.
Represent named management by actual people whenever possible, rather than vague
organizational units. Do not infer subsidiary status from branding, partnership,
or affiliation.

A **Supplier** is an external entity directly providing a product or service
incorporated into, or materially necessary for, the focal company's own client
offering. Do not recursively include suppliers' suppliers or incidental vendors
merely because the company buys from them.

Sections cannot be edited. ENTITY and DETAIL are editable text; ENTITY must remain
nonblank and clearing DETAIL stores `null`. TYPE uses the section-specific
dropdown above. Imported nonblank types outside those choices are preserved,
not relabeled; the schema therefore does not enumerate TYPE. Optional
`entity_kind` is preserved as extension metadata: the implementation defines no
entity-kind vocabulary or validation. Evidence and other extension fields survive
editing. A new row is persisted only after Entity and a supported Type are
explicitly supplied. Deleting a row requires the UI's confirmation.

## Import, storage, and missing data

Use a root object with `companies` for company-only research imports; no jobs or
version marker are required. Both `company import file.json` and `job import
file.json` use the same importer. Both launchers also support `export file.json`.
Canonical storage/export is `{"version": 8, "jobs": [...], "companies": [...]}`
in `~/Documents/Career/applications.json`. `version` is not an import gate.
Legacy `applications` is accepted when `jobs` is absent.

Required and optional fields:

- Company: nonblank `name` required. `id` is optional (string or `null`);
  absent/empty/null IDs generate a stable UUID5 from the normalized name for a
  new company. `aliases` (strings), `clients`, and `delivery` are optional arrays,
  defaulting to empty; these arrays cannot be `null`.
- Client relationship: nonblank `client` and `service` required. `segment`,
  `value`, `momentum`, `benefit`, `coverage`, `geography`, and `evidence` are
  optional. `observations` is an optional array of objects, not `null`.
  Coverage/geography may be a string or list of strings, or `null`.
- Observation: all fields optional, allowing partial merge updates. `period`
  normally uses consistent strings such as a year or year-month; numeric periods
  also survive import. Missing/null periods are unknown. `wallet` and `capture`
  are optional objects or `null`. Their `amount` is a JSON number or `null`, never
  a formatted string. `currency`, `unit`, legacy `units`, `service`, and `period`
  are optional; use explicit comparable currency and unit labels when known.
  `unit` takes precedence over `units`; absent both, the default is `currency`.
- Delivery: nonblank `entity`, nonblank `type`, and valid `section` required.
  `detail`, `entity_kind`, and `evidence` are optional.

Omit unknown optional fields or use `null` where allowed by the schema. Empty
text remains supported for optional text fields; an empty Value string is a
legacy unknown representation (including the default job metadata). Prefer
`null` in new research. Empty arrays represent no supplied entries. Evidence and
unknown extension fields have no required shape and remain open at every level.
The writer removes `share` from relationships and observations, even if imported.

For combined files, canonical jobs require nonblank `id`, `company`, and `job`.
Normalized jobs require nonblank `id`, `company`, `role`, and `when`; optional
`deadline`, `url`, and `description` are strings. `schema_version`, when present,
must be integer `1`. With that marker and no job containing a `job` key, the
normalized path requires `jobs`, even for an otherwise company-only document.
Without the marker, or if any `jobs` item contains `job`, the canonical path runs;
within it a `role` item without `job` still uses normalized parsing.
Normalized jobs cannot supply `action` or `Action`. Canonical job text fields use
empty strings, not nulls; optional matching metadata can be unknown/null.
`when` accepts a date, month, month range, or lowercase season. The application
additionally validates actual dates, range order, duplicate job IDs, and filesystem
names; schema validation does not replace those checks.

Import merging is deterministic:

1. Resolve companies by exact ID, then normalized incoming name against existing
   aliases, then existing names; if unresolved, try each incoming alias the same
   way. Keep an existing company's ID. A renamed company's old name becomes an
   alias. Normalization is Unicode NFKC, case folding, and joining Unicode word
   tokens with spaces (punctuation becomes separators).
2. Merge relationships by normalized `(client, service)`; observations by
   `str(period)`; DELIVERY by `(section, normalized entity, normalized type)`.
3. Explicit scalars, including nulls, overwrite; omitted keys survive. Objects
   merge recursively; lists retain existing entries and append distinct incoming
   entries. Empty incoming arrays do not delete stored rows. Changing a row's
   merge key can add a row rather than rename it.
4. Jobs match import identity/ID, not company and role. Existing Action and managed
   attachments are protected; omitted fields survive. A known Deadline is not
   erased by an empty incoming deadline, and more precise timing is retained.
   Unknown root and nested fields are preserved, subject to canonical legacy-field
   migrations and the removal of stored Share.

The importer currently validates only basic company/row structure, not Value,
Momentum, or numeric amount types. This schema enforces those research constraints;
some malformed data accepted by the permissive importer consequently fail it.

## Derived values and exact company aggregation

The latest observation is the maximum natural-sort period key: digit runs become
integers and nondigit runs retain their text, with numeric runs ordered before
text runs. Missing/null/empty periods use an empty key. This is not a calendar
parser. Ties retain the first observation. No older observation substitutes for
an unusable latest observation.

Share requires a truthy observation period, a nonempty normalized relationship
service, finite numeric Wallet > 0 and Capture >= 0, and matching signatures.
A signature is `(currency, unit, normalized relationship service)`; currency
must be truthy. Each amount's explicit period must equal the observation period;
its service (falling back to observation service, then relationship service)
must normalize to the relationship service. Currency/unit comparisons are exact;
no conversion or rescaling occurs. Share is not capped at 100%.

Relationship Δ sorts observations by descending period key and compares the
latest with the first earlier entry having a distinct period, valid shares,
matching Wallet signatures, and identical period strings after replacing every
digit with `#`. The result is `(latest share - prior share) × 100` percentage
points. This tests period shape, not economic comparability or adjacency; research
must ensure meaningful comparisons. Otherwise use explicit `up`/`flat`/`down`,
or unknown.

**Comparable capture weights** require every included relationship's latest
capture to have a finite nonnegative amount, a valid signature, a truthy period,
the same signature and period across all included rows, and a positive total.
Wallet is not required. Otherwise the entire included set falls back to counts.

| Company column | Current algorithm |
| --- | --- |
| CLIENTS | Count distinct nonempty normalized client names across all relationships. |
| SEGMENTS | Use comparable capture weights across all relationships; otherwise count distinct normalized clients separately within each segment. Segment labels are grouped by exact text, with falsy labels mapped to `-`. Sort descending weight, then case-folded label (stable input order for remaining ties). Skip labels normalizing to `other` or empty when selecting leaders, but retain their weights in the denominator. Append named segments until cumulative selected weight is strictly greater than 50% of the total; if never reached, include all named segments. Join with ` · `; no leaders displays `-`. A client in multiple segments can count in each fallback bucket. |
| SHARE | Unweighted median of valid latest relationship shares; exclude unknowns. Display one decimal percent, or `-`. No cross-relationship comparability test is applied to this median. |
| Δ | Unweighted median of numeric relationship Δ values, ignoring qualitative ones whenever any numeric result exists. Otherwise a qualitative direction must have a strict majority among qualitative results only; unknowns are excluded. Display signed one-decimal `pp`, an arrow (`↑`, `→`, `↓`), or `-`. |
| VALUE | First retain only relationships with a valid case-sensitive Value tag. Independently compute comparable capture weights on that subset; otherwise give each retained relationship weight 1. Sum by tag; choose highest weight, breaking exact ties alphabetically by tag. No valid tags displays `-`. |

## Job ↔ company matching

Company identity is the hard link: exact `company_id` first, otherwise normalized
employer name against aliases, then company names. An unresolved ID falls back to
name resolution. Employers without intelligence appear with empty views; jobs do
not generate intelligence.

Within that company, sort lexicographically by descending match counts in this
order: **service → coverage → geography → client segment → Value → text overlap**.
Each structural comparison intersects sets of normalized whole values (scalar
or list), not substring matches. Value matching retains only normalized controlled
tags. The final comparison counts distinct shared word tokens between job
`job`, `role`, `program`, `description_text`, `brief`, `description` and relationship
`client`, `service`, `coverage`, `geography`, `segment`, `value`.
Benefit and evidence never contribute. Ties retain existing order: stored client
order in VALUE, the current job list order in reverse navigation. Same-company
jobs without metadata remain visible. No runtime LLM, network call, or weighted
relevance score is required.

## External research workflow

```text
public web research + manual information
                ↓
              ChatGPT
                ↓
     handbook + JSON Schema
                ↓
      generated import JSON
                ↓
        local job-company app
```

Give the researcher this handbook and schema. Identify the focal company and
client/service boundaries, collect sourced observations and concrete DELIVERY
entities, separate interpretation, preserve unknowns, and generate schema-valid
JSON. Validate it, then import into the local app; retain evidence for later
updates. The repository stores code, this handbook, and the schema. The user's
current live intelligence database remains local and need not be committed.

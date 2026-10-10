# Company tables

The `company` and `job` launchers share `~/Documents/Career/applications.json`.
Company identity (`id`, `name`, `aliases`), company/job links, job records, evidence,
and unrelated metadata remain in that document. No second database or stored HOME
summary exists. The document version remains 8; job storage is unchanged.

Each company has exactly six table arrays, with lowercase field keys:

| Array | Columns in display order |
| --- | --- |
| `strategy` | Department, Revenue, Rank, Model |
| `makeup` | Department, Revenue, Scale, Mix |
| `direction` | Department, Revenue, Growth, Edge |
| `clients` | Client, Period, Engagement, Role |
| `franchise` | Entity, Parent, Footprint |
| `leadership` | Layer, Parent, Composition |

STRATEGY describes business strategy. FRANCHISE describes the corporate entity
hierarchy. All table fields are editable strings; missing fields or nulls render
as `-`. On save, cells become canonical strings. Literal middle dots delimit
phrases and normalize to exactly one space, a middle dot, and one space.
Empty phrases and standalone missing markers disappear. Other punctuation never
creates a phrase boundary. For example, `Alpha· Beta ·` becomes `Alpha · Beta`.

Opening an existing database renames the old `composition` array to `makeup`,
preserving every row and its metadata (appending to any existing `makeup` rows).
STRATEGY `position` migrates to `rank` and the old key is removed. If both keys
contain distinct nonmissing values, both survive in `rank`, joined by ` · `.
Imports accept `rank` (and migrate legacy `position`); exports emit `rank`.
It also normalizes stored table cells to the canonical separator.
The existing migration discards obsolete VALUE relationships (legacy
`clients` rows containing service/observation/value fields), the `delivery` array,
and any old company `value` field. It does not infer new rows from that data.
New-format rows survive and absent tables become empty arrays. This migration is
idempotent and writes only when the company representation changes. Old-format
imports are discarded by the same rule.

HOME has only Company and Departments. Departments is derived from STRATEGY,
ordered by descending Revenue and joined with ` · `; an empty summary is `-`.
Edited company profiles sort first; unedited JOB-employer placeholders sort second.
Each group sorts by normalized company name (Unicode NFKC, case folding and word
normalization), then ID. The persistent boolean `profile_edited` is set by explicit
company imports and successful manual saves, including identity-only edits and
profiles with empty tables. An exported `false` marker survives reimport; merging
identities never clears a `true` marker. Legacy records recover this status from
substantive table/profile data, evidence, research notes, ownership or aliases,
before obsolete data is discarded. Name-only records without such evidence remain
unedited; unknown historical activity is not inferred from dates or empty tables.
Departments, Revenue and modification dates do not determine HOME ordering.
All stored companies appear on HOME, including companies
without jobs; search and identity resolution remain unchanged. Returning from any company table restores the same company by ID
as the first visible row, retaining the search filter.

STRATEGY, MAKEUP, and DIRECTION sort by descending parsed Revenue. Currency
prefixes and k/m/mn/b/bn/t/tn scales are supported without changing displayed
strings or converting currencies. Missing and unparseable values come last in
stable order. CLIENTS sorts by the final year in Period, newest first, including
ranges such as `2012–2018`; missing and unparseable periods come last.

| Context | Keys |
| --- | --- |
| HOME | Up/Down select; Right opens STRATEGY; j opens jobs; / search; q quit |
| Company tables | S STRATEGY; M MAKEUP; D DIRECTION; C CLIENTS; F FRANCHISE; L LEADERSHIP |
| Table cells | Up/Down selects row in the same column; Left/Right selects column; Enter edits the selected cell; j opens jobs; i edits identity; Escape returns HOME |
| Text | Existing inline cursor, Ctrl+A, paste, and Space input; Enter commits and Escape cancels, returning to the same selected cell |
| Any normal row | Space toggles full wrapped content in place |
| JOB home/detail | c opens employer STRATEGY |

Collapsed cells have bounded widths and display-only Unicode ellipses, preferring
complete phrases. Expanded rows wrap every cell within the same widths. Editing
Revenue or Period re-sorts after commit while keeping the edited row selected.

Each table ends with a transient blank row. Select a cell, press Enter, and type to create a
row on commit; another blank row then becomes available. An untouched row is not
saved. Clearing one field saves `-`; clearing every substantive field removes the
row on commit, without a delete command or confirmation. Space expands/collapses
outside text editing and inserts a space while editing. Editing has no underline.

From company HOME or a table, j opens the existing job HOME with an editable
company search resolved by identity. Zero matches show the normal empty job
list. Use / to change the search or Escape in search to clear it; Left returns
to the company screen. No job is created by navigating.

The [JSON Schema](../schemas/company-intelligence.schema.json) describes imports.
Both launchers retain import/export support. Company imports resolve by ID, then
alias/name; existing IDs survive renames. Rows merge by optional row ID, otherwise
by the first column (plus Period for CLIENTS). Explicit fields update, omitted
fields survive, and distinct list metadata merges. Use the editor to delete rows.
Job import validation and protected application fields retain their existing rules.

# OffDayKit input and output profile

OffDayKit prepares native resource days-off records in an existing project. It
does not schedule tasks, calculate resource load, level resources, evaluate
expressions, follow links, import calendars, or claim working-time behavior.
Compatibility is deliberately restricted to the **GanttProject 3.4.3396** file
profile. Passing the Python tests is not evidence of native GUI acceptance; the
separate native probe has to establish that against the actual application.

## Run locally

Python 3.10 or newer and its standard library are sufficient. Run from this
repository; no package installation, service, network request or dependency
download is needed for the producer.

```sh
python -m off_day_kit inventory input.gan
python -m off_day_kit preview input.gan --recipe scripts/recipe.json
python -m off_day_kit preview input.gan --recipe scripts/recipe.json --resource 0 --resource 1
python -m off_day_kit apply input.gan --recipe scripts/recipe.json --resource 0 --resource 1 --output new-project.gan --report new-receipt.json
python -m unittest discover -v
```

Inventory and preview print JSON and create no files. Preview without a resource
selection lists candidate dates but proposes no additions. Apply requires one or
more `--resource` arguments **on every invocation**, including a no-op invocation.
Only existing IDs from that exact imported project are accepted. Success exits 0;
profile, file and command-argument failures exit 2. The apply receipt is both
printed and saved to the requested new JSON file.

## Recipe

Exactly these six JSON fields are required; all other fields are rejected:

```json
{
  "weekdays": ["friday"],
  "every_weeks": 2,
  "anchor": "2027-01-04",
  "start": "2027-01-04",
  "end": "2027-02-28",
  "exclusions": ["2027-01-22"]
}
```

- `weekdays`: one to seven distinct lowercase English weekday names
- `every_weeks`: integer 1 (weekly) or 2 (fortnightly); booleans are invalid
- `anchor`: ISO `YYYY-MM-DD`, and a Monday defining week zero
- `start`, `end`: finite ISO dates defining an **inclusive** window, 1–366 days
- `exclusions`: distinct ISO dates inside that window; an empty list is valid

The recipe never contains resource selections. Duplicate JSON keys and nonfinite
numbers are rejected. Dates before the anchor work in complete Monday–Sunday
weeks, using the same fortnight parity. Exclusions that are not recurrence dates
remain visible in the recipe but produce no candidate row. All recognized XML and recipe dates are limited to modern planning years **1900–2199**. The latest supported
window end is 2199-12-30, leaving room for a one-day exclusive end.

For the example, candidates are January 8, January 22, February 5 and February 19.
January 22 is excluded. If resource 0 already has `[2027-01-08, 2027-01-11)` and
resource 1 has `[2027-02-01, 2027-02-02)`, selecting those two resources adds two
intervals to resource 0 and three to resource 1. Resource 2 is untouched. Each new
record starts on its candidate date and ends on the following date.

## Accepted XML

Input must be a local regular file, BOM-free, strict UTF-8, XML 1.0, with one
`project` root and `version="3.4.3396"`. An XML declaration is optional; if present
its encoding must be UTF-8. An ISO date must be exactly `YYYY-MM-DD` and denote an
actual calendar day within 1900-01-01 through 2199-12-31. This range avoids the native
GregorianCalendar historical cutover and short-year formatting behavior. The same
range applies to anchors, windows, exclusions, vacation endpoints, task/baseline/view
dates, explicit calendar dates and declared custom dates. Resource and task IDs must be canonical nonnegative decimal
32-bit integer strings (no signs, whitespace or leading zeroes except `0`).

The producer independently implements an explicit element/attribute allowlist
based on the pinned native schema and genuine GUI-authored fixture. It accepts
the documented project, view, calendar, task, resource, allocation, vacation,
baseline and role shapes, including nested tasks and declared custom properties.
Unknown tags, unknown attributes, incorrect nesting and duplicate singleton
sections are errors. The obsolete `overriden-day-types` and `days` placeholders
must be empty; their nonempty legacy content is unsupported.

Exactly one each of `tasks`, `resources`, and `vacations` must exist. Absence of
`vacations` is rejected; the tool does not invent a location for a missing
section. Both `<vacations/>` and a nonempty `<vacations>…</vacations>` work, as does
an explicitly paired empty section. The section accepts only whitespace and
`vacation` elements. Each vacation must have exactly `start`, `end`, `resourceid`,
no children, and no non-whitespace text. Its end must be strictly after its start
and is interpreted as **exclusive**. Overlapping and repeated existing vacation
records are accepted and preserved, without normalization or consolidation.

Duplicate resource/task IDs, duplicate custom-property definitions, missing
custom-property definitions, and dangling vacation/allocation/dependency
references fail closed. Task/baseline start dates, optional task `thirdDate`,
project `view-date`, and recognized custom date values/defaults are checked too.
Calendar `date` records require explicit numeric year/month/day that form a valid
date; months are 1–12, as in the pinned
[native calendar writer](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/net/sourceforge/ganttproject/io/CalendarSaver.java).
Its recurring dates use an empty year; recurring/wildcard calendar dates are
outside this profile. This is a
bounded adapter, not a validator for every historic GanttProject file or feature.

Comments outside the vacation section and CDATA in native text elements
(`description`, task `notes`, view `timeline`, `option`, calendar `date`) are
accepted and retained byte for byte. Comments and CDATA inside `vacations` are
rejected. Standard XML escaped characters and numeric character references are
handled by the XML parser. DTDs, custom entities, processing instructions,
namespaces, encoding conflicts, duplicate attributes, invalid UTF-8 and invalid
XML characters are rejected. Project links, text, custom values and expression
strings are inert: the producer never evaluates them, fetches them or uses them
as paths.

## Bounds

Bounds are checked before data is retained by application structures. XML is
validated with incremental Expat callbacks; no whole XML tree is built. The raw
source is bounded before reading and retained solely for exact byte splicing.

| Item | Limit |
| --- | ---: |
| Project input and generated output | 10 MiB each |
| Recipe JSON | 64 KiB |
| Inclusive recipe window | 366 days |
| Explicitly selected resources | 100 |
| Existing plus generated vacation intervals | 10,000 |
| XML element nesting | 32 |
| XML elements | 50,000 |
| Attributes per element / total | 32 / 200,000 |
| UTF-8 bytes per attribute name plus value | 16,384 |
| Total UTF-8 attribute bytes | 4 MiB |
| Total decoded text and comment bytes | 2 MiB |
| Text per element or single comment | 256 KiB |

Recipe validation and selection validation are strict, including duplicate
selections. The finite window bounds candidate generation to 36,600 resource/date
rows. To avoid amplifying thousands of overlapping input records into a huge
receipt, each candidate includes the number of covering intervals plus one exact
covering interval example, rather than repeating every covering record. Inventory
provides every original interval once under its resource.

## Byte preservation and receipt

The parser retains source-byte offsets. For an existing nonempty section,
generated records are inserted immediately before its parsed closing tag. For a
self-closing section, only that section is expanded. No XML tree serialization
occurs. Every original vacation record and every byte outside the vacation
section remain unchanged, including indentation, quotes, attribute order,
comments, CDATA, task properties, unselected resources and calendar content.
Existing records are never shortened, deduplicated, sorted or coalesced. Any day
inside an existing interval for that selected resource is already covered.

A plan with no additions returns the **exact original bytes**, including for a
second application of the same recipe. Preview and apply receipts identify the
anchor, inclusive window, weekdays, cadence, all exclusions, selected IDs, every
candidate (including exclusions), existing coverage, exact additions, counts,
no-op status, and SHA-256 of the source and proposed/generated output. Coverage
and exclusion are independent flags; a covered excluded day is still excluded.
Candidate status is `excluded`, otherwise `covered`, otherwise `add`.

Both output and receipt destinations must be new. They cannot alias each other,
the project input or the recipe. Existing files, hard links and dangling symlinks
are refused. Both destinations are reserved with exclusive creation before
writing either content. Detected failures attempt cleanup of only the files this
invocation created; an OS/process crash can leave incomplete **new** files. The
input is never opened for writing. No cross-file crash-atomic transaction is
claimed. New files are created with owner-only permissions on POSIX.

File input rejects a final-component symlink, FIFO, directory or device before
opening, then checks the opened descriptor and identity. POSIX nonblocking and
no-follow flags also defend against a file being swapped for a FIFO or symlink.
Reads request at most the configured byte limit plus one and detect ordinary
concurrent size/timestamp changes. Parent directory symlinks are resolved by the
OS; this is not a filesystem sandbox or a protection against a hostile process
that can rewrite the surrounding directories.

## Python API

```python
from off_day_kit import Recipe, apply, parse_project, preview

project = parse_project(source_bytes)
recipe = Recipe.from_dict(recipe_dictionary)  # Or Recipe.from_json(json_bytes).
plan = preview(project, recipe, ["0", "1"])
receipt = plan.to_dict()
output_bytes = apply(project, plan)
```

`parse_project` accepts bytes, checks the entire bounded profile and returns a
`Project` with immutable source bytes, resource inventory, original intervals and
section offsets. `preview` also validates generated bytes against every XML
bound before returning a deterministic immutable `Plan`; resource
IDs are strings and are sorted numerically in receipts. `apply` verifies that
the plan still matches the source and recipe, and returns bytes without any file
access. Callers should use parsed projects and validated recipes rather than
constructing implementation dataclasses themselves. `OffDayKitError` reports
profile and safety failures. The CLI adds bounded regular-file reads and
exclusive destination creation.

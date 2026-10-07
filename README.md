# OffDayKit

Prepare finite resource days-off patterns in an existing GanttProject file. The Japanese/English offline workbench's actual downloads have passed the official native GUI, chart, save and fresh-process reopen gate, with independent Python and literal date checks.

Choose resource IDs from the imported project, a weekly or fortnightly weekday pattern, a Monday anchor, an inclusive date window and exclusions. OffDayKit previews every candidate date, distinguishes existing coverage from exclusions, and appends only uncovered one-day intervals. Existing vacation records and every byte outside the vacation section are preserved. Reapplying the same pattern produces an exact byte-identical no-op.

This prepares native days-off records and their display. It does not schedule tasks, level resources or optimize workloads. GanttProject already has per-resource Days off editing and project-wide calendar import. p2gan can generate vacation records while rebuilding a project; this adapter's narrower difference is selective preparation in an existing file. [Primary sources](docs/SOURCES.md)

## Offline workbench

Download [off-day-kit-offline.zip](off-day-kit-offline.zip), extract every file and open `index.html` in a current Chrome or Chromium browser. No server, account or network connection is needed. Choose a project, explicitly select resource IDs, set a weekly/fortnightly pattern and finite window, then preview and acknowledge before saving a new `.gan`. Changing the file, recipe, selections or settings invalidates the old review.

All candidate dates are listed, including exclusions and already-covered days. Resource browsing uses search and pages of at most 100; the date review uses pages of 60. The complete JSON receipt contains every resource/date row. Printing includes the current review page and its overall summary. Recipes contain no resource identities; project and recipe imports require a fresh selection. The original file is never written, and links/expressions stay inert. [Browser acceptance contract](docs/BROWSER-ACCEPTANCE.md)

## Python CLI

Python 3.10+ and its standard library are sufficient for the producer. Run from this source directory:

```sh
python3 -m off_day_kit inventory input.gan
python3 -m off_day_kit preview input.gan --recipe scripts/recipe.json --resource 0 --resource 1
python3 -m off_day_kit apply input.gan --recipe scripts/recipe.json --resource 0 --resource 1 --output prepared.gan --report receipt.json
```

Both output destinations must be new. Input is never opened for writing. Resource selections are required on each apply invocation and are deliberately excluded from reusable recipes. The receipt includes the recipe, exact selected IDs, candidate dates, exclusions, coverage, additions and input/output hashes. Inventory and preview create no files.

The example recipe selects Fridays in alternate weeks anchored to January 4, 2027, through February 28, excluding January 22. Native stored ends are exclusive: a day off on February 5 is stored with an end of February 6. The [profile](docs/INPUT-PROFILE.md) explains supported XML, filename safety, all limits and failure behavior.

The first profile is explicitly limited to **GanttProject 3.4.3396 Beta VI**, UTF-8 `.gan`, a 366-day window within 1900–2199, 100 selected resources and 10,000 total intervals. Unknown structures, invalid dates, duplicate IDs, dangling references, DTD/custom entities and unsupported input forms fail closed. Existing links and expression strings remain inert data. No resource file or remote URL is followed.

## Native evidence and current status

The actual [browser-to-native run](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37592459664) passed using the official pinned GanttProject ZIP, its unmodified launcher and vendor-recommended Liberica Full JRE. Genuine mouse/keyboard editing first created A's January 8–10 range and B's February 1 single day; saved XML ended them on January 11 and February 2. The exact packaged offline workbench then downloaded a new file with five uncovered records. The official application opened those actual bytes, displayed every intended date for A/B and C's empty list, saved, closed and reopened in a fresh process. Both native saves retained all seven intervals and complete task/resource/calendar fields.

January/February chart screenshots show the selected days, the excluded January 22 without a marker, B's original February 1, and C unchanged. The separate literal oracle verifies raw byte preservation, every receipt row, exact native dates and a byte-identical repeated application; four deliberately corrupted files fail that oracle. All 63 Python tests, 29 JavaScript tests, 29 browser scenarios, 131 artifact-member hashes and 729 vendor/runtime integrity checks passed. [Exact browser/native evidence](docs/BROWSER-VERIFICATION.md) · [Acceptance design](docs/TEST-DESIGN.md)

The JavaScript producer is a separate implementation with bounded tokenization and raw-byte insertion. Its 29 Node tests include 290 comparisons with the unchanged Python implementation and exact native-fixture output/receipt/no-op parity. The same hosted run opened the exact six-file offline package with networking disabled and sandboxed Chromium, downloaded real files, and sent them through the independent oracle and official GUI. JA/EN desktop, 390-pixel mobile, 200% root-text, keyboard, cancellation and all four print-PDF pages were inspected. Printing retains the pinned-beta and no-scheduling scope.

The repository contains original source and synthetic test instructions. Native dependencies and browser test tools are installed separately only by hosted verification. No vendor application binaries, original-code license grant, hosted interface or user data is distributed. Delivery is GitHub source plus a downloadable offline package.

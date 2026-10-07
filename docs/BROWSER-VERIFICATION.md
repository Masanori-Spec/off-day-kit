# Offline browser and native verification

The exact packaged offline workbench passed [run 37592459664](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37592459664) on 2026-10-07 at commit `51b4132920f3e02bb09b2287ac9681899a023aff`. Actual browser downloads were consumed by the unmodified official GanttProject 3.4.3396 Beta VI GUI. The independent Python implementation and handwritten date oracle checked the output separately.

## Package and actual files

- Shipped offline ZIP: six original source files, 111,854 bytes; SHA-256 `14158716e358e10f4eedbd688d8f8f6dea12f3cb06bded98a3c273839a0cd3e9`
- Raw GitHub artifact `11469596716`: 3,935,175 bytes, 132 members; SHA-256 `f23cbd368f56279899688f66f572d57f0520a486049980592896f8e10b10cf86`
- Genuine GUI-authored input: 3,457 bytes; SHA-256 `21d5147f83ff94631c8ad00275a6104c654dc25751ccad865429c337767be11a`
- Actual browser `.gan` download: 3,817 bytes; SHA-256 `ac83e1e53179368389fef4c42aff49a55589e595656ec7eff33b39833e54d33a`
- Actual complete JSON receipt: 3,404 bytes; SHA-256 `1807625b616d9a67cbe4786474adabb7f10e6ea18fa4e7f647e679ca58f14459`
- Native saved and fresh-process reopened/saved files: each 3,811 bytes; SHA-256 `d2669adf15cd527600d69159543dd079cafabec0378b98779f481d42208396d5`

The raw artifact digest, member CRCs and all 131 internal file hashes were verified. Every shipped file matches its source and package manifest, including the worker bundle's exact reconstruction from original core and handler source. The package contains no vendor runtime or application binary.

## Browser output through the real consumer

The workflow first used real mouse/keyboard actions to create A's January 8–10, 2027 interval, B's February 1 single day, C's empty state and a native task sentinel. Native stored ends are January 11 and February 2. It saved, closed and reopened this actual fixture before browser work.

The browser opened the exact extracted package through `file://`, selected that fixture and resource IDs 0/1, and applied alternate Fridays anchored Monday January 4 over January 4–February 28 inclusive, excluding January 22. Its real download adds only A's February 5/19 and B's January 8/February 5/19. Existing record bytes and every byte outside `vacations` remain identical. All eight resource/date receipt rows match the independent literals, including two exclusions and A's covered January 8.

Eight actual downloads cover the `.gan`, complete review, resource-free recipe, repeated output, reapplication/no-op output and review, and shifted-anchor output and review. Their hashes were checked. The Python producer independently produces the same output bytes and complete receipts; both repeat paths are byte-identical. The native consumer then opened the actual browser `.gan`, displayed all seven intervals in the three resource dialogs, displayed the January/February charts, saved to a new path, closed and opened a fresh application process. It repeated all three date-list checks and saved again. Complete task/resource/calendar data and exact intervals persist. Both original input and browser output hashes remain unchanged.

The charts visibly retain A/B's January 8, exclude January 22, retain B's February 1 and show A/B's February 5/19. C remains empty. The saved viewport dates, daily zoom and complete target columns agree with the screenshots. These observations concern records and display; no scheduling behavior is inferred.

Four separate valid XML files fail the independent literal date/record oracle: a following end extended by one day, assignment to C, an excluded January 22 interval, and an actual browser download using a shifted anchor. The three mutations start from the actual browser download. These are independent-oracle negative controls, not claims that each corrupted file was loaded in the GUI.

## Interface, limits and visuals

All 29 browser scenarios passed with no page/console errors or HTTP requests. Both Chromium launches used their sandbox; networking was disabled. Cases cover real keyboard file-chooser activation, Japanese/English switching, explicit ID selection, acknowledgment invalidation, deterministic downloads, exact no-op, resource-free recipes, all dates/coverage/exclusions, malformed inputs, bounds before file reads, inert markup-looking names/links, same-file reselection and explicitly dispatched empty input changes.

Race tests cover late file/recipe reads, Clear during pending reads and parser workers, settings changed during preview, worker startup failure/recovery and a queued real result from an earlier revision. Resource search and pagination keep at most 100 controls mounted; review pagination exposes all 300 rows in its larger test while the complete JSON contains every row. Large diagnostics remain bounded. These cases do not claim actual OS-picker cancellation.

Japanese and English desktop/mobile screenshots were inspected. The 390-pixel view has no page-wide horizontal overflow; the review table's full rightmost column is reachable and measured. A 200% root-text mobile check remained contained and operable. Each language produced a two-page print PDF; all four rendered pages were inspected. The eight fixture rows, summary, both hashes, pinned-beta scope and no-scheduling statement are readable and complete. Printing is deliberately the current review page and summary, while JSON contains the full review.

All 29 JavaScript tests passed again with the actual native fixture enabled, including 290 independent Python comparisons; all 63 Python tests passed. Every one of 153 installed full-runtime package files matched the verified payload. All 729 vendor/runtime checks after execution and 97 observed native mouse destinations passed.

## Scope and reproducibility

The accepted profile remains UTF-8 GanttProject 3.4.3396 Beta VI files, years 1900–2199, an inclusive window of at most 366 days ending no later than December 30, 2199, at most 100 selected resources and 10,000 total intervals, and the documented input/resource limits. Unknown structures fail closed. Existing links and expressions stay inert. Other versions, scheduling, resource leveling and workload optimization are not established.

In the first UI run, the runner-default compiler rejected `--release 17`; the workflow now explicitly uses the standard installed JDK17 compiler while retaining the pinned full JRE21 consumer. The next run passed browser behavior but a test still expected the prior fixture's whole-file hash. Genuine native authoring generates a fresh task UID; that assertion now hashes the current actual source/output while preserving exact receipt/output comparisons and the independent literal/Python/native checks.

These particular two native saves are identical, but native resave byte equality is not a general guarantee. Raw producer preservation and independently checked native field/record equality are the contract. GitHub artifacts expire after 14 days; the workflow reproduces the synthetic checks. Delivery is source plus an offline package, without hosting or an original-code license grant.

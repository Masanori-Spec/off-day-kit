# OffDayKit

Prepare finite resource days-off patterns in an existing GanttProject file. The Python producer is implemented; **its generated-output native GUI gate is pending**. The separate GUI-authored endpoint fixture has passed. No product UI is shipped yet.

Choose resource IDs from the imported project, a weekly or fortnightly weekday pattern, a Monday anchor, an inclusive date window and exclusions. OffDayKit previews every candidate date, distinguishes existing coverage from exclusions, and appends only uncovered one-day intervals. Existing vacation records and every byte outside the vacation section are preserved. Reapplying the same pattern produces an exact byte-identical no-op.

This prepares native days-off records and their display. It does not schedule tasks, level resources or optimize workloads. GanttProject already has per-resource Days off editing and project-wide calendar import. p2gan can generate vacation records while rebuilding a project; this adapter's narrower difference is selective preparation in an existing file. [Primary sources](docs/SOURCES.md)

## Run

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

The actual [GUI endpoint probe](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37579068549) passed using the official pinned GanttProject ZIP, its unmodified launcher and vendor-recommended Liberica Full JRE. Genuine mouse/keyboard editing created A's January 8–10 range and B's February 1 single day; saved XML ended them on January 11 and February 2. A fresh application process reopened the actual file, displayed both intended ranges and C's empty state, and saved a fresh file with unchanged resource/vacation/task records. All 729 vendor/runtime integrity checks passed. [Exact baseline evidence and remaining gate](docs/TEST-DESIGN.md)

The producer passes 63 unit tests and a separate literal date/byte oracle on that actual fixture. Its five-addition output, January/February chart display, native save/reopen and all four distinguishing negative controls are the next hosted acceptance gate. Unit tests and the baseline GUI probe do not establish generated-output compatibility.

The repository contains original source and synthetic test instructions. Native dependencies are installed separately only by the hosted verification workflow. No vendor binaries, original-code license grant, hosted interface or user data is distributed. This is an offline file-preparation prototype, not a GUI automation product.

# OffDayKit

Native-first feasibility work for a small GanttProject days-off recipe tool. **The native GUI probe is unrun; no conversion tool or product UI is shipped yet.**

The intended utility takes an existing UTF-8 `.gan` file and an explicitly selected set of resource IDs, expands a weekly or fortnightly weekday pattern over a finite inclusive window, and appends only uncovered days-off intervals. It will preserve existing vacation records and every byte outside the edited section. Resource selections must be made again for each imported project.

This is preparation of native days-off records and their display. It makes no scheduling, resource-leveling, workload optimization or working-time guarantee. GanttProject already has a per-resource Days off editor and project-wide calendar import. Existing generators such as p2gan can write vacation records while rebuilding a project; this proposed adapter has the narrower goal of modifying an existing project's vacation section. See [primary sources and limitations](docs/SOURCES.md).

## Current native gate

The hosted workflow downloads and verifies the official **GanttProject 3.4.3396 Beta VI** AppImage. It runs the unchanged application under standard Xvfb and creates three synthetic resources through genuine GUI controls:

- RESOURCEA: January 8–10, 2027, inclusive in the Days off editor
- RESOURCEB: February 1, 2027, one visible day
- RESOURCEC: no days off

The expected persisted ends are **January 11** and **February 2**, respectively. The gate must establish those exclusive ends from actual GUI-authored files, then close the app, reopen that exact file in a fresh process, inspect all three Days off dialogs, and save a fresh native file. A task sentinel must retain its dates and fields.

The original read-only Java agent discovers public Swing/JavaFX controls and screen bounds. It has no bytecode transformer, model setter or action invoker. Every edit uses actual X11 mouse/keyboard input. Screenshots, saved `.gan` files, literal XML checks and vendor integrity records are retained for independent review. Source review alone is not runtime proof.

No native executable, vendor source tree, original-code license grant, hosted interface or user data is included. Native software is downloaded only on the disposable hosted runner. Product conversion and its additional native acceptance gate remain future work.

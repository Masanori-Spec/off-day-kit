# Native acceptance contract

## Accepted GUI-authored endpoint baseline

The first gate passed at commit `3b2621dc355709542cdeffc56aaf92ade85705e4`, [run 37579068549](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37579068549), on 2026-10-07.

- Actual artifact ID `11463807776`, 923,640 bytes, 42 files; raw ZIP SHA-256 `a70bffdae7b36c3f2dcde5412069f57da108e613f6388b00f8de8d23fe034580`
- GUI-authored file SHA-256 `38873f444b839bf40b01c305f5a8c3f6e6b4988263be73d8cebde764ce1556d0`
- Fresh native reopened/save file SHA-256 `c0c48fb12d084dc3940a3a40d90603475e342b78df70436653dca1f7198ebd50`

The unmodified official GanttProject 3.4.3396 Beta VI application creates resources and dates through actual GUI controls under standard Xvfb/Openbox. A read-only Java agent discovers public Swing/JavaFX text and bounds; it registers no transformer, invokes no model setters and calls no action handlers. Actual edits use X11 mouse/keyboard input. Pointer coordinates are observed before clicks; missing or ambiguous controls fail. The inspector waits for the application's existing UI threads. It snapshots loaded class references once per discovery pass; this changes no application classes or values.

The native-authored fixture is literal:

| Resource | Visible dates | Stored start | Stored exclusive end |
| --- | --- | --- | --- |
| 0 / RESOURCEA | January 8–10, 2027 | 2027-01-08 | 2027-01-11 |
| 1 / RESOURCEB | February 1, 2027 | 2027-02-01 | 2027-02-02 |
| 2 / RESOURCEC | None | None | None |

A native task sentinel is also created. The exact resource, vacation and task records survive a real application close, fresh-process reopen and save to a new path. All three reopened Days off dialogs were independently viewed, including C's empty list. Only native view state differs between those two files; byte-identical native resaves are not claimed. All 41 recorded artifact-member hashes, 35 observed click destinations and 729 after-execution vendor/runtime checks passed. No scheduling behavior was tested.

## Actual recurrence producer gate

This gate passed at commit `d37aa05a1323344c15b461d714633a6c09a5bf05`, [run 37585161113](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37585161113). [Exact output and proof hashes](VERIFICATION.md) identify the actual producer/native artifacts.

The extended workflow repeats that genuine GUI authoring route. It then runs the actual `python3 -m off_day_kit apply` CLI on the resulting saved file. Its recipe selects resources 0 and 1, Fridays every two weeks, anchored Monday January 4, 2027, over January 4–February 28 inclusive, excluding January 22.

The separate `date_oracle.py` imports neither the producer nor the UI harness. It advances literal Fridays by fourteen days and cross-checks the handwritten candidate list: January 8, January 22, February 5 and February 19. It requires all eight resource/date review rows, including two exclusions and A's pre-existing January 8 coverage. Exactly five intervals must be appended: A gets February 5 and 19; B gets January 8, February 5 and 19; C stays unchanged. Every new end is the following day.

The raw output is checked before native loading. Every original record's byte sequence and all bytes outside the vacations section must remain identical. The receipt's selected IDs, recipe, all coverage/exclusion values, counts, additions and hashes must match the independent literals. A second actual CLI application must return identical bytes with zero additions.

The official GUI then opens that exact produced file. The test selects each actual resource row, verifies its name, checks every displayed Days off row against literal text, and retains screenshots. Genuine chart zoom/scroll controls navigate to January and February. Native daily zoom3 (34 pixels per day) gives room for the required columns; OCR must locate January 22/February 19 fully within the chart header with a 40-pixel right margin. Fresh native position saves establish the actual viewport dates before small daily adjustments; the final chart saves must show January 4 and February 1. Screenshots with native month/year headers require independent inspection of the expected markers, including C's unchanged row and the excluded date. They do not establish scheduling or resource leveling.

The test saves to a new native file, closes the app, starts a fresh process on that file, repeats all three displayed-date checks and saves again. Both actual native saves must retain all seven intervals and the complete task/resource/calendar subtrees; view navigation state may change. The original GUI fixture and producer output hashes must still match their pre-consumer bytes.

## Distinguishing negative controls

Four real, valid XML files traverse the same independent raw date/record oracle:

1. Advance a new interval's end by one extra day
2. Assign a new A interval to unselected C
3. Add the explicitly excluded January 22
4. Run the actual producer with the Monday anchor shifted to January 11

All four must fail the literal interval contract without relying on a receipt hash mismatch. They are independent-oracle controls; native GUI execution of each corrupted file is not claimed. The positive generated file still has to pass the real official GUI consumer.

## Bounds and evidence limits

63 unit tests cover recurrence boundaries, exact body/section preservation, overlapping coverage, no-op behavior, XML/declaration/entity/resource limits, malformed IDs/references, nonblocking file reads, symlink/FIFO races and exclusive output creation. They do not substitute for native acceptance.

The entire hosted run is bounded, with separate deadlines for GUI authoring and generated-output consumption. Official application/runtime releases are size/hash verified, installed runtime files match their package payload, and all vendor/runtime regular files are checked again after execution. Every required native file is newly saved; stale evidence cannot satisfy the gate. Only synthetic files, logs and screenshots are retained. No vendor binary is uploaded in the artifact.

The generated-output gate passed, including all three fresh-process reopened dialogs and independently inspected January/February chart markers. The producer is limited to its documented pinned-beta profile. Product UI/browser behavior, other native versions, arbitrary historic `.gan` features and scheduling/leveling are outside current evidence. A future browser producer must send its actual downloaded `.gan` through the same raw preservation oracle and official GUI/save/fresh-reopen route. GitHub artifacts expire after 14 days; the workflow can reproduce the checks from source.

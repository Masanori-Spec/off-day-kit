# Native producer verification

The bounded Python producer passed [hosted run 37585161113](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37585161113) on 2026-10-07 at commit `d37aa05a1323344c15b461d714633a6c09a5bf05`. This is actual GUI consumption of the CLI's output, with genuine GUI authoring of its synthetic input. The later [offline browser acceptance](BROWSER-VERIFICATION.md) has its own actual-download/native proof; this historical record establishes the earlier CLI/native boundary.

## Exact evidence

- GitHub artifact `11465459141`: 1,837,477 bytes, 99 files
- Raw artifact ZIP SHA-256: `8300a07cff43bcc10ed5ed4bdfe4c73158966d2ad5c500ea31c0c97e35c9396c`
- GUI-authored input: 3,457 bytes, SHA-256 `d7ca8ecdee49d93497c588d2a551a51fcebc5f59efd6804eb42af357b80ce5e3`
- Actual generated output: 3,817 bytes, SHA-256 `7f7724ac9b1e61b1c8fa7e439b3d6f2e6a0c44d9242b23add07374eff82a0937`
- Complete receipt: SHA-256 `bf4624c979e99bd7cd600f88e2d0e50c29ce59632371f9d2c1f7b8be86caca22`
- First native save: SHA-256 `f2651f984b635b94bd37e431236802ebec62758474aa5ca720525769b86d72bb`
- Fresh-process reopened native save: SHA-256 `cd4141b3c62bbd67c114c47a4301cc9a1ad02f9d347b1fe267b0951735111b8d`

The raw ZIP digest and all members' CRCs were checked; all 98 internal file hashes match. The original GUI input and generated file stayed byte-identical during native consumption. Native saves may rewrite formatting/order and view state, so their whole-file byte equality is not claimed. The independent native comparison retains all seven exact intervals and complete task/resource/calendar data, while permitting only native view state changes elsewhere.

## Observed behavior

The original A interval displays January 8–10 and stores the exclusive end January 11. B's original February 1 stores end February 2. The producer appends February 5 and 19 to A, and January 8, February 5 and 19 to B. C remains empty. Every new interval ends the following day.

The independent date oracle checks all four candidate dates and eight resource/date review rows: January 8, January 22 excluded, February 5 and February 19, with A's January 8 already covered. Existing record bytes and all bytes outside the vacation section remain identical. The actual repeated CLI application returns exactly the same output bytes with zero additions.

The official application opened that produced file, displayed all intended rows for each resource, saved it to a fresh path, closed, and started a fresh process on the saved file. All three reopened dialogs were checked again. January and February screenshots show the expected yellow absence markers for A/B, no January 22 marker, B's original February 1, and no markers for C. Exact native position saves and fully visible date columns support the screenshot review.

Four separate valid-XML corruptions fail the same independent raw date/record oracle: an extra end day, assignment to unselected C, the excluded January 22, and an actual producer run with a shifted fortnight anchor. These are oracle controls, not claims that each corrupted file was loaded in the GUI.

## Runtime and scope

The official GanttProject 3.4.3396 Beta VI ZIP and BellSoft Liberica Full JRE 21.0.12.1+1 DEB were verified against their pinned sizes/digests. The unmodified supported launcher used that runtime. All 153 installed runtime package files matched the verified payload, and all 729 application/runtime regular-file integrity checks passed after execution. The read-only inspector made no model changes; 97 observed mouse destinations supported normal GUI input. All 63 producer/filesystem unit tests passed.

The earlier AppImage probe could not load the inspection agent because its trimmed runtime omitted instrumentation. A standard Ubuntu JDK lacked JavaFX, producing the official runtime warning; the vendor-recommended full runtime resolved that dependency. The first generated-output attempt reached the expected dialogs and native save but stopped at an overly narrow chart-navigation bound; the reviewed retry accounts for native week alignment while retaining exact final viewport/date checks.

This proves the documented Python producer profile and actual native record/display behavior for the pinned beta. It does not establish scheduling, resource leveling, workload optimization, other GanttProject versions or future browser output. No vendor binary or original-code license grant is distributed. Public Actions artifacts expire after 14 days; the source workflow reproduces the synthetic checks.

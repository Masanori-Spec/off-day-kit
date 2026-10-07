# Official sources and bounded scope

Checked 2026-10-07. The native target is GanttProject **3.4.3396 Beta VI**, not a stable-release compatibility claim.

## Workflow difference

- [Issue 210](https://github.com/bardsoftware/ganttproject/issues/210) requests reusable holiday sets and recurrence.
- [Recurring work patterns discussion](https://help.ganttproject.biz/t/recurring-work-patterns-calendar-resource-loading-costs/2678) describes weekly and alternate-Friday patterns and the manual days-off workflow. Maintainer guidance distinguishes chart markings from scheduling behavior. OffDayKit will retain that limited claim.
- Native per-resource Days off editing and project-wide ICS import already exist. [p2gan](https://github.com/tensorworks-llc/p2gan/blob/aa8612b399c55ee84d35c0a235921b449d99f454/src/p2gan/models.py) can represent vacations; its generator reconstructs a complete project. The intended difference is a finite, explicitly selected recurrence recipe, duplicate avoidance, review and a vacation-section-only patch of an existing file.

## Exact official pins

- [Release](https://github.com/bardsoftware/ganttproject/releases/tag/ganttproject-3.4.3396), tag commit `36964e221d53cf52e72a3ab81722b15819be6253`
- [AppImage used by the probe](https://github.com/bardsoftware/ganttproject/releases/download/ganttproject-3.4.3396/ganttproject-3.4.3396.AppImage): asset `566721059`, 178,039,288 bytes, SHA-256 `2147e92f25ea4c9efad30980b3e4d15def7ceeaec08c89ddf9b7eceb9fb0586c`
- [Official cross-platform ZIP](https://github.com/bardsoftware/ganttproject/releases/download/ganttproject-3.4.3396/ganttproject-3.4.3396.zip): asset `566731029`, 80,256,592 bytes, SHA-256 `22ab7129525b25158a41f921ae92617a436b15bb3913a970acd6ec80edfd32e4`; researched alternative, not executed by this probe

The release API independently confirms sizes/digests; the workflow rechecks actual bytes before execution. All extracted vendor regular files are hashed before and after the GUI gate. The probe does not alter vendor classes or launch options that change system security.

## Exclusive ends and genuine GUI boundary

- [DateIntervalListEditorFx.kt](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/net/sourceforge/ganttproject/gui/DateIntervalListEditorFx.kt): GUI selection calls `DateInterval.createFromVisibleDates`; it advances the visible last day to the next day boundary. The reverse display conversion subtracts one day from the model end.
- [GanttDialogPerson.java](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/net/sourceforge/ganttproject/gui/GanttDialogPerson.java): the actual Days off tab and OK action commit those intervals to the resource.
- [VacationSaver.java](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/net/sourceforge/ganttproject/io/VacationSaver.java): writes the model `start`, `end` and `resourceid` fields.
- [ResourceLoader.kt](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/net/sourceforge/ganttproject/parser/ResourceLoader.kt): reads the stored endpoints directly. Its old equal-start/end comment is not evidence of the current GUI convention.
- [PropertySheet.kt](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/biz/ganttproject/app/PropertySheet.kt): links visible labels to editor controls with the public `labelFor` property used by read-only UI discovery.
- [Keyboard bindings](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/resources/resources/keyboard.properties) and [local storage UI](https://github.com/bardsoftware/ganttproject/blob/36964e221d53cf52e72a3ab81722b15819be6253/ganttproject/src/main/java/biz/ganttproject/storage/local/LocalStorage.kt) ground actual new-resource/save/open keyboard and local-file actions.

## Required later product gate

Only after the GUI-authored endpoint proof may the recurrence producer be treated as native-compatible. Its fixture selects A and B, alternate Fridays anchored to Monday January 4, 2027, through February 28 inclusive, excluding January 22. Eligible dates are January 8, February 5 and February 19. A already covers January 8 and must receive two intervals; B receives three; C stays unchanged. Each added one-day interval ends the following day.

An independent Python date oracle must compare every candidate/covered/excluded date, the exact five additions, existing vacation bytes and bytes outside that section, then feed the actual produced `.gan` to the real application. Native Days off dialogs/chart, save, close and fresh reopen must confirm the resource/date sets and unchanged task dates. Corrupted exclusive ends, assigning C, restoring excluded January 22 and shifted fortnight anchors must fail the same oracle.

The planned profile is UTF-8 XML with a maximum 10 MiB input, 366-day window, 100 selected resources and 10,000 intervals. Invalid dates, DTD/entities, duplicate IDs, dangling references and unsupported structures must fail closed. Existing links and expressions remain inert data. No external file traversal, remote fetch, input code execution or scheduling interpretation belongs in the product.

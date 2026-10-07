# Offline browser acceptance

The browser passed real hosted execution and independent visual review at `51b4132920f3e02bb09b2287ac9681899a023aff`, [run37592459664](https://github.com/Masanori-Spec/off-day-kit/actions/runs/37592459664). [Exact evidence](BROWSER-VERIFICATION.md) identifies the shipped package and actual output. Delivery is GitHub source plus the downloadable offline ZIP. No web hosting, account or remote storage is needed.

## Data boundary

The exact six shipped files are `index.html`, `web/core.js`, `web/worker-source.js`, `web/app.js`, `web/style.css` and `README-OFFLINE.txt`. The verifier checks every ZIP member and source hash before extracting the actual package for browser use. The app uses only explicitly selected `.gan`/recipe bytes; it has no network or filesystem traversal code, runtime dependencies, persistence or content execution. A restrictive local-compatible CSP blocks connections, objects, forms and base URLs. Names and input text use DOM text nodes.

The JavaScript byte parser is separate from the Python implementation. Parsing and preview computation run in disposable workers, so Clear and newer settings can terminate them. The worker source bundle is verified as exactly our core plus worker handler; it uses a local Blob for file-protocol compatibility, without network loading. Both enforce the documented profile and resource caps; default browser imports select no IDs. Every project and recipe import clears selections. A receipt from an invalidated project, selection, recipe or setting is unavailable for download. Late file reads, late recipe reads and disposable parsing/preview workers cannot restore stale output. Same-file reselection is supported by clearing the input element after snapshotting its File list.

Resource search/pagination retains explicit selections by ID and limits mounted resource controls to 100. A single selection is capped at 100 resources; the date review shows 60 rows per page and exposes every row by navigation. The complete JSON receipt includes all candidate/resource rows, even across pages. Print intentionally contains the current review page and overall summary; it does not claim to print unseen pages. Inputs remain unmodified, output is a newly downloaded file, and no-op output is byte-identical.

## Actual producer and consumer

The hosted test uses a real keyboard-activated browser file chooser and the genuine GUI-authored native fixture. It selects A/B and the literal fortnight recipe, previews eight resource/date rows, acknowledges and downloads the real `.gan`, review JSON and recipe. Repeated output and reapplication are downloaded and compared byte-for-byte. An actual shifted-anchor browser download supplies one negative control.

The unchanged Python implementation checks complete output/receipt parity independently. The separate handwritten date oracle checks the exact five additions, all original/outside bytes, resource identity, exclusive ends, exclusions and covered values. The official GanttProject 3.4.3396 Beta VI GUI opens the actual browser download, checks every A/B/C Days off row, displays January and February, saves to a fresh file, closes and reopens in a fresh process, checks all rows again and saves another new file. Complete task/resource/calendar data and seven intervals must persist. The original input and browser download hashes remain unchanged. Vendor/runtime hashes must match after execution.

## UI scenarios and visuals

Required cases include Japanese default, English switching, keyboard skip/chooser/acknowledgment, explicit and repeated resource selection, deterministic downloads, no-op, recipe import/export without IDs, invalidation after edits, empty input changes, newer file winning over a delayed read, clear during a pending read, form edits during recipe reads, and edits during a worker preview. Worker startup failures and queued results from older revisions must fail safely; displayed diagnostics are bounded. A 200% root-text mobile check exercises enlarged controls and confirms no page-wide horizontal overflow. Explicit empty-change tests do not claim OS file-picker cancellation.

Rejections include unsupported versions and years, non-Monday anchors, too-long windows, wrong file types, multiple files, byte-size limits before reads, oversized/resource-bearing/duplicate-key recipes, DTDs, duplicate IDs, dangling references and excessive selections. Hostile-looking labels and links must remain literal, with no HTTP requests or page/console errors. Unit tests cover deeper parser/reference/decompression-free byte boundaries independently.

Retain JA/EN desktop and 390-pixel mobile screenshots. Assert no page-wide horizontal overflow; scroll the review table and verify its full rightmost column is within the visible container. Retain JA/EN print screenshots and actual PDFs with all eight fixture rows and hashes, then inspect the rendered PDF pages. Both actual Chromium launches must keep their sandbox enabled. No local heavy GUI execution or security workaround is part of this workflow.

The acceptance scope is finite native days-off records and their display. Scheduling, leveling, optimization and other native versions are not established.

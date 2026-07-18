# Sharp Frames Application Audit

Date: 2026-07-14
Baseline: `develop` at `e712afa`
Remediation branch: `codex/deep-application-review`

## Scope

This audit covered the direct CLI, Textual UI, extraction and saving pipelines,
all three selection methods, multi-video and image-directory inputs, sharpness
analysis, packaging, dependency health, cancellation, and platform support.

The audit combined source inspection with focused behavior probes, synthetic
FFmpeg runs, package builds, static analysis, and the full test suite.

## Remediation Outcome

All Critical and High findings in this audit are resolved on
`codex/deep-application-review`.

| Finding | Resolution |
| --- | --- |
| C1 | All non-interactive save paths now fail closed on unapproved output conflicts. |
| C2 | Modern and direct-CLI directory saves transcode to the requested format and deterministically disambiguate colliding stems. |
| H1–H5 | CLI, TUI, previews, and compatibility entry points share canonical, source-aware selection implementations with exact previews. |
| H6 | FFmpeg output is continuously drained; completion requires a clean exit; failure, timeout, and cancellation reject partial output. |
| H7 | Cancellation reaches active extraction and analysis, and temporary directories are cleaned on every tested exit path. |
| H8 | The declared and tested support floor is Python 3.10. |
| H9 | Image-only processing skips video-tool checks; video checks require FFmpeg and FFprobe; HDR and platform requirements are documented. |
| H10 | CLI, TUI, validation, extraction, and documentation use one shared media-format contract. |
| H11 | FFprobe failures preserve actionable stderr and can no longer be masked by a local import error. |
| H12 | The maintained suite is green, dependencies no longer install a stale app revision, and CI covers four Python versions on three operating systems. |

Final local verification used clean environments with current dependency
resolution on Python 3.10, 3.11, 3.12, and 3.13. Each environment passed all
307 tests. The runtime regressions include real synthetic FFmpeg extraction,
nonzero partial output, overall timeout, cancellation, temporary-directory
cleanup, image-only dependency checks, format discovery, and OS-specific
guidance. The sdist and wheel build cleanly and advertise Python 3.10+ with the
expected runtime dependencies and license metadata. A final dependency audit
reported no known vulnerabilities in the resolved environment.

## Baseline Verification

- Wheel build succeeded.
- A synthetic video completed end-to-end extraction with the expected frame
  count.
- Color-space tests passed, including real FFmpeg Display P3, BT.2020 SDR, and
  HDR filter execution.
- The full suite reported 220 passing and 71 failing tests.
- No GitHub Actions workflow was configured.
- Two Dependabot findings were open: a medium-severity pytest temporary
  directory issue and a low-severity Pygments ReDoS issue.

## Critical Findings

### C1. Non-interactive saving bypasses overwrite protection

When the Textual path uses `FrameSaver(show_progress=False)`, an existing
output directory only produces a warning when `force_overwrite` is false. The
save then proceeds and overwrites matching output names. This contradicts the
UI choice and creates a direct data-loss risk.

Required outcome: existing output files must remain untouched unless overwrite
was explicitly authorized. Non-interactive conflicts must fail safely and
report the conflicting paths.

### C2. Image-directory output can have false extensions and collisions

For directory inputs without resizing, the saver constructs a filename using
the configured output format but copies the source bytes unchanged. A PNG can
therefore be written as `image.jpg` while retaining PNG content. Files with the
same stem but different extensions can map to the same destination and
overwrite one another.

Required outcome: byte copies preserve their real format, requested format
changes perform an actual transcode, and every selected input gets a unique,
deterministic destination.

## High Findings

### H1. Best-N is behaviorally different between CLI and TUI

The Textual `FrameSelector` ranks by sharpness only; its advertised
distribution weighting is absent. The direct CLI uses a separate segmented
implementation. Users can receive materially different selections from the
same frames and parameters depending on entry point.

Required outcome: one canonical algorithm and identical results across CLI,
TUI, preview, and tests. Sharpness and temporal distribution must be normalized
to comparable scales before weighting.

### H2. Best-N buffer semantics disagree with the preview

The preview treats `min_buffer` as the number of intervening frames, while
selection accepts an index distance equal to `min_buffer`. This creates count
and guarantee mismatches.

Required outcome: define `min_buffer` as intervening frames, require an index
distance of at least `min_buffer + 1`, and calculate preview counts using the
same implementation as execution.

### H3. Outlier-removal endpoints contradict each other

At sensitivity 100, the Textual implementation removes every frame, the CLI
keeps every frame, and the preview estimates that roughly 60 percent remain.
At sensitivity 0, execution keeps every frame while preview still removes a
small percentage.

Required outcome: consistent monotonic semantics, with 0 disabling removal and
100 representing maximum useful aggressiveness without a hard-coded all/none
special case.

### H4. Outlier preview is not an actual preview

The Textual preview uses a fixed sensitivity-to-removal-rate lookup and ignores
the scores and window size. It can disagree with execution and show an
incorrect save count and completion message.

Required outcome: exact preview counts from the canonical selection algorithm.

### H5. Video-directory selection crosses source boundaries

All extracted frames are concatenated. Best-N spacing, batched groups, and
outlier neighborhoods can cross from one source video to another. Global
sharpness ranking can also starve videos with lower-resolution or lower-contrast
content.

Required outcome: group-aware selection. Batches, neighborhoods, and spacing
reset at source boundaries; Best-N allocates a deterministic and fair quota
across sources.

### H6. FFmpeg extraction can silently accept incomplete output

The modern extractor pipes stderr without continuously draining it, terminates
after ten seconds without a newly observed file, may terminate when its frame
estimate is reached, and accepts any extraction that produced at least ten
files even if FFmpeg failed or was killed.

Required outcome: continuously consume process output, support explicit
cancellation and a real overall timeout, wait for a successful FFmpeg exit,
and never infer success from an arbitrary minimum file count.

### H7. Cancellation does not stop extraction and can leak temporary files

`TUIProcessor.cancel_processing()` only signals sharpness analysis. Active
FFmpeg extraction continues in a worker thread. Cleanup attempts before
`current_result` is assigned do not know the temporary directory and therefore
leak it on cancellation or intermediate errors.

Required outcome: cancellation propagates to the extractor and process, every
temporary directory has explicit ownership, and cleanup runs on all exit paths.

### H8. Declared Python support is inaccurate

Packaging advertises Python 3.7 and 3.8, while runtime code uses built-in
generic annotations and executor APIs requiring Python 3.9 behavior.

Required outcome: either restore compatibility or declare and test the real
minimum. The implemented correction is Python 3.10+ with matching classifiers
and CI. Python 3.9 is end-of-life, and the security-fixed pytest 9 line also
requires Python 3.10+.

### H9. Platform dependency checks and documentation disagree with reality

The Textual validation path requires FFmpeg even for image-only input. Modern
video processing requires FFprobe although metadata describes it as optional.
HDR conversion requires an FFmpeg build with `zscale`/libzimg but this is not
documented.

Required outcome: dependency checks are input-type-specific, FFprobe and
zscale requirements are accurately communicated, and errors include
platform-appropriate remediation.

### H10. Supported formats differ between entry points

The README, validators, single-file processing, image extractor, and video
directory scanner use different extension sets. Validated WebP or M4V inputs
can later be ignored.

Required outcome: shared format constants used by detection, validation,
extraction, help, and documentation.

### H11. FFprobe errors are masked

`FrameExtractor._get_video_info()` imports `json` inside its try block and
references it in an exception clause. Failures before that import can surface
as `UnboundLocalError` instead of the real FFprobe error.

Required outcome: preserve the original failure type and actionable stderr.

### H12. Test and dependency baselines are not release-grade

The suite had 71 failures, many encoding obsolete or contradictory selection
semantics. `requirements.txt` mixes runtime, documentation, and test packages
and includes an editable install pinned to an old application commit.
`tests/requirements.txt` omits Pillow even though tests import it. With no CI,
these failures cannot prevent regressions.

Required outcome: one truthful green suite, separated dependency manifests,
and CI across supported Python and operating-system versions.

## Deferred Selection-Quality Roadmap

The following quality improvements are important but are deferred until the
Critical and High correctness and safety defects above are closed.

### Implementation status (2026-07-15)

| Finding | Current status |
| --- | --- |
| Q1 | Baseline implemented. Modern and direct-CLI analysis now normalize the long edge to 512 pixels before scoring. The synthetic cross-resolution ratio fell from 4.0 to approximately 1.39, guarded by a `< 1.5` regression threshold. A fine-detail probe improved sharp/mild-blur separation from approximately 1.17× at 256 pixels to 1.56× at 512 pixels. |
| Q2 | Baseline implemented. A 5×5 Gaussian denoise pass now feeds an equal-weight, log-normalized Laplacian/Tenengrad score. In the deterministic noise probe, the clean edge scores about 4× above the noisy blurred image. Real labeled-corpus validation remains under Q6. |
| Q3 | Natural, case-insensitive numbered ordering is implemented for image directories, video directories, extracted frame discovery, and the direct CLI. Optional EXIF chronology remains a future enhancement. |
| Q4 | Local outlier comparison now uses the neighbor median and median absolute deviation with a stable zero-MAD fallback. A single extreme high score no longer masks a real blurry frame. Scene-aware windows remain future work. |
| Q5 | Resolved for the modern pipeline. Failed reads are excluded instead of receiving score zero; all-failed inputs stop safely; structured counts and paths are added to metadata; and the Textual selection screen reports exclusions. |
| Q6 | In progress. Deterministic probes now track resolution invariance, noise resistance, chronology, unreadable exclusion, and synthetic outlier precision/recall. A representative real-media corpus, duplicate metric, and cross-camera baseline remain outstanding. |
| Q7 | In progress. The chart now scrolls horizontally across the full timeline with guaranteed bar separation. Source-boundary markers and per-frame selection explanations remain outstanding. |

The focus-score metadata records
`normalized_laplacian_tenengrad_v1` and the 512-pixel analysis scale so future
quality comparisons can distinguish algorithm versions.

### Q1. Normalize analysis resolution

Laplacian variance is strongly resolution-dependent. The same synthetic edge
scored approximately 2032 at 128 pixels and 508 at 512 pixels under the current
half-size analysis. Normalize every analysis image to a defined scale before
comparing focus scores, especially across image directories and source videos.

### Q2. Reduce sensitivity to noise and compression

Noise can score as high-frequency detail. In a focused probe, a blurred image
scored about 66, while adding noise raised it to about 820. Add light denoising
and evaluate a combined focus metric such as normalized Laplacian variance plus
Tenengrad. Validate against a labeled sharp/blurred corpus.

### Q3. Use natural and metadata-aware ordering

Lexicographic ordering places `frame10` before `frame2` and is case-sensitive
across platforms. Use natural sorting for numbered sequences and consider EXIF
capture time where appropriate. Temporal methods must operate on the intended
chronology.

### Q4. Make outlier statistics robust

The global min/max range is distorted by a single extreme noisy or corrupt
frame. Prefer robust scale estimates such as median/MAD or percentile ranges,
and consider scene boundaries so legitimate softer scenes are not compared to
unrelated high-detail scenes.

### Q5. Treat unreadable images explicitly

The modern analyzer converts failed reads into score zero while keeping the
frame eligible for later saving. Exclude failed inputs from selection, report
them separately, and expose partial-success information in metadata and UI.

### Q6. Define selection quality metrics

Build a repeatable evaluation corpus covering motion blur, defocus, noise,
compression, exposure changes, animation, scene cuts, mixed resolution, HDR,
and multi-camera directories. Track precision/recall for rejected blurry
frames, coverage uniformity, duplicate rate, and per-source representation.

### Q7. Improve visualization and explainability

The Textual chart only shows the first portion of long inputs. Downsample the
whole timeline, show source boundaries, and explain why a frame was selected or
rejected. This makes parameter tuning and regression review substantially more
trustworthy.

## Lower-Priority Engineering Improvements

- Remove dead and duplicated legacy UI/preview implementations after migration.
- Replace broad `except`/silent-pass blocks with typed errors and structured
  logging.
- Avoid import-time FFmpeg subprocess checks, especially for image-only use.
- Use `opencv-python-headless` as an optional server/CLI installation extra.
- Add deterministic metadata schemas and atomic metadata writes.
- Add performance benchmarks for large frame sets and long videos.
- Add linting, type checking, security scanning, and package smoke tests to CI.

## Exit Criteria for This Remediation

All Critical and High findings are closed only when:

1. Each issue has a regression test that failed before the fix.
2. CLI and TUI selection results agree for equivalent input and parameters.
3. All save paths preserve data and honor conflict policy.
4. Synthetic FFmpeg success, failure, timeout, and cancellation paths pass.
5. Image-only processing succeeds without FFmpeg.
6. Supported format and Python-version declarations match tested behavior.
7. The complete maintained test suite is green.
8. A final review finds no remaining Critical or High regression.

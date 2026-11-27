# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.4] - 2026-11-27

### Changed
- The "not valid UTF-8" error now says how to fix it (save as UTF-8, `iconv`) and names a UTF-16 byte order mark when the file has one. English and Korean.
- README evaluation tables updated to the latest measurement.

## [0.1.3] - 2026-11-27

### Changed
- Evaluation set: the segment-start task (`task-sms-split-points`) is replaced by `task-kr-lms-notice`, a long Korean LMS notice with three Hangul syllables outside KS X 1001 that Python's `euc_kr` and `cp949` codecs accept; the answer is each character with its position. The Korean task prompts now ask the way a user does ("국내 통신사") instead of naming the strict EUC-KR rule, and the graders accept more wordings of the same exact values (`≥2 segments`, `more than 1 segment`, "발송이 안 되는 것").
- `SKILL.md`: report each total next to the script's own label, and name every Korean culprit with its `index` even when Python's codecs accept the text. No script change.
- Package, plugin metadata and the script's `--version` report 0.1.3.

### Known limitations
- The task case `task-kr-lms-notice` is already solved without the skill (baseline 1.0, delta 0.0); it stays as a regression case.
- `SKILL.md` step 5 calls `after` the cleaned text; in `fix-sms --json` the cleaned text is `candidate` and `after` is its measurement.
- `SKILL.md` step 4 mentions `kr_class`, which only `--jsonl` items carry; for a single text `value: null` means the text cannot be sent.

## [0.1.2] - 2026-11-24

### Changed
- README (English and Korean): the evaluation table is updated to the latest measurement; see the table in the README for the numbers.
- The script's `--version` now reports `0.1.2`, matching the package and plugin metadata. No other skill or script change.

## [0.1.1] - 2026-11-24

### Changed
- README (English and Korean): the evaluation table now shows the measured values for the final skill (see the README table).
- README: `uv run pytest` shows the pass count, the `--file` trailing-newline behaviour is explained next to the 741-character example, and the "no files written" note mentions `__pycache__`.
- CI: each job writes a diagnostics summary (step outcomes and the pytest log tail).
- Package and plugin metadata version is 0.1.1; the skill and script code are unchanged from 0.1.0 (the script's `--version` string was not updated in this release; see [Unreleased]).

## [0.1.0] - 2026-11-23

### Added
- `charfit.py count`, `check` and `fix-sms` commands.
- Profiles `sms`, `sms:N`, `x-post`, `kr-sms`, `kr-lms`, `utf16:N`, `utf8:N`, `chars:N`.
- SMS segment counting that never splits a two-unit character (GSM-7 extension or UCS-2 emoji) across segments; `boundary_extra` reports the segments this adds over `units / per_segment`.
- `segment_starts` in SMS results: the 0-based code point index where each segment starts (character positions, not multiples of 153 or 67), shown as `part N: index I` in the human output.
- `--jsonl PATH` for `check` and `fix-sms`: one `{"id", "text"}` object per line, per-item results and `totals` (billed segments, GSM-7/UCS-2 and multi-segment item counts, Korean `SMS`/`LMS`/`OVER`/`FAIL` counts, segments before and after a GSM-7 cleanup, items still UCS-2), so a template file is measured in one call without adding up by hand.
- GSM-7 accent table in `references/rules.md` (`é` is GSM-7, `á` is not), checked against the `gsm0338` 1.1.0 codec.
- X weighted length (`x-post`) as an approximation of X's published rules, cross-checked against the twitter-text 3.1.0 library: country-code domains count as links (so `setup.py` and `README.md` weigh 23), emoji sequences count as one emoji (2), a bare `©` `®` weighs 1, NFD text is counted after NFC; `x_emoji` and `x_nfc_code_points` in the check results. Emoji sequence weights follow twitter-text 3.1.0 and are not guaranteed for every X client.
- Strict EUC-KR byte counting that rejects Hangul outside KS X 1001 (Python's `euc_kr` codec does not), with `--kr-codec cp949` as an option.
- English and Korean output (`--lang`, `CHARFIT_LANG`, locale variables); JSON output is identical in both languages.
- `SKILL.md`, `references/rules.md`, an evaluation set and the Claude Code plugin manifests. The task cases measure template batches and a long newsletter (billed segment totals, segment start positions, totals after a GSM-7 cleanup, strict EUC-KR classes); `tests/naive_baselines.py` keeps nine shortcut implementations that the graders must reject, including hand-written GSM-7 tables that miss the section sign or the Greek capitals.
- `SKILL.md` tells the agent to report a failed or unusable script run instead of falling back to a count of its own; `references/rules.md` lists the Greek capitals `Δ Φ Γ Λ Ω Π Ψ Σ Θ Ξ` as GSM-7.

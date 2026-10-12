# Changelog

All notable changes to this project are listed here, newest first. Entries are taken from the git history; commit hashes are given in parentheses.

## Unreleased

Changes on the `haiku/ci` branch, not yet merged to `main`.

### Added

- GitHub Actions workflow that runs the offline test suite on push and pull request, on Python 3.9 and 3.13 (`.github/workflows/test.yml`).
- `--dry-run` flag that prints the message the next send would deliver without sending it or changing the state file.
- `--list-content` flag that prints the number of entries in each section of `content.json` and the total.
- `LOG_LEVEL` environment variable (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; default `INFO`), applied through the standard `logging` module while keeping the Mountain Time timestamp format.
- README sections for the dry run, content summary, log level and CI workflow.

### Changed

- `.gitignore` now also ignores `sent_state.tmp`, `venv/` and `.pytest_cache/`.

## 2026-10-12

### Added

- `tzdata` requirement so Windows can look up the Mountain Time zone (1900fbf).
- Validation of `PHONE_NUMBER`: it must contain digits only, so `+`, spaces and dashes are rejected (d4019d0).
- Validation of `content.json`: the top level must be an object (9392206), definition and question records must have their required fields (1069fa1), and a file with no entries is rejected (d053d4c).
- The program exits with status 1 when the content cannot be loaded (e976a74).
- Slot dispatch was moved out of the scheduler loop into its own function (a80be6e).

### Changed

- State files are written atomically, so an interrupted save keeps the previous state (8ff7a2a).
- State files that are not JSON objects are treated as empty (175c4cc), and missing or mistyped keys are filled with defaults (45b3350).
- The failed-send log now states that the slot is not marked and will not be retried that hour (b08b6ba).
- Type hints were added to the function signatures in `main.py` (5387aef).

### Tests

- Content loading for every category and for missing sections (99c5bc2).
- Selection recycling and the 320-character message limit (a73b760).
- Delivery recovery after a transient failure and the missing API key case (a5978ad).
- State defaults, the save-failure warning and the same-day no-op (b6f203f).
- Slot dispatch (a80be6e).

### Documentation

- Public helpers in `main.py` are documented (1790c51).
- README gained a usage section (b3d9b7e), a description of the content file format and validation rules (7ddb97d), and a description of the send schedule, state file and retry behavior (66e70d2).

## 2026-10-01

### Added

- Published a sanitized source snapshot of the personal project, with credentials, delivery state and personal configuration removed (97d9d1a).

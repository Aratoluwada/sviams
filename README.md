# SVIAMS (AutoGate ID)

Smart Vehicle Identification and Access Management System. A handheld gate checker for FUNAAB (MTE 403): the gateman captures a vehicle plate, taps an NFC card, and the Raspberry Pi checks both against a local database and logs the result.

Built with Flask and SQLite on a Raspberry Pi 4. Work in progress.

## Layout

| Path | What it is | Role |
| --- | --- | --- |
| `camera.py`, `anpr.py` | Camera and plate reading | A |
| `nfc.py`, `db.py`, `logic.py` | Card reader, database, entry/exit rules | B |
| `app.py`, `config.py`, `mock.py`, `templates/`, `static/` | Flask routes, touchscreen and admin pages | C |
| `tests/` | Tests | all |
| `instance/` | Local database (not committed) | |

Each person works on their own branch, for example `feature/nfc-logic`, and merges through review.

# Study Tip Sender

A small personal Python scheduling project that sends study reminders through Resend to a configurable email-to-SMS gateway address.

## What the code demonstrates

DST-aware scheduling with `zoneinfo`, persistent delivery-slot state, randomized daily content selection, bounded retries with exponential backoff, and recovery from malformed state files.

## Run locally

Use Python 3.9+, install `requirements.txt`, and set `RESEND_API_KEY`, `PHONE_NUMBER` and optionally `FROM_ADDRESS` in your environment. The `.env.example` file documents them; the program does not automatically load dotenv files. Run `python main.py` only when you intend to send messages.

The included content is a small generic sample, not exported class notes. Credentials, personal phone defaults and prior delivery state have been removed from this public copy. The code uses T-Mobile's email-to-SMS address format; current carrier availability and delivery behavior have not been verified, so this is a scheduling/delivery prototype rather than a guaranteed working SMS service.

## Usage

Install the dependencies with `python -m pip install -r requirements.txt`, which includes `tzdata` for Windows timezone support. Then set the environment variables and start the scheduler in the foreground:

```
export RESEND_API_KEY=re_your_key      # PowerShell: $env:RESEND_API_KEY = "re_your_key"
export PHONE_NUMBER=15555550100
python main.py
```

`PHONE_NUMBER` must contain digits only, including the country code, with no `+`, spaces or dashes. `FROM_ADDRESS` is optional and defaults to the Resend test sender. Press Ctrl+C to stop; the process logs the shutdown and exits. The sender refuses to start, with a message, if either required variable is missing or the phone number is malformed.

### Dry run

`python main.py --dry-run` picks the message the next send would deliver and prints it with the recipient address, then exits. Nothing is sent, and `sent_state.json` is neither created nor changed, so it is safe to run while the scheduler is active. A dry run needs `PHONE_NUMBER` but not `RESEND_API_KEY`.

### Content summary

`python main.py --list-content` prints the source file path and the number of entries in each section of `content.json`, followed by the total number of items. It does not need `PHONE_NUMBER` or `RESEND_API_KEY`, does not touch the state file, and exits with status 1 if the file is missing or invalid. `--dry-run` and `--list-content` cannot be combined.

### Log level

Log lines are written to stdout with a Mountain Time timestamp. Set `LOG_LEVEL` to `DEBUG`, `INFO` (the default), `WARNING`, `ERROR` or `CRITICAL` to choose how much is shown; the name is case-insensitive. At `DEBUG`, each minute that is not a send slot is logged as `No send due at HH:MM`. Failed send attempts are warnings, and an unknown value makes the program exit with a message:

```
export LOG_LEVEL=WARNING      # PowerShell: $env:LOG_LEVEL = "WARNING"
```

## Content file

`content.json` in the project directory supplies the messages. Every section is optional, but the file must contain at least one entry:

```json
{
  "tips": ["Explain a concept in your own words before checking your notes."],
  "concepts": ["A mutex protects a critical section shared by multiple threads."],
  "definitions": [{"term": "Deadlock", "definition": "Tasks wait indefinitely for resources held by one another."}],
  "questions": [{"q": "Why use persistent scheduler state?", "a": "To avoid repeating a completed delivery after a restart."}]
}
```

Each item is sent as one text with a prefix for its kind (`Tip:`, `Concept:`, `Def:` or `Q:`). Texts longer than 320 characters are cut to 317 characters and end with `...`.

Validation runs at startup. A file that is not a JSON object, a section that is not a list, a blank string, or a definition or question missing a field stops the sender with a message naming the bad entry, and the process exits with status 1.

## Schedule, state and retries

The sender checks the clock every minute. It sends at minute 0 of each hour listed in `SEND_HOURS` (08:00, 10:00, 12:00 and so on through 22:00, Mountain Time), so the schedule is every two hours. Each slot sends one randomly chosen item that has not yet been sent that day. When every item has been used, the pool starts again.

A send is attempted up to three times, waiting 5 s and then 10 s between attempts. If all attempts fail, the slot is not marked as sent and is not retried during that hour.

Delivered slots and the item indices used are saved to `sent_state.json` beside `main.py`. This keeps a restart within the same hour from sending a duplicate. The file is replaced atomically, and a missing or unreadable file is treated as an empty day. Delete `sent_state.json` to start the day over.

## Offline validation

Run `python -m unittest discover -s tests -v`. Tests stub the delivery SDK and do not send messages. The public-copy cleanup, sample content and offline tests were prepared with AI assistance.

The GitHub Actions workflow in `.github/workflows/test.yml` runs the same command on every push and pull request, on Python 3.9 and 3.13, after installing `requirements.txt`.

# Study Tip Sender

A small personal Python scheduling project that sends study reminders through Resend to a configurable email-to-SMS gateway address.

## What the code demonstrates

DST-aware scheduling with `zoneinfo`, persistent delivery-slot state, randomized daily content selection, bounded retries with exponential backoff, and recovery from malformed state files.

## Run locally

Use Python 3.9+, install `requirements.txt`, and set `RESEND_API_KEY`, `PHONE_NUMBER` and optionally `FROM_ADDRESS` in your environment. The `.env.example` file documents them; the program does not automatically load dotenv files. Run `python main.py` only when you intend to send messages.

The included content is a small generic sample, not exported class notes. Credentials, personal phone defaults and prior delivery state have been removed from this public copy. The code uses T-Mobile's email-to-SMS address format; current carrier availability and delivery behavior have not been verified, so this is a scheduling/delivery prototype rather than a guaranteed working SMS service.

## Offline validation

Run `python -m unittest discover -s tests -v`. Tests stub the delivery SDK and do not send messages. The public-copy cleanup, sample content and offline tests were prepared with AI assistance.

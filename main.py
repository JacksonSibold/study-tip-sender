"""
Study Tip SMS Sender
Sends periodic CS study tips via T-Mobile email-to-SMS gateway using Resend.
"""

import os
import json
import time
import random
import traceback
from datetime import datetime, date
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

import resend


# ---------- Config ----------
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
TO_ADDRESS = f"{PHONE_NUMBER}@tmomail.net"
FROM_ADDRESS = os.getenv("FROM_ADDRESS", "Study Tips <onboarding@resend.dev>")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

MT = ZoneInfo("America/Denver")
SEND_HOURS = {8, 10, 12, 14, 16, 18, 20, 22}

CONTENT_FILE = Path(__file__).parent / "content.json"
STATE_FILE = Path(__file__).parent / "sent_state.json"

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 5


# ---------- Logging ----------
def log(msg: str) -> None:
    ts = datetime.now(MT).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{ts}] {msg}", flush=True)


# ---------- Content ----------
def load_content() -> list:
    with CONTENT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for tip in data.get("tips", []):
        items.append(f"Tip: {tip}")
    for c in data.get("concepts", []):
        items.append(f"Concept: {c}")
    for d in data.get("definitions", []):
        items.append(f"Def: {d['term']} - {d['definition']}")
    for q in data.get("questions", []):
        items.append(f"Q: {q['q']} A: {q['a']}")
    return items


# ---------- State ----------
def _empty_state() -> dict:
    return {"date": "", "sent_indices": [], "sent_slots": []}


def _normalize_state(data: object) -> dict:
    """Return a state dict with every expected key present and well-typed."""
    state = _empty_state()
    if not isinstance(data, dict):
        return state
    if isinstance(data.get("date"), str):
        state["date"] = data["date"]
    for key in ("sent_indices", "sent_slots"):
        if isinstance(data.get(key), list):
            state[key] = data[key]
    return state


def load_state() -> dict:
    if not STATE_FILE.exists():
        return _empty_state()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_state()
    return _normalize_state(data)


def save_state(state: dict) -> None:
    # Write to a temp file and swap it in, so an interrupted write never
    # leaves a truncated state file behind.
    tmp_file = STATE_FILE.with_suffix(".tmp")
    try:
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp_file, STATE_FILE)
    except Exception as e:
        log(f"WARN: failed to save state: {e}")
        try:
            tmp_file.unlink(missing_ok=True)
        except OSError:
            pass


def reset_state_if_new_day(state: dict, today_str: str) -> dict:
    if state.get("date") != today_str:
        state = {"date": today_str, "sent_indices": [], "sent_slots": []}
        save_state(state)
    return state


# ---------- Selection ----------
def pick_message(content: list, state: dict) -> tuple:
    used = set(state.get("sent_indices", []))
    available = [i for i in range(len(content)) if i not in used]
    if not available:
        # All used today; reset pool but keep slot tracking
        log("All content used today; recycling pool.")
        state["sent_indices"] = []
        available = list(range(len(content)))
    idx = random.choice(available)
    msg = content[idx]
    if len(msg) > 320:
        msg = msg[:317] + "..."
    return idx, msg


# ---------- Sending ----------
def send_sms(message: str) -> bool:
    if not RESEND_API_KEY:
        log("ERROR: RESEND_API_KEY not set.")
        return False
    resend.api_key = RESEND_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            params = {
                "from": FROM_ADDRESS,
                "to": [TO_ADDRESS],
                "subject": "",
                "text": message,
            }
            resp = resend.Emails.send(params)
            log(f"Sent (attempt {attempt}): id={resp.get('id') if isinstance(resp, dict) else resp}")
            return True
        except Exception as e:
            wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            log(f"Send failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                log(f"Retrying in {wait}s...")
                time.sleep(wait)
    log("ERROR: All retries exhausted.")
    return False


# ---------- Scheduler ----------
def run() -> None:
    if not PHONE_NUMBER or not RESEND_API_KEY:
        raise SystemExit("Set PHONE_NUMBER and RESEND_API_KEY before running the sender.")
    log("Study Tip Sender starting.")
    log(f"Recipient: {TO_ADDRESS}")
    log(f"Send hours (MT): {sorted(SEND_HOURS)}")

    try:
        content = load_content()
        log(f"Loaded {len(content)} content items.")
    except Exception as e:
        log(f"FATAL: cannot load content: {e}")
        return

    state = load_state()

    while True:
        try:
            now = datetime.now(MT)
            today_str = now.strftime("%Y-%m-%d")
            state = reset_state_if_new_day(state, today_str)

            slot_key = f"{today_str} {now.hour:02d}"
            if (
                now.hour in SEND_HOURS
                and now.minute == 0
                and slot_key not in state.get("sent_slots", [])
            ):
                log(f"Trigger slot {slot_key}")
                idx, msg = pick_message(content, state)
                ok = send_sms(msg)
                if ok:
                    state["sent_indices"].append(idx)
                    state["sent_slots"].append(slot_key)
                    save_state(state)
                else:
                    log("Send unsuccessful; will not mark slot, retry next minute window.")

            # Sleep until next minute boundary
            sleep_s = 60 - datetime.now(MT).second
            time.sleep(max(1, sleep_s))
        except KeyboardInterrupt:
            log("Shutdown requested. Exiting.")
            return
        except Exception as e:
            log(f"Loop error: {e}")
            traceback.print_exc()
            time.sleep(30)


if __name__ == "__main__":
    run()

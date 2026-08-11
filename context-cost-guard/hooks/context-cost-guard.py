#!/usr/bin/env python3
"""
Warn before a turn that will cost far more than it looks like it should.

Every turn re-sends the whole conversation. While the prompt cache is warm that
is cheap — reads are billed at roughly a tenth of a normal input token. Once the
cache expires the same context has to be written back at roughly double, so the
identical question can cost ~20x more purely because of when it was asked.

This hook runs on UserPromptSubmit, before the request goes out. When the
conversation is large *and* the cache has almost certainly expired, it blocks
once and explains the two cheap ways out. Re-sending within SNOOZE_SECONDS goes
through untouched, so it can never trap you.
"""

import json
import os
import sys
from datetime import datetime, timezone

IDLE_MINUTES = 55
BIG_CONTEXT = 60_000
SNOOZE_SECONDS = 300

STATE_PATH = os.path.expanduser("~/.claude/.context-cost-guard.json")


def read_transcript(path):
    """Return (context_tokens, last_assistant_timestamp) from the last usage record."""
    context, stamp = 0, None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            usage = (record.get("message") or {}).get("usage")
            if not usage:
                continue
            context = (
                usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
            )
            stamp = record.get("timestamp") or stamp
    return context, stamp


def idle_minutes(stamp):
    if not stamp:
        return 0.0
    try:
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (datetime.now(timezone.utc) - then).total_seconds() / 60.0


def snoozed(session_id, now):
    try:
        with open(STATE_PATH, encoding="utf-8") as handle:
            return now - json.load(handle).get(session_id, 0) < SNOOZE_SECONDS
    except (OSError, ValueError):
        return False


def snooze(session_id, now):
    try:
        with open(STATE_PATH, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    state = {k: v for k, v in state.items() if now - v < 86_400}
    state[session_id] = now
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except OSError:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return

    path = payload.get("transcript_path")
    session_id = payload.get("session_id") or "unknown"
    if not path or not os.path.exists(path):
        return

    try:
        context, stamp = read_transcript(path)
    except OSError:
        return

    idle = idle_minutes(stamp)
    if context < BIG_CONTEXT or idle < IDLE_MINUTES:
        return

    now = datetime.now(timezone.utc).timestamp()
    if snoozed(session_id, now):
        return
    snooze(session_id, now)

    warm = context * 0.1
    cold = context * 2
    # Claude Code's block card collapses ASCII \n to spaces (CSS white-space:
    # normal). U+2028 LINE SEPARATOR is a forced break in that UI.
    br = "\u2028"
    message = br.join([
        "This turn will cost much more than it looks.",
        f"Conversation context : {context:,} tokens",
        f"Idle                 : {idle:.0f} min  (cache likely expired after 60 min)",
        f"Est. turn cost       : ~{cold:,.0f} vs ~{warm:,.0f} token-equivalents",
        "",
        "/clear    new topic — cheapest, start from zero",
        "/compact  same thread, summarized",
        "resend    send the same prompt again to continue anyway",
    ])

    print(json.dumps({
        "decision": "block",
        "reason": message,
        "systemMessage": message,
    }))


if __name__ == "__main__":
    main()

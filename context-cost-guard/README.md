# context-cost-guard

A Claude Code plugin that **blocks once** before an expensive cold-cache turn — when your conversation is large *and* you have been idle long enough that the prompt cache has likely expired.

Claude’s Messages API is **stateless**: every turn resends the full conversation. Warm prompt-cache reads bill around **0.1×** input; cold cache writes bill around **2×** (1h TTL) or **1.25×** (5m TTL). The same prompt can cost ~**20×** more after a lunch break on a large session.

This plugin is the **runtime guard**. Pair it with scoping `~/.claude/rules/` (`paths:` frontmatter) and a thin `CLAUDE.md` to cut always-on context.

Blog: `https://<site>/blog/reduce-claude-code-token-usage` (placeholder — replace with the published URL)

---

## Install

Requires [Claude Code](https://code.claude.com/docs/en/overview) and `python3` on your `PATH`.

In Claude Code:

```text
/plugin marketplace add JanBancerewicz/context-cost-guard
/plugin install context-cost-guard@context-cost-guard
```

Then **restart Claude Code** (or run `/reload-plugins`). Hooks load at session start; a restart is the reliable way to activate them.

You do **not** need to edit `~/.claude/settings.json`. The plugin merges its `UserPromptSubmit` hook with any hooks you already have.

### Local / development install

From a clone of this repo:

```bash
claude --plugin-dir ./context-cost-guard
```

Or add the marketplace from a local path:

```text
/plugin marketplace add /absolute/path/to/context-cost-guard
/plugin install context-cost-guard@context-cost-guard
```

---

## What it does

| Piece | Detail |
| --- | --- |
| Event | `UserPromptSubmit` — runs **before** the API call |
| Action | **Block** the turn once with a clear English message (not “warn after you already paid”) |
| Trigger | **Both** must be true: context ≥ `BIG_CONTEXT` **and** idle ≥ `IDLE_MINUTES` |
| Context size | From the last transcript usage record: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` |
| Idle | Minutes since the last assistant `timestamp` in the session JSONL transcript |
| Snooze | After a block, the same session may resend for `SNOOZE_SECONDS` (default 300) without another block |
| Fail-open | Bad stdin, missing transcript, corrupt JSON, I/O errors → exit quietly, **never** block |

### Example block message

```text
  This turn will cost much more than it looks.

  Conversation context : 379,250 tokens
  Idle                 : 94 min  (cache likely expired after 60 min)
  Est. turn cost       : ~758,500 vs ~37,925 token-equivalents

  /clear    new topic — cheapest, start from zero
  /compact  same thread, summarized
  resend    send the same prompt again to continue anyway
```

- **`/clear`** — cheapest reset for a new topic  
- **`/compact`** — stay in the thread with a summarized context  
- **resend** — send the same prompt again within the snooze window to continue anyway  

Snooze state lives at `~/.claude/.context-cost-guard.json` (keyed by `session_id`; entries older than one day are pruned).

### When it stays quiet

- Context under 60 000 tokens (default), **or**
- Idle under 55 minutes (default), **or**
- You already hit the block and are within the 5-minute snooze window, **or**
- Anything goes wrong reading the transcript / stdin (fail-open)

---

## How it works

```text
You submit a prompt
        │
        ▼
UserPromptSubmit hook
        │
        ├─ read session transcript (JSONL)
        ├─ measure last context size + idle minutes
        │
        ├─ below thresholds? ──────────────► allow (no output)
        ├─ snoozed for this session? ──────► allow
        │
        └─ otherwise ──────────────────────► block once + write snooze
                                              show cost estimate + options
```

Approximate token-equivalent estimate used in the message:

- Warm (cache hit): `context × 0.1`
- Cold (cache write at ~2×): `context × 2`

These are **illustrative multipliers**, not live Anthropic price tables. Check current docs for exact rates.

---

## Knobs

Edit constants at the top of  
`context-cost-guard/hooks/context-cost-guard.py`  
(then reinstall / reload the plugin, or restart Claude Code):

| Constant | Default | Meaning |
| --- | ---: | --- |
| `IDLE_MINUTES` | `55` | Block only if idle at least this many minutes (tuned for ~1h cache TTL) |
| `BIG_CONTEXT` | `60000` | Block only if last-turn context is at least this many tokens |
| `SNOOZE_SECONDS` | `300` | After a block, allow resends for this many seconds |

---

## Caveats

1. **Time-based TTL assumption** — The hook infers cache expiry from **idle time**, assuming a **1 hour** prompt-cache TTL (`IDLE_MINUTES=55`). On accounts / routes that use a **5 minute** TTL (or other overage behavior), it can **under-warn**: the cache may already be cold while idle is still under 55 minutes.
2. **Not a billing meter** — Token-equivalent numbers are rough (`0.1×` warm / `2×` cold). They are for intuition, not invoices.
3. **Needs a transcript with usage** — Brand-new sessions or missing usage records fail open (no block).
4. **Python 3 required** — The hook command is `python3 …`.

---

## Uninstall / disable

```text
/plugin disable context-cost-guard@context-cost-guard
```

or

```text
/plugin uninstall context-cost-guard@context-cost-guard
```

Optional cleanup:

```bash
rm -f ~/.claude/.context-cost-guard.json
```

To remove the marketplace catalog from Claude Code:

```text
/plugin marketplace remove context-cost-guard
```

---

## Repository layout

This git repo is a **single-plugin marketplace**:

```text
.claude-plugin/marketplace.json          # marketplace catalog
context-cost-guard/
  .claude-plugin/plugin.json             # plugin manifest
  hooks/hooks.json                       # UserPromptSubmit → command hook
  hooks/context-cost-guard.py            # guard script
  README.md
  LICENSE
LICENSE
README.md
```

The hook command uses `${CLAUDE_PLUGIN_ROOT}` so it resolves correctly after install:

```json
"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/context-cost-guard.py\""
```

---

## License

[MIT](LICENSE)

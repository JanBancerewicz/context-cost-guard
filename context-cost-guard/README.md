# context-cost-guard (plugin)

Claude Code plugin that blocks **once** before an expensive cold-cache turn when context is large and the session has been idle past the prompt-cache TTL window.

**Full documentation** (install, screenshots, trust notes, extensibility, caveats): see the [repository README](../README.md).

## Quick install

```text
/plugin marketplace add JanBancerewicz/context-cost-guard
/plugin install context-cost-guard@context-cost-guard
```

Restart Claude Code afterward.

## Files

| Path | Role |
| --- | --- |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `hooks/hooks.json` | `UserPromptSubmit` → command hook |
| `hooks/context-cost-guard.py` | Guard script (English messages, fail-open) |

## License

[MIT](LICENSE)

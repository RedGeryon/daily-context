# Other AI tools

Daily Context's capture boundary is host-neutral. Any AI tool that can run a command at session end can call:

```sh
daily-context capture-session --host other
```

Send a JSON object on standard input. The adapter recognizes these fields:

```json
{
  "session_id": "stable-session-id",
  "cwd": "/path/to/the/workspace",
  "transcript_path": "/private/path/to/an/exported-transcript",
  "reason": "session-ended"
}
```

`sessionId`, `conversation_id`, `workspace`, and `transcriptPath` are accepted aliases. Unknown fields are ignored rather than stored.

The workspace should contain `.daily-context.json`, normally created by `daily-context init --workspace .`. Alternatively, set `DAILY_CONTEXT_DIR` to the context directory.

## Safety behavior

- Capture does nothing unless `auto_update.mode` is `capture`.
- Repeated events for the same host, session, and transcript are deduplicated.
- The hook payload itself is not copied into tracked records.
- A small private receipt is stored under the ignored `raw/` directory.
- An available transcript is copied only when capture is enabled and it is below the configured size limit.
- Exact local paths stay in ignored local state, not tracked manifests.
- The source remains pending until a person or agent reviews it.

An integration should call the command once when a main session ends. It should not call it after every tool invocation or subagent event.

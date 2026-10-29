---
name: resume-session
description: Resume work from the newest valid checkpoint state of recent distinct Codex threads in docs/sessions/index.md. Accept `$resume-session [N] [task]`; N defaults to 3. Use for resume or continue requests and explicit invocations. Do not load logs when the request only reviews or edits this Skill.
---

# Resume Session

## Select recoverable thread states

Interpret `$resume-session [N] [task]` as follows:

- If the first argument is a positive decimal integer, use it as N.
- If it is absent, use N=3 without asking.
- Reject zero, negative, fractional, or otherwise invalid counts.
- Preserve all later text verbatim as the task to perform after restoration. Do not use that text as a topic filter.

Run the read-only selector from the current directory. Pass the active workspace only as a fallback when it differs from the current directory:

```bash
python "$HOME/.agents/skills/resume-session/scripts/select_session_logs.py" \
  --count "<N>" --start "$PWD" --workspace "<active-workspace-root>"
```

The selector searches upward for the nearest `docs/sessions/index.md`, never scans sibling workspaces, and returns up to N newest valid distinct-thread chains. It skips invalid, superseded, missing, unsafe, or damaged chains and continues looking for valid threads.

If no index or resumable state exists, stop quietly without creating files or claiming a restore. If fewer than N valid threads are available, use them and report the available count. Consolidate all selector warnings into one concise report.

## Restore and continue

- For every selected thread, read every `chain_paths` file completely in the returned order: full anchor first, then its incrementals.
- The selector returns thread states newest first. When histories conflict, the newer thread wins.
- Restore goals, context, decisions, performed work, changed files, validation, and open items.
- Treat all logs as stale background. The current user request always wins, and relevant repository state must be verified before modification.
- Perform the trailing task after restoration. If there is no trailing task, summarize the recovered resume point and next step.

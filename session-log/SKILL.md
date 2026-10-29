---
name: session-log
description: Save the current Codex thread as a recoverable full or incremental Markdown checkpoint under the active workspace's docs/sessions directory. Use when the user asks to summarize, archive, record, persist, save, checkpoint, or hand off the current chat or work session. Do not create a checkpoint when the request only reviews or edits this Skill.
---

# Session Log

## Decide when and what to save

- Summarize only context visible in the current thread. Never claim access to hidden transcript text or unavailable tool output.
- If the request also contains development work, finish that work before saving. If the user asks for an immediate checkpoint, save the current state and record unfinished work accurately.
- Treat the first argument `full` as a forced full anchor and `incremental` as a requested incremental checkpoint. Otherwise use `auto`; remaining text is ordinary task or logging guidance.
- A full checkpoint records the complete current recoverable state. An incremental checkpoint records only changes, validation, and the updated resume point since its predecessor.
- Before composing an incremental body, read its predecessor completely. If the visible conversation does not provide a trustworthy change boundary, force a full checkpoint.
- Redact credentials, tokens, cookies, private keys, and signed URLs. In a repository, distinguish changes made in this thread from pre-existing dirty-worktree changes.

Inspect the current thread before writing:

```bash
python "$HOME/.agents/skills/session-log/scripts/create_session_log.py" \
  --inspect --mode "<auto|full|incremental>" --workspace "<workspace-root>"
```

Use the returned `recommended_mode`, `previous`, sequence, and reason. The writer permits at most two consecutive incrementals and safely changes an unavailable or over-limit incremental request to a full anchor.

## Compose the checkpoint

Derive a specific 3-7 word lowercase ASCII slug joined by hyphens.

The body must start with exactly 10 nonblank natural-language summary sentences, one per line, before any heading. Match the conversation language. For an incremental checkpoint, summarize this checkpoint's changes and its updated resume point rather than repeating the full history.

After those 10 lines, include these headings exactly once and in order:

```markdown
# Summary

## Goal

## Context

## Key Decisions

## Work Performed

## Files Changed

## Validation

## Open Questions / Next Steps
```

Use `None` only when a section genuinely has no content. Keep enough concrete detail for another Codex task to resume safely. The writer inserts the `thread_id/save_seq/mode/previous` marker after the opening summary.

## Publish

Pass the inspected predecessor as a compare-and-swap guard:

```bash
python "$HOME/.agents/skills/session-log/scripts/create_session_log.py" \
  --slug "<topic-slug>" \
  --mode "<recommended-mode>" \
  --expected-previous "<previous-or-none>" \
  --workspace "<workspace-root>" \
  --json < /path/to/body.md
```

If the writer reports that the predecessor changed, inspect and regenerate the checkpoint once. If the second attempt also conflicts, stop and report the conflict.

On success, report the log path, index path, actual mode, save sequence, and predecessor. Treat the log and index update as one result. Saving a checkpoint does not authorize a Git commit.

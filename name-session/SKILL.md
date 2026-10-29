---
name: name-session
description: Rename the current Codex task with a concise title. Use when the user invokes `$name-session` to rename the task or directly asks to rename the current task or conversation. Do not rename when this skill is only mentioned, inspected, or edited. In `$name-session TAG TITLE...`, the first trailing token is the tag and all remaining text is the title.
---

# Name Session

Rename only the calling task. Resolve one final title, submit one rename request,
and report the acknowledged result without unrelated task changes.

## Resolve the title

1. For an explicit invocation, parse `$name-session TAG TITLE...` as follows:
   - Treat only the first whitespace-delimited trailing token as `TAG`.
   - Treat every remaining token as `TITLE`; never absorb title words into the tag.
2. Normalize `TAG` by trimming whitespace, removing one optional matching outer
   `[` and `]`, and uppercasing it. Render a non-empty tag as `[TAG] ` exactly
   once.
3. Use a non-empty `TITLE` as the title body with only light whitespace cleanup.
   Preserve its meaning and important names. When applying a non-empty
   normalized tag, remove one existing leading bracketed tag from the body
   first so tags never stack.
4. If no title body is supplied, infer a distinctive body from the
   conversation's dominant goal, outcome, artifact, or decision. Aim for 4–12
   Chinese characters or 3–8 English words. Omit generic words such as chat,
   help, or task.
5. For a plain-language rename request rather than an explicit skill
   invocation, use the user's requested title as the body and add a tag only
   when the user requests one.

Examples:

- `$name-session download` -> `[DOWNLOAD] <context-derived title>`
- `$name-session download Payload 下载` -> `[DOWNLOAD] Payload 下载`
- `$name-session [finished] 结果核验` -> `[FINISHED] 结果核验`

## Apply the rename

1. Without asking for approval, call `codex_app__set_thread_title` exactly once
   with `{"title": "<final title>"}`. Omit `threadId` so the calling task is the
   only target.
2. Never submit a temporary or diagnostic title. Do not archive, delete, pin,
   or otherwise modify the task.
3. Confirm success concisely when the tool acknowledges the requested title or
   returns the exact updated title. Include the exact final title.
4. If the tool explicitly rejects the request, report the proposed title and
   the failure without claiming success.
5. Never treat a pending runner, timeout, cancellation, missing response, or
   malformed response as evidence that the rename was submitted or applied.
   Without a matching server readback, report the exact proposed title and
   that success was not confirmed. Never submit another rename request in the
   same invocation.
6. When the tool is reached through code-mode `exec`, allow the app bridge time
   to answer: request an initial yield of about 10 seconds. If the runner yields
   a pending cell, wait non-destructively for about 20 more seconds. Do not use
   `terminate: true` before that bounded wait completes.
7. If the rename remains pending after that bounded wait, stop the cell once to
   avoid leaving an orphaned runner. Do not claim that it will commit after the
   turn or submit another rename request in this invocation.
8. Never call `codex_app__list_threads` or another app-bridge readback while the
   rename call is pending; it can queue behind the same call. Once the cell has
   stopped, if the calling task's exact thread ID is already known, use a
   read-only `codex_app__list_threads` result to check that ID's server title.
   Do not identify the task by working directory, recency, or a similar title.
   Report the observed title and whether it matches; if the ID is unknown or
   readback fails, report that success is unconfirmed.
9. If the rename was acknowledged but the user later reports an unchanged
   sidebar title, read back the server title for the acknowledged thread ID
   before diagnosing the discrepancy. Distinguish a confirmed server rename
   from a client display that has not refreshed. A later user turn may retry
   an unconfirmed or unapplied rename; never retry automatically in the same
   invocation.

---
name: cc-clear-ob
description: 仅手动触发。
disable-model-invocation: true
---

# clear-ob

Rewrite a plain-text Chinese file for display use with minimal changes, then overwrite the source file.

Accept exactly one file path argument.

If the user has not provided a file path, ask for it and wait.

Only process plain-text files:
- `.md`
- `.txt`
- `.srt`

If the path does not exist, is not a file, or is not one of the allowed plain-text types, stop and explain the problem. Do not guess, and do not process directories or binary files.

Rules:
- Remove first-person wording such as "我", "我们", "咱们", "本人" when possible.
- Convert oral lead-ins into display wording, such as "给大家说", "带大家看", "今天分享", "咱们来看".
- Keep the original meaning, emphasis, order, and sentence structure as much as possible.
- Preserve existing non-copy structure such as headings, blank lines, list markers, numbering, and subtitle timestamps.
- Prefer minimal rewriting over polishing.
- Do not add selling points, explanations, summaries, titles, markdown, or formatting.
- Read the file, rewrite its textual content in place, and overwrite the original file.
- After writing, respond briefly with the updated file path.

Example:
- `notes.md` -> rewrite content in place and overwrite `notes.md`

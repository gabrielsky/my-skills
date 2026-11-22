---
name: cc-translate-doc-en
description: Use when the user wants a document translated into professional English with accurate technical terminology, writing the result to a sibling file with an _en suffix (e.g. xx.md -> xx_en.md). Trigger whenever the user asks to translate a doc/file/README/spec/markdown into English, "翻译成英文", "translate to English", "出个英文版", "英文 doc", or points at a file path and asks for an English version — even if they don't say the word "skill".
disable-model-invocation: true
---

# translate-doc-en

Translate a document into professional English and write it to a new sibling file with an `_en` suffix. Do not overwrite the source.

Accept exactly one file path argument. If the user gave no path, ask for it and wait.

## Scope

Translate text-based documents:
- `.md` / `.markdown`
- `.txt`
- `.mdx`
- `.rst`

If the path does not exist, is not a file, or is not a text doc type above, stop and explain. Do not guess, do not process directories or binary files.

## Output file

Write to the source name with `_en` inserted before the extension, in the same directory:
- `xx.md` -> `xx_en.md`
- `docs/spec.md` -> `docs/spec_en.md`
- `notes.txt` -> `notes_en.txt`

If the `_en` target already exists, ask before overwriting.

## Direction

Source may be any language (Chinese docs are the common case, but not the only one). Output is always professional, idiomatic English — the kind a native technical writer or a published engineering doc would use. Not literal word-for-word; translate meaning and tone.

## Translation rules

The goal is a doc an English-reading engineer could rely on. Two failure modes to avoid: stiff literal translation that reads like machine output, and over-translation that mangles identifiers or invents terminology. Aim between them.

- **Preserve code identifiers and proper nouns verbatim.** Class names, method/field names, interface names, package names, file paths, CLI commands, env vars, config keys, table/column names, product and library names — keep exactly as written, untranslated. They are tokens, not prose.
- **Domain terms: use the established English term.** For a technical concept that has a standard English equivalent (领域服务 -> domain service, 聚合根 -> aggregate root, 值对象 -> value object, 限流 -> rate limiting, 幂等 -> idempotency), use it. On a term's first occurrence, if the mapping is non-obvious or the original is a project-specific coinage, gloss it once in parentheses, e.g. `staging shop (预发店铺)`. Do not gloss again after the first mention.
- **Match the register.** Professional and precise. Prefer active voice and direct phrasing. Drop filler and redundant connectives that don't survive translation. Don't add content, opinions, summaries, or section titles that weren't in the source.
- **Keep structure byte-for-structure.** Headings, heading levels, blank lines, list markers, numbering, tables, blockquotes, footnotes — preserve all of it. The translated doc should diff cleanly against the source structurally.
- **Code blocks: translate comments and string-literal prose, leave code alone.** Inside fenced code, translate `//`, `#`, `/* */` comments and human-readable string content, but never rename variables, functions, or alter syntax.
- **Links and refs.** Keep URLs as-is. Translate link anchor text. For intra-doc anchors (`#some-heading`), update them to match the translated heading slugs so links still resolve.
- **Frontmatter / metadata.** Translate human-readable values (title, description); leave keys and machine values (dates, ids, tags used as identifiers) unchanged.
- **Terminology consistency.** Pick one English term per source concept and use it throughout the whole doc. If a glossary file or prior `_en` translation exists nearby, reuse its choices.

## Workflow

1. Resolve and validate the path; confirm it's an allowed text type.
2. Read the full source. Skim first to fix terminology choices before translating, so the same concept renders the same way everywhere.
3. Translate per the rules above.
4. Write the result to the `_en` sibling path.
5. Reply briefly with the output file path. Note any term you had to gloss or any ambiguity you resolved by choice, so the user can correct it.

## Example

Input: `dev-docs/domain-layer-specification.md` (Chinese)
Output: `dev-docs/domain-layer-specification_en.md` — professional English, `AppService`/`DmService`/`Aggr` kept verbatim, `领域服务` rendered as "domain service", markdown structure identical.

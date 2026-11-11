---
name: ai-news
description: Brief me on what is newest in AI and Claude Code since my last check — new Claude models, Claude Code releases and features, Anthropic announcements, the wider AI landscape, and community tips worth adopting. Use when I ask "what's new", "catch me up", "latest in AI / Claude Code", or run /ai-news.
argument-hint: "[focus: all | claude-code | models | ai | tips] [window: 7d | 30d]"
allowed-tools: WebSearch WebFetch Read Edit
---

# AI & Claude Code news brief

Arguments: `$ARGUMENTS` (empty = focus `all`, window = since the last entry in the log).

## 1. Know what I already know

Read `log.md` in this skill's folder. The newest entry's date is the start of the window,
and anything already listed there is old news: skip it unless it changed.
If the log is empty or missing, use the last 14 days.

## 2. Check sources in this order (primary first)

Fetch each and keep only items dated inside the window. Skip a source that fails; note it.

| Area | Source |
|---|---|
| Claude Code releases | https://code.claude.com/docs/en/changelog.md (newest at top; read only the top) |
| Claude Code docs map | https://code.claude.com/docs/llms.txt (spot new or renamed pages) |
| Anthropic announcements | https://www.anthropic.com/news |
| Engineering deep dives | https://www.anthropic.com/engineering |
| Models, prices, retirements | https://platform.claude.com/docs/en/about-claude/models/overview and https://platform.claude.com/docs/en/about-claude/model-deprecations |
| API changes | https://platform.claude.com/docs/en/release-notes/overview |
| Community patterns | https://github.com/shanraisshan/claude-code-best-practice (look at recent changes / "hot features") |
| Community discussion | Reddit is often blocked to direct fetch: use WebSearch with `site:reddit.com/r/ClaudeCode` and `site:reddit.com/r/ClaudeAI` plus the current month |
| Wider AI | WebSearch (`mode: standard`) for "AI news this week <month year>"; then confirm big items on the vendor's own blog (OpenAI, Google, Meta, xAI, Mistral, DeepSeek) |

## 3. Rules

- Every item gets a date and a source link. No date or no source → leave it out.
- Tag each item **[official]** (vendor's own site or docs) or **[unverified]** (news site, aggregator, Reddit).
  Never present an unverified number (benchmark, revenue, user count) as fact.
- If community advice contradicts current official docs, say so and side with the docs unless the user's own experience says otherwise.
- Don't guess. If a source was unreachable, say which one.
- Keep the brief under ~400 words unless the user asks for depth.

## 4. Output format

```
## AI brief — <today>  (covering <start> → <today>)

**Top 3 that matter to you**
1. <item> — <one line on why it matters / what to do> ([source](url)) [official]
2. …
3. …

**Claude models** — …
**Claude Code** — versions <x>–<y>: the few changes worth knowing …
**Anthropic** — …
**Wider AI** — …
**Try this week** — 1–2 concrete tips or features to try, with the doc link
**Couldn't check** — <sources that failed, if any>
```

## 5. Update the log

Append one entry to the top of `log.md` (newest first), at most 6 bullets:

```
## <today>
- <item> (<date>, <source>)
```

If the brief contains something that makes `.claude/notes/ai-foundation.md` wrong
(a new default model, a renamed feature, a retired model), tell the user and offer to update it — don't edit it silently.

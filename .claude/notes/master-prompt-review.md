# Master prompt system: review and how to set it up in Claude Code

As of **2026-11-11**. Checked against the official Claude Code docs and Anthropic's code-review work.
Tags: **[official]** = Anthropic docs/site · **[unverified]** = second-hand summary.

## Verdict

The system is sound and mostly matches Anthropic's own guidance: layered knowledge, evidence over opinion, a way to check work, and humans owning the irreversible.
The biggest gap is that **every rule is written as text**. Claude usually follows text, but nothing forces it to. Turn the rules that must never break into settings. [official]

## 1. Turn the must-never-break rules into settings

Official rule of thumb: prompts, CLAUDE.md and skills are things Claude *decides* to follow; hooks, deny rules and settings are things Claude Code *enforces*. "If it's a rule that can't bend, turn it into a hook or a deny rule." [official]

| Your rule | Text today | Enforce it with |
|---|---|---|
| Human gate: never publish, delete, send, spend, change live systems | Agent base, Full general | Auto mode already blocks production deploys, force pushes, mass deletes, merging unapproved PRs, IAM changes and more. Add `permissions.deny` rules for anything specific to you, e.g. `"Bash(git push *)"`. Deny rules apply in every mode |
| Use only the tools and folders in your role file | Agent base | The subagent's `tools:` / `disallowedTools:` fields, plus permission rules for paths |
| Stop if you exceed [X] steps or costs look unusual | Agent base | The subagent's `maxTurns:` field; `--max-turns` and `--max-budget-usd` for scripted runs (`claude -p`) |
| Every piece of work must include a way to verify it | Agent base | A `Stop` hook that runs the check, or `/goal` |
| Never store passwords or API keys | Notes | A deny rule on reading `.env`/secret files. Auto mode also blocks printing live credentials |

Keep the rest (context first, evidence, report format, concise answers) as text. Those are judgment calls, and the docs say Claude is better placed to make them with the code in front of it.

## 2. Put each layer in the right file

| Layer | Where it goes in Claude Code | Change |
|---|---|---|
| Compact | claude.ai → Settings → personal preferences | Already in place ✓ |
| Full general | `~/.claude/CLAUDE.md` on your machine, once. It applies to every project | Don't copy it into each project's CLAUDE.md |
| "This project" section | The project's own `CLAUDE.md` | Only what Claude can't see in the code: goal, commands, standards, gotchas. The docs say to keep it short and skip architecture descriptions |
| Agent base | A skill: `.claude/skills/agent-base/SKILL.md` with `user-invocable: false` | Each agent preloads it with `skills: [agent-base]`. One copy instead of pasting it into every agent |
| Role template | A subagent file: `.claude/agents/<name>.md` | See §3 |
| Boss | The main Claude Code session (or the lead in agent teams) | Only the boss gets the `Agent` tool |

## 3. The role template as a real subagent file

Every field in your template has a direct match: [official]

```markdown
---
name: researcher                      # Role
description: <the one-sentence Job>   # Claude uses this to decide when to delegate
tools: Read, Grep, Glob, WebSearch    # Tools allowed (anything else is unavailable)
disallowedTools: Agent                # specialists can't spawn their own agents
maxTurns: 30                          # Limits: the "[X] steps" (pick your own number)
memory: project                       # Notes: persists in .claude/agent-memory/researcher/
skills: [agent-base]                  # Agent base, loaded once from one place
model: sonnet                         # cheaper model where the job allows
---
Not my job: …
What good output looks like: …
Reports to: boss
```

- `memory: project` gives the agent a `MEMORY.md`. Claude Code loads its first 200 lines or 25KB, which naturally enforces your "short, dated, current" notes rule.
- By default, subagents can spawn other subagents up to 3 layers deep. Removing `Agent` from the specialists keeps the boss → specialist structure flat.

## 4. What Anthropic's code-review work adds

**[official]** *Code Review in Claude Code*, claude.com/blog/code-review, 2026-03-09:
- A team of agents reviews each pull request in parallel. Each suspected bug is checked again to weed out false alarms, then ranked by severity. **It never approves the PR; a human still decides.**
- At Anthropic, PRs with substantive review comments went from 16% to 54%. Under 1% of findings were marked incorrect.
- Bigger PRs get deeper reviews: 84% of PRs over 1,000 lines had findings (7.5 on average), vs 31% of PRs under 50 lines.
- Costs about $15–25 per review and takes about 20 minutes. Team and Enterprise plans. A free, lighter path is the `/code-review` command in Claude Code.

**[unverified]** *Solving code review at Anthropic*, claude.dev/blog. I couldn't open it from this session, so this comes from secondary summaries:
- Risk tiers decide which changes need a human and which can rely on automated checks.
- Code owners write a `REVIEW.md` telling the AI reviewer what matters in their area.
- Review rounds are capped at 3 before the reviewer asks the author to rethink the approach.
- Reported results: roughly 40% fewer rollbacks, with about 90% of the Claude Code repo written by AI.

**Ideas to borrow:**
1. **Add risk tiers to your Human gate.** For example: *low* (docs, copy) → agent-checked only; *medium* (logic) → independent reviewer agent; *high* (money, data, live systems) → you approve. Today the gate is all or nothing.
2. **Make the second opinion a fresh agent.** The docs say a new reviewer helps because it hasn't seen the author's reasoning. Delegating the same task to a subagent doesn't make the answer better. Your "another model" is fine; the fresh context is what matters most.
3. **Your boss's 2-round cap is right.** Anthropic reportedly uses 3. Either way, a cap that hands the work back to you is the key part.
4. **Add a `REVIEW.md` per project** for anything a reviewer must always check (e.g. "the league board in `live_state.json` must never be wiped").

## 5. Small fixes

- **"Measure, then refine"** → make the escalation explicit: first miss, add a plain line; still missed, make it a hook. Don't add CAPS or "IMPORTANT". The docs say emphasis makes Claude over-apply rules.
- **Fill in the placeholders** before use: `[X] steps` → a `maxTurns` number; "Tools allowed" → real tool names (`Read`, `Grep`, `WebSearch`, `Bash(npm test *)`…).
- **The pasted copy repeated the whole system about 7 times.** Your saved claude.ai preferences hold just one copy, which is right. Make sure no saved file has duplicates, since every copy is re-read on every turn.

## Decisions (2026-11-11)

- **Text for judgment, settings for guarantees.** Reason: the official docs split instructions this way, and your Human gate is exactly the kind of rule that can't have exceptions.
- **Agent base becomes a preloaded skill, not pasted text.** Reason: one source of truth, matching your "share the basics" principle.

Sources: [Claude Code best practices](https://code.claude.com/docs/en/best-practices.md) · [Subagents](https://code.claude.com/docs/en/sub-agents.md) · [Permission modes](https://code.claude.com/docs/en/permission-modes.md) · [Code Review announcement](https://claude.com/blog/code-review) · secondary: [besthub.dev summary](https://www.besthub.dev/articles/how-anthropic-scales-code-review-with-ai-90-automated-40-fewer-rollbacks-d852562f2ae7), [alexop.dev](https://alexop.dev/tils/how-claude-code-team-does-code-review)

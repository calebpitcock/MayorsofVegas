# AI & Claude Code — catch-up foundation

As of **2026-11-11**. A stable primer to get you current; for what changed since, run `/ai-news`.
Tags: **[official]** = Anthropic's own docs/site. **[unverified]** = news/aggregator, not confirmed at the source.

---

## 1. The 60-second version

1. **Two things move separately: the model and the harness.** The model (Fable, Opus, Sonnet, Haiku) is the brain. Claude Code is the harness: the tool that gives the model files, a shell, permissions, memory and automation. Most "what's new" is one or the other.
2. **Current lineup:** Fable 5.2 (top, released 2026-11-09), Opus 5.5 (default recommendation), Sonnet 5.5 (fast/cheap), Haiku 5.5 (high-volume). All have a 1M-token context. [official]
3. **Claude Code now works well out of the box.** New terminal and VS Code sessions start in *auto mode* (a classifier screens risky actions instead of asking you every time), compaction is automatic, and Claude delegates to subagents on its own. [official]
4. **The one idea to internalize:** prompts, CLAUDE.md and skills are *suggestions* Claude usually follows; hooks, deny rules and settings are *guarantees* Claude Code enforces. Put must-never-break rules in the second group. [official]
5. **A lot of older advice is obsolete** (see §5). Community guides lag the docs, so check the date on any tip.

---

## 2. Claude models right now [official]

| Model | Use it for | API ID | Price in / out per 1M tokens | Default effort |
|---|---|---|---|---|
| **Fable 5.2** | Hardest reasoning, long agentic runs | `claude-fable-5-2` | $8 / $40 | high |
| **Opus 5.5** | Start here for most work, incl. coding | `claude-opus-5-5` | $4 / $20 | medium |
| **Sonnet 5.5** | Best speed-to-smarts balance | `claude-sonnet-5-5` | $2 / $10 | high |
| **Haiku 5.5** | Classification, extraction, routing | `claude-haiku-5-5` | from $0.10 / $0.50 | medium |

- All: 1M context, 128K max output, knowledge cutoff June 2026, "adaptive thinking" (the model decides how much to think; you steer with **effort**: `low` → `max`).
- **Mythos 5.2** is the same model as Fable 5.2 with different safeguards, only for verified cyber/life-science orgs.
- Benchmarks in the launch coverage come from Anthropic's own announcement; outlets call the gains over Opus 5.5 real but mixed. [unverified]
- **Retiring 2026-11-30:** `claude-sonnet-4-5` on the API (→ Sonnet 5.5) and Opus 4.8 fast mode in Claude Code.
- `temperature` / `top_p` / `top_k` are gone in API version `2026-10-21`. Steer with prompting instead.

Sources: [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) · [deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) · [Fable/Mythos 5.2 announcement](https://www.anthropic.com/news/claude-fable-and-mythos-5-2)

---

## 3. Claude Code: the building blocks

What each piece is, and when to reach for it. Current version: **2.1.322**.

| Piece | What it is | Use it when |
|---|---|---|
| **CLAUDE.md** | Notes Claude reads at the start of every session | Facts Claude can't get from the code: commands, conventions, gotchas. Keep it short |
| **Rules** (`.claude/rules/` with `paths:`) | CLAUDE.md snippets that load only for matching files | A rule applies to one part of the codebase |
| **Skills** (`.claude/skills/<name>/SKILL.md`) | Reusable instructions Claude loads when relevant, or you run as `/name` | A procedure you repeat (deploy, review checklist, this news brief) |
| **Hooks** | Scripts Claude Code *must* run on events (before/after a tool, on Stop…) | Something must always or never happen; formatting; a check before "done" |
| **Permissions & sandbox** | Allow/deny rules for tools, files, commands | Hard limits: "never read `.env`", "never push to main" |
| **Permission modes / auto mode** | How much Claude asks before acting | Auto (default) for most work; plan mode to review a plan first |
| **Subagents** | Separate Claude workers with their own context | Parallel work, noisy searches, an independent review |
| **Agent teams** | Several Claude Code sessions coordinated together | Big jobs that split cleanly into parallel parts |
| **MCP servers** | Plug-ins that connect Claude to outside tools (GitHub, Slack, DBs) | Claude needs data or actions outside your repo |
| **Plugins** | Bundles of skills, hooks, agents and MCP config you install | Sharing a whole setup across projects or a team |
| **Scheduled tasks** (formerly *routines*) | Cloud runs on a schedule, an API call, or a GitHub event | Recurring jobs nobody needs to watch |
| **Remote Control** | Continue a local session from your phone or browser | Kick off work at your desk, check it from anywhere |
| **Effort & `ultrathink`** | Effort = how hard the model thinks by default; `ultrathink` = deeper on one turn | Raise for hard problems; "think harder" in a prompt does *not* raise effort |
| **`/goal`, `/code-review`, Stop hook** | Ways to define "done" | Give Claude a check to pass instead of trusting its summary |
| **Code Review (GitHub)** | A team of agents reviews every PR, double-checks each bug, ranks it by severity, never approves | Team/Enterprise; ~$15–25 and ~20 min per review. `/code-review` is the lighter local version |
| **Headless (`claude -p`)** | Run from scripts/CI, capped with `--max-turns` / `--max-budget-usd` | Automation and batch jobs |

Official guidance in three lines: **tell Claude what it can't see, give it a check to run, and enforce the rules that can't have exceptions.**

Sources: [best practices](https://code.claude.com/docs/en/best-practices.md) · [skills](https://code.claude.com/docs/en/skills.md) · [hooks](https://code.claude.com/docs/en/hooks-guide.md) · [docs index](https://code.claude.com/docs/llms.txt) · [changelog](https://code.claude.com/docs/en/changelog.md)

---

## 4. A simple way to work

1. **Say what you want and how you'll know it's done.** Include the check (a test, a screenshot, a command).
2. **For anything big, plan first.** Plan mode, or "interview me before building", then build.
3. **Let it run.** Auto mode handles routine approvals. Say `continue` if it stops short.
4. **Ask for proof, not a summary.** "Show me the diff and the test passing."
5. **`/clear` between unrelated tasks.** It's cheaper and answers are sharper. Use `/rewind` to undo a bad attempt instead of piling on corrections.
6. **When Claude repeats a mistake,** add one plain line to CLAUDE.md. If it still misses it, make it a hook.

---

## 5. Habits to drop (and where community advice is behind)

Straight from the official docs [official]:

| Old advice | Why it's out of date |
|---|---|
| Manage the context window aggressively | 1M context + automatic compaction. Still `/clear` between tasks |
| Write IMPORTANT / ALL CAPS | Current models follow plain lines; emphasis makes them over-apply rules. Use a hook for hard rules |
| Use subagents to save context | Rarely needed now; subagents cost extra tokens. Use them for parallel work or a fresh reviewer |
| "think hard / be thorough" | Effort is the control. `ultrathink` still works for one turn |
| "keep going, don't be lazy" | Causes over-work. Give a check instead (`/goal`, Stop hook) |
| Describe your architecture in CLAUDE.md | Claude reads the repo. Only write what isn't there |

**Where your sources disagree:** the community repo `shanraisshan/claude-code-best-practice` still recommends wrapping up at 40–60% context and using subagents mainly to protect context. Both conflict with the current official guidance above. Its other tips (plan first, ask for proof, `/rewind`, short CLAUDE.md, hooks for formatting) still line up.

---

## 6. What happened recently (Oct–Nov 2026)

| Date | Event | Tag |
|---|---|---|
| 2026-11-10 | Anthropic launches IPO roadshow | [official] |
| 2026-11-10 | Claude Meetings (Claude joins video calls), Whiteboards, Sheets | [unverified] |
| 2026-11-09 | Claude Fable 5.2 and Mythos 5.2; Fable 5.2 becomes Claude Code's default Fable model | [official] |
| 2026-11-06 | Engineering post: "The components of agent memory" | [official] |
| 2026-10-26 | Anthropic files S-1 for IPO | [official] |
| 2026-10-22 | Agent Skills standard donated to the Agentic AI Foundation; 70+ platforms use it | [official] |
| 2026-10-21 | API version `2026-10-21` removes sampling parameters | [official] |
| 2026-10-08 | Anthropic Cyber Mission announced | [official] |
| undated | "Solving code review at Anthropic" (claude.dev): risk tiers, `REVIEW.md` per code area, 3-round cap, ~40% fewer rollbacks. Applied to your setup in `master-prompt-review.md` | [unverified: blocked here, summaries only] |
| 2026-03-09 | Code Review in Claude Code launched: substantive PR comments 16% → 54%, <1% of findings marked wrong | [official] |

**Wider AI** [unverified — from newsletters, confirm on vendor blogs before relying on it]:
- The big theme this month is **security-focused models**: Google's Gemini 4 Carbon and OpenAI's GPT-6 Cyber, both first released only to vetted defenders.
- OpenAI: Images 2.6 (2026-11-04), "Businesses in ChatGPT" (2026-11-10), a revised Model Spec.
- Google: Gemini Omni 1.2 Flash GA (2026-11-05); AI Plus subscribers lose Pro model access from 2026-11-13.

Sources: [Anthropic news](https://www.anthropic.com/news) · [Anthropic engineering](https://www.anthropic.com/engineering) · [TechCrunch on Claude Meetings](https://techcrunch.com/2026/11/10/anthropic-launches-claude-meetings-to-turn-workplace-discussions-into-plans-and-tasks/) · [The Neuron, 2026-11-11](https://www.theneuron.ai/digest/everything-that-happened-in-ai-today-wednesday-november-11-2026/) · [AI News of the Week, 2026-11-06](https://manaknightdigital.com/blog/ai-news-week-of-november-06-2026)

---

## 7. Your sources, ranked by trust and how often to check

| Source | Trust | Check |
|---|---|---|
| [Claude Code docs](https://code.claude.com/docs/llms.txt) + [changelog](https://code.claude.com/docs/en/changelog.md) | Highest | Weekly (via `/ai-news`) |
| [Anthropic news](https://www.anthropic.com/news) | Highest | Weekly |
| [Anthropic engineering blog](https://www.anthropic.com/engineering) | Highest, deep | Monthly; read the posts you care about |
| [Claude API release notes](https://platform.claude.com/docs/en/release-notes/overview) | Highest | Only if you build on the API |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | Good ideas, can lag the docs | Monthly |
| r/ClaudeCode, r/ClaudeAI | Mixed; great for real-world gotchas | When stuck, or skim weekly |

---

## Decisions (2026-11-11)

- **Skill and notes live in `.claude/`** of this repo, so they're versioned and not served by the GitHub Pages site. To use `/ai-news` in every project, copy `.claude/skills/ai-news/` to `~/.claude/skills/` on your own machine.
- **Foundation and news log are separate files.** This primer stays stable; `.claude/skills/ai-news/log.md` grows with each run, so the skill knows what you've already seen.
- **Primary sources first, everything else tagged.** Aggregators surfaced most wider-AI items here and some of their metadata was inconsistent.

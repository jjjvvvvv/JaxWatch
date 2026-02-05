# Claude Code Workflow Constitution
**Version**: 2026-02 · Merged & opinionated personal/team runbook
**Inspired by**: Boris Cherny (@bcherny) thread + team practices (Jan/Feb 2026)
**Core philosophy**: Experiment relentlessly. No single "right" way exists. Build compounding habits via plans, lessons, subagents, and ruthless self-improvement.
**Golden rule**: **Plan first. Prove it works. Demand elegance. Capture lessons.**

## 1. Plan Mode Default (Foundation)

- Enter **plan mode** for ANY non-trivial task (≥3 steps, architectural decisions, refactors, new features)
- Write detailed, low-ambiguity specs upfront → reduces downstream ambiguity
- If anything goes sideways → **STOP immediately**, switch back to plan mode and re-plan (do **not** keep pushing broken code)
- Use plan mode also during verification / review steps — not only for initial building
- When accepting a plan → let Claude clear context for fresh focus (default in recent versions)
- After plan approval → verify the plan itself before implementation starts

## 2. Subagent Strategy

- Use subagents **liberally** — append "use subagents" to throw more compute at hard/complex problems
- Keep main context window clean: offload research, exploration, parallel analysis, deep reasoning
- One focused task per subagent → better quality, less drift
- Background/async subagents return control → discuss with main agent while subtasks run
- Route safety/permission checks → hook to stronger model (e.g. Opus 4.5) for auto-approval of safe actions

## 3. Self-Improvement & Lessons Loop

- After **ANY** correction, feedback, or mistake from user:
  → Immediately update `tasks/lessons.md` (or `CLAUDE.md` / `docs/claude-guidance.md`) with the pattern / rule
- Write clear, reusable rules for yourself that **prevent the same mistake**
- Ruthlessly iterate / prune these lessons → mistake rate drops measurably over time
- At session start (especially project-relevant ones): **Review lessons file first**
- Advanced: maintain per-project `notes/` or `tasks/` folder → point Claude at entire directory

## 4. Verification Before Done (Non-Negotiable)

- **Never** mark a task complete without proving it works
- Diff behavior: main vs. feature branch / before vs. after when relevant
- Ask internally: "Would a staff engineer approve this?"
- Run tests, check logs, reproduce bugs, demonstrate correctness
- For PRs: Claude does first-pass review (many teams run `claude -p` in CI)
- Challenge own work: "Grill me on these changes — don't PR until I pass"

## 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and explicitly ask
  → "Is there a more elegant way?"
  → "Knowing everything I know now, scrap this and implement the elegant solution"
- Skip for dead-simple, obvious fixes — don't over-engineer
- Challenge mediocre first drafts → force cleaner, more idiomatic code
- Prioritize: **Simplicity first** · **Minimal impact** · **No temporary hacks**

## 6. Autonomous Bug Fixing

- Given bug report / failing test / log: **just fix it** — no hand-holding
- Point at logs, errors, stack traces, failing CI → resolve autonomously
- Zero context switching from user in many cases
- "Go fix the failing CI tests" → let Claude own it end-to-end
- Slack / thread bugs → paste entire context → "fix"

## Task Management Flow

1. **Plan First**
   Write plan → `tasks/todo.md` with clear, checkable items

2. **Verify Plan**
   Get approval / review before starting implementation

3. **Track Progress**
   Mark items complete as you go; high-level summary per step

4. **Explain Changes**
   Document why at each meaningful commit / milestone

5. **Document Results**
   Add review / verification section to `tasks/todo.md`

6. **Capture Lessons**
   Update `tasks/lessons.md` after corrections / insights

## Core Principles

- **Simplicity First** — every change as simple as possible; minimal code touched
- **No Laziness** — find root causes; no band-aids; senior-level standards
- **Minimal Impact** — change only what's necessary; avoid introducing new bugs
- **Compounding Memory** — treat lessons.md / docs/ as long-term shared brain
- **Execution > Chat** — workflows should ship, not just converse

## Appendix: Team-Sourced Tactical Tips (Boris / Anthropic Claude Code team)

These are lighter / setup-oriented patterns from the original thread — integrate as you see fit.

- **Parallel Sessions** — biggest unlock: 3–5 git worktrees (preferred) or checkouts; each with own Claude; aliases like za/zb/zc; dedicated analysis worktree for logs/BigQuery
- **Custom Slash Commands / Skills** — commit to git; reuse everywhere; if you do something >1×/day → skill it (e.g. /techdesk scan dupes, /dump-slack-gdrive-asana)
- **Terminal & Environment** — Ghostty (color/unicode); /statusline shows usage+branch; color-code tabs; voice dictation (fn×2 on macOS) for detailed prompts
- **Data & Analytics in Flow** — Use `bq` CLI / DB tools live; checked-in BigQuery skill; many haven't written SQL in months
- **Learning Modes** — /config → Explanatory or Learning style; generate HTML slides / ASCII diagrams of codebases; spaced-repetition skill (you explain → Claude quizzes/stores)

Experiment, measure what compounds for **you**, and iterate the file.

Happy shipping!

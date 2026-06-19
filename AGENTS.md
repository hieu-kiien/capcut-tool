# Codex Working Rules

## Quota Saver

Use a narrow, evidence-first workflow in this repository. Assume long recursive scans and repeated packaging builds are expensive.

- Start from the specific user request and relevant files. Do not inspect the whole repository unless the user explicitly asks for a full audit.
- For project context, start with `docs/README.md` and `docs/PROJECT_CONTEXT.md` before scanning source files.
- Before any broad scan, state the scope and keep output bounded. Prefer targeted `rg` with globs and `-m`, or pipe to `Select-Object -First 80`.
- Avoid unbounded commands such as plain `rg --files`, `git status --short`, `Get-ChildItem -Recurse`, or `Select-String -Pattern '.'` over the repository.
- Exclude noisy/generated paths by default: `.git`, `.venv`, `venv`, `__pycache__`, `build`, `dist`, `node_modules`, `output`, `downloads`, `tools/ffmpeg`, `obfuscated`, and bundled third-party/vendor folders.
- When reading files, use line windows or small targeted ranges. Do not paste entire large source files into context.
- For searches, cap results to the first 80 matching lines unless the user asks for more.
- For package/build commands such as `python scripts\build_exe.py`, run them only when packaging is required or explicitly requested. If run, write verbose logs to a file and return only the final status plus the last 80 lines.
- Do not repeat the same expensive command after a failure unless a relevant input changed.
- For UI work, inspect only the files/components being changed, then run the smallest relevant verification. Full packaging is a final optional step, not the default.
- If a task needs more than about 8 tool/model loops, pause with a short status summary and ask before continuing deeper.

## Preferred Verification

- Use focused unit/smoke checks first.
- Run full build/package only after code-level checks pass and the user wants a distributable artifact.
- Keep terminal output concise. Summarize long outputs instead of forwarding them into the thread.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **capcut tool** (5988 symbols, 8850 relationships, 285 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/capcut tool/context` | Codebase overview, check index freshness |
| `gitnexus://repo/capcut tool/clusters` | All functional areas |
| `gitnexus://repo/capcut tool/processes` | All execution flows |
| `gitnexus://repo/capcut tool/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

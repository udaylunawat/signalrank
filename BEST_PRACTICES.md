# Best Practices: Claude Code + OpenCode for Job Ranker

## Cost Optimization

### 1. **Manage context window aggressively**
Context fills fast. Claude performance degrades as context grows.
- Use `/clear` between unrelated tasks
- Use `/rewind` to summarize checkpoints, not accumulate
- Avoid "kitchen sink" sessions with mixed topics
- Use `/btw` for side questions (doesn't enter context)

### 2. **Use subagents for research**
Exploration consumes context. Delegate to subagents:
```
"Use a subagent to investigate how scraping.py handles rate limits"
```
Subagents run in separate context, report back summaries.

### 3. **Prefer Plan Mode for multi-file changes**
Separate exploration from implementation.
- Plan Mode: Claude reads, analyzes, creates plan (Ctrl+G to edit)
- Normal Mode: Claude implements from plan
Avoids solving wrong problem and reduces rework.

### 4. **Provide verification criteria**
Claude self-corrects better with clear success conditions.
```
"Write tests for scraper.py. Run them and fix failures. Coverage must be >80%."
```
Without verification, you become the sole feedback loop → more context usage.

### 5. **Use CLI tools over API calls**
Tools like `gh`, `git`, `just` are context-efficient.
- `gh pr create` uses cached auth, no rate limits
- `just lint` runs locally, no LLM tokens
Avoid making Claude call APIs that require full context transmission.

## Performance Optimization

### 6. **Scope prompts precisely**
```
"Fix type error in job_ranker/batch/ranker.py:45"
```
vs
```
"Fix the error"
```
Precise scoping reduces file reads and reasoning steps.

### 7. **Leverage caching and immutability**
Job Ranker uses embedding cache (`.mini_ranker_cache/`) and DuckDB.
- Don't re-scrape unnecessarily
- Use `--force-refresh` only when needed
- `just doctor` checks env sanity to avoid wasted runs

### 8. **Batch operations with `--allowedTools`**
For unattended batch processing:
```bash
for f in files/*.py; do
  claude -p "Fix lint in $f" --allowedTools "Edit,Bash(ruff *)"
done
```
Limiting tools reduces decision overhead and safety checks.

### 9. **Configure permissions to reduce interruptions**
After verifying safety, allowlist commands in `.claude/settings.json`:
```json
{
  "permissions": {
    "allow": ["Bash(just *)", "Bash(uv *)", "Bash(pytest *)"]
  }
}
```
 fewer prompts = smoother workflow.

### 10. **Use hooks for repetitive actions**
Automate after every edit via `.claude/settings.json`:
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.file_path // empty' | grep -qE '\\.py$' && just lint 2>/dev/null || true",
        "statusMessage": "Linting...",
        "async": true
      }]
    }]
  }
}
```
Keeps code clean without manual intervention. Already configured in this project's `.claude/settings.json`.

## Job Ranker Specific

### 11. **Respect domain purity**
`domain/` functions must remain pure (no I/O, DB, env). Changing this breaks determinism and testability.

### 12. **Don't enable unnecessary scrapers**
- `jobspy_only: true` avoids RapidAPI rate limits and costs
- `--skip-enrich` avoids LinkedIn 429s (slow, rate-limited)
- SerpAPI free tier: 100/month → use judiciously

### 13. **Run `just check` before commits**
Catch style/type issues early. Prevents context-wasting review cycles.

### 14. **Check `docs/` before modifying ranking**
Architecture docs explain tradeoffs. Read `DESIGN.md`, `AGENTS.md`, invariants.

### 15. **Use `/init` to refresh AGENTS.md**
After structural changes, run `/init` to regenerate AGENTS.md with updated commands and patterns.

## What to Avoid

- **Long-running interactive sessions** → `/clear` every 5-10 exchanges
- **Vague prompts** → "make it better" → 10 rounds of correction
- **Missing verification** → ship broken code, fix later (costlier)
- **Ignoring invariants** → technical debt, debugging hell
- **Parallel scrapes for Indeed** → 403s, wasted tokens/time

## When to Use What

| Task | Recommended Approach |
|------|---------------------|
| Fix lint errors | `just lint` (auto-fix) |
| Add feature across 3+ files | Plan Mode → subagent implementation → review |
| Debug failing test | Provide error output, ask for root cause |
| Onboard to codebase | "Explain @batch/ranker.py scoring pipeline" |
| Large refactor | Break into subtasks, use separate sessions |
| Verify PR | Use subagent: "review for edge cases" |

## Quick Reference

```bash
# Before starting
/claude /init   # Generate AGENTS.md

# During work
<Ctrl+G>        # Enter Plan Mode
<Esc>           # Stop current action
/clear          # Reset context
/undo           # Revert changes

# After changes
just check      # Lint/type check
just doctor     # Verify environment
```

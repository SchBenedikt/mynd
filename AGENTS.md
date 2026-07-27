# Mynd AI Project Context

## Objective
Advance the AI agent architecture toward general superintelligence (AGI/ASI): planning, memory, self-improvement, reasoning, multi-agent delegation, and dynamic knowledge integration.

## Architecture
- **Agent Loop**: `app/agent_loop.py` — two variants: sync `web_agent_loop` and streaming `web_agent_loop_stream` (line 504)
- **LLM Layer**: `core/llm.py` — `chat_with_tools()` (line 38) and `chat_with_tools_stream()` (line 77)
- **Tools**: `core/tools.py` — 40 static tools via `CORE_TOOLS`/`CORE_MAP` pattern (line 1028/1327)
- **Memory**: Simple key-value via `memory_get/set/delete` in `data/plugins/system.py` and `core/tools.py`
- **Knowledge Base**: `app/helpers.py:KnowledgeBase` — hybrid search (semantic + keyword), Reciprocal Rank Fusion, re-ranking, context window enrichment, query expansion (keyword extraction + question trimming)
- **Reflection**: `core/reflection.py` — tool call history, consecutive failure tracking, failure analysis, performance analytics, improvement suggestions, daily summaries, history pruning (in-memory cache + batch flush every 5 writes)
- **Skills**: `core/skills.py` — episodic memory for reusable multi-step patterns with semantic matching (in-memory cache)
- **Sub-Agents**: `core/tools.py:delegate()` — basic sub-agent delegation
- **Planning**: `core/planner.py` — UUID-based plan tracking with steps, verification, progress reporting; persisted in `data/plans.json`
- **Dynamic Tool Creation**: `core/tool_creator.py` — agent writes Python plugins at runtime with AST validation (blocks subprocess, socket, eval, exec, os.system, __builtins__, etc.)
- **Advanced Reasoning**: `core/reasoning.py` — Tree-of-Thought (parallel branches with evaluation), Step-by-Step reasoning with verification, confidence scoring, and reasoning evaluation

## Important Details
- Reflection: in-memory cache + batch flush (every 5 writes) to avoid disk-I/O hangs
- Skills: in-memory cache; learn/recall/list/delete; keyword-based semantic matching; auto-tag extraction from descriptions
- KnowledgeBase: hybrid search combining semantic (cosine similarity) + BM25-like keyword search; Reciprocal Rank Fusion for merging results; re-ranking with term-overlap + position bonus; context-window enrichment (±1 chunk); query expansion (keyword extraction from questions + trimming)
- Tool creation: AST-safe code validation (blocks `ast.Call` + `ast.Attribute` chains, `getattr()` with dangerous args, `sys.modules` access, `__builtins__` references, and 15+ `DANGEROUS_PATTERNS` via normalized code); atomic write via `tempfile.mkstemp` + `os.replace`; max 50000 char code length; system plugins (email, immich, nextcloud) protected from deletion
- Plan tracking: UUID-based plans stored in `data/plans.json`; each step has id/status/result/verified; create/get/update/advance/complete/fail/list/delete operations; progress bar in formatted output
- Agent loops: automatic skill retrieval injected at loop start (wrapped in `<untrusted_data type="skills">` with injection warning); `record_tool_result()` after every tool call; reflection hints injected when ≥2 consecutive failures; `refresh_tools()` for live plugin reload without server restart; context size protection (max 200K chars, 3-level reduction); max 25 tool calls per round; tool results truncated to 4000 chars
- Security hardening: rate limiting (10 calls/s per tool), input length validation (100K char max), hostname validation for SSH, SSRF double-resolve DNS rebinding protection, shell injection pattern blocking (`$(`, backtick, `${`), null byte injection protection, symlink traversal protection via `resolve()`, vault encryption with `cryptography.fernet`
- LLM retry: exponential backoff (1s-16s, 5 retries) on connection errors, timeouts, HTTP 429/5xx; no retry on 400/401/403/404
- Permission mode: reads `MYND_PERMISSION_MODE` env var (defaults to `'semi'`); no longer hardcoded to `'auto'`
- Advanced Reasoning: `core/reasoning.py` — `tree_of_thought()` (generate multiple branches, evaluate, select best path), `reason_step_by_step()` (sequential reasoning with verification per step), `evaluate_reasoning()` (score 0-1 on clarity/correctness/completeness), `confidence_score()` (LOW/MEDIUM/HIGH with gaps); exposed as `reason_deep` and `evaluate_reasoning` tools
- 364+ tests pass, 4 skipped (browser), Ruff clean

## Key Gaps to ASI
- No multi-agent coordination (sub-agents run independently, no aggregation)
- No recursive self-improvement (no code review + patch cycle)
- No planning verification loop (no execute → verify → retry)
- SSH password pipe still broken (issue #98)
- AFFiNE v0.27.2 write endpoints return 404 (CRUD tools export Yjs binary as fallback)

## Work State
### Completed
- **PR #117**: Lint cleanup (279 errors) + AFFiNE shared workspace / CRUD fixes
- **PR #118**: 87 new tests across 6 modules, pytest-cov added
- **PR #119**: AGI/ASI foundation — `core/reflection.py` (self-reflection + failure analysis), `core/skills.py` (episodic memory), hybrid search in KnowledgeBase, reflection + skill injection in agent loops, 78 new tests
- **Deep Planner** (`core/planner.py`): plan creation, step tracking, verification, progress reporting
- **Dynamic Tool Creation** (`core/tool_creator.py`): agent writes + validates + loads Python plugins at runtime
- **Deep Analytics**: tool performance stats, improvement suggestions, daily summaries, history pruning
- **New Tools**: `get_plan`, `update_plan_step`, `list_plans`, `delete_plan`, `analyze_performance`, `get_improvement_suggestions`, `get_daily_summary`, `prune_history`
- **Security Hardening**: input validation (length, null byte, path traversal), SSRF DNS rebinding protection, shell injection pattern blocking, SSH hostname validation, rate limiting (10 calls/s per tool), LLM retry with exponential backoff, message context limit protection (200K chars), max tool calls per round (25), tool result truncation (4K chars)
- **AST Validation Hardening**: blocks `ast.Attribute` call chains (`builtins.exec`), `getattr()` with dangerous string args, `sys.modules` access, `__builtins__` references; normalized code pattern matching catches `eval (` with space; atomic file writes via `tempfile.mkstemp` + `os.replace`
- **Permission Mode Fix**: removed hardcoded `PERMISSION_MODE = 'auto'` in agent loop; reads `MYND_PERMISSION_MODE` env var (default `'semi'`)
- **Bypass Logic Fix**: removed auto-SSH/HTTP execution in think-loop bypass; removed auto-IP extraction from user messages; removed credential auto-extraction from messages
- **In-memory caching fix**: for reflection + skills modules (eliminates disk I/O on every call)
- **116 new tests**: planner module (29 tests), reflection analytics (25 tests), security hardening (11 tests), security boundaries (9 tests), tool wrappers (79 tests) — 341 total
- **Advanced Reasoning** (`core/reasoning.py`): Tree-of-Thought (parallel branches + evaluation + selection), Step-by-Step (with per-step verification), evaluation scoring, confidence analysis; exposed as `reason_deep` + `evaluate_reasoning` tools — 23 new tests

## CI Status
- 364 tests pass, 4 skipped (browser), Ruff clean
- `python3 -m pytest --ignore=tests/test_plugin_affine.py`
- `ruff check`

## Relevant Files
- `app/agent_loop.py` (908 lines): main agent loops (sync + streaming) — reflection injection, skill injection, tool result tracking, context size enforcement, bypass logic
- `core/llm.py`: `chat_with_tools()` + `run_tool_loop()` — LLM interaction layer with retry + backoff
- `app/helpers.py` (17+): KnowledgeBase — hybrid search RAG with query expansion, re-ranking, context enrichment
- `core/reflection.py`: tool history, failure analysis, performance analytics, improvement suggestions, daily summaries, history pruning
- `core/skills.py`: episodic memory — learn/recall/list/delete reusable multi-step patterns
- `core/planner.py`: plan tracking — create/get/update/advance/complete/fail/list/delete plans with verification
- `core/tool_creator.py`: dynamic tool creation — AST-validated plugin generation at runtime
- `core/tools.py` (1358 lines): 40 tools via CORE_TOOLS/CORE_MAP pattern; input validation, rate limiting, SSRF protection
- `core/reasoning.py`: Tree-of-Thought, Step-by-Step reasoning, evaluation scoring, confidence analysis
- `data/plugins/`: plugin directory for auto-generated tools
- `data/plans.json`: persistent plan state
- `data/reflections.json`: persistent tool-call history (batch-flushed)
- `data/skills.json`: persistent skill store
- `tests/test_core_planner.py`: 29 tests for plan creation/tracking/management
- `tests/test_core_tools_wrappers.py`: 79 tests for all tool wrapper functions
- `tests/test_security_hardening.py`: 10 tests for SSRF, shell injection, XSS, null byte
- `tests/test_security_boundaries.py`: 9 tests for symlink traversal, rate limiting, context limit
- `tests/test_core_reasoning.py`: 23 tests for Tree-of-Thought, Step-by-Step, evaluation, confidence scoring

# Codex MCP Degradation Adaptation Implementation Plan

> **For agentic workers:** Execute inline in the current Codex task; do not introduce the upstream control plane or delegate implementation.

**Goal:** Selectively port honest pre-call MCP degradation and host-neutral cheap-research fallback semantics into the Codex branch.

**Architecture:** Keep the existing prompt-layer MCP workflow and Codex state runtime unchanged. Add a contract lint that guards the agreed vocabulary and forbidden Claude-specific fallback, then update all active rule surfaces to describe the same three outcomes.

**Tech Stack:** Markdown contracts, Python `unittest`, existing `tools/lint_codex_contract.py`.

## Global Constraints

- No `.mcp_gate_trace.jsonl`, gate catalogs, metadata fields, new commands, or MCP servers.
- Business eligibility is independent from tool exposure.
- A directly visible tool must be called; an unexposed tool must not be represented as an attempted call.
- Fallback text must not bind Codex to a specific agent API or model name.

---

### Task 1: Add regression contracts

**Files:**
- Modify: `tools/lint_codex_contract.py`
- Modify: `tests/test_codex_contract.py`

**Produces:** A lint rule that rejects `Agent(model="haiku")`/“Claude 家族最便宜模型” in active MCP fallback surfaces and requires `unavailable_before_call` in the four contract truth sources.

- [ ] Add a failing unit test for host-specific fallback text.
- [ ] Add a failing repository contract test for missing three-state markers.
- [ ] Run `python3 -m unittest tests.test_codex_contract -v` and confirm the new checks fail before documentation changes.

### Task 2: Align MCP fallback semantics

**Files:**
- Modify: `SKILL.md`
- Modify: `references/thinking_core.md`
- Modify: `references/mcp_per_step.md`
- Modify: `references/anti_laziness.md`
- Modify: `references/mcp_integration.md`
- Modify: `steps/fast.md`
- Modify: `mcp/cheap-research/README.md`

**Produces:** One Codex-compatible three-state contract and host-neutral cheap-research fallback wording.

- [ ] Separate business eligibility from runtime availability.
- [ ] Document `called`, `degraded_after_attempt`, and `unavailable_before_call` consistently.
- [ ] Make tool discovery conditional on facilities exposed by the current host.
- [ ] Replace Claude-specific Agent fallback wording without changing cheap-research's internal model examples.
- [ ] Run the targeted contract test until it passes.

### Task 3: Verify repository behavior

**Files:**
- No additional production files.

**Produces:** Evidence that the selective port does not alter commands, state, crosscheck, or MCP installation behavior.

- [ ] Run `python3 tools/lint_codex_contract.py .`.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
- [ ] Run the existing shell contract/self-check scripts applicable to Codex and crosscheck.
- [ ] Inspect `git diff --check`, `git diff --stat`, and the final diff for accidental upstream control-plane imports.

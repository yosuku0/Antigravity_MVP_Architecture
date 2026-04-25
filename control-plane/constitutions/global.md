# Global Constitution — All Agents
## Mandatory Invariants

1. **No production merge without CEO (Higurashi) approval.**
   - All code changes must pass HITL Gate 2 before `memory/working/` → source code.
2. **No hardcoded secrets in source code.**
   - API keys, passwords, tokens must live in `.env` only.
3. **HITL is mandatory, not optional.**
   - Gates 1, 2, 3 cannot be bypassed by any automation.
4. **Single crew per job.**
   - No nested crew spawning. Max execution depth: 1.
5. **Hermes memory is never canonical.**
   - `runtime/hermes/` is tactical only; `wiki/` is Source of Truth.
6. **Idempotent operations preferred.**
   - All file writes must be atomic. All promotions must be append-only.

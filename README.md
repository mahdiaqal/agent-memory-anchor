# AgentMemoryAnchor

A GenLayer primitive for append-only semantic memory evolution. Owners anchor a scoped memory, propose immutable child versions, and use independent validator comparison to classify meaning, scope, constraints and ambiguity.

Deterministic rules produce `ACCEPT_UPDATE`, `ACCEPT_FORK`, `REVIEW` or `REJECT`. Safe updates advance only their exact scope head; disjoint contexts create forks; sensitive contradictions require explicit owner review. Every version stores a parent-bound content fingerprint, and no free-form LLM output enters state.

## Consensus invariant

Every validator independently reconstructs the complete categorical compatibility vector and candidate fingerprint from the same immutable parent/proposal pair. Exact equality is required. The leader cannot choose the final disposition.

## Safety properties

- Versions and evaluations are immutable.
- Context heads are isolated by anchor plus normalized scope.
- Ambiguous or unknown semantics never auto-activate.
- High/critical-sensitivity contradictions never auto-activate.
- Human override is explicit and preserves the consensus evaluation.
- Exactly one Python file is discoverable as contract source.

Validation: `genvm-lint check contracts/AgentMemoryAnchor.py`, `npm test`, `npm run check:surface`.


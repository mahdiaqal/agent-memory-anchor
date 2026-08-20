# Architecture

`create_memory_anchor` creates an immutable root version and scoped active head. `propose_memory_update` freezes a child candidate. `evaluate_update` obtains exact validator agreement on bounded semantic relations, then deterministic code activates a safe update/fork or routes it to review/rejection. `resolve_review` records an explicit owner decision without erasing the consensus result.

This contract stores semantic state transitions, not embeddings, summaries, or similarity scores.


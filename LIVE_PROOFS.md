# StudioNet live proofs

Exact deployed source: `contracts/AgentMemoryAnchor.py` at commit `144fb8b`  
Source SHA-256: `6bf7a37d2a81f8d5e26ec665eb38a02ef61e97ac9a32bbd5820d4a7ce82170ec`

- Contract: https://explorer-studio.genlayer.com/address/0xfd9e90544e30E6eB88d52aD7Ff6DB5De7dF0B373
- Deployment: https://explorer-studio.genlayer.com/tx/0x35a250fd45844c62e15f989824ab339aadb9e20a65f0fde784c95f8e14fa3566
- Root anchor: https://explorer-studio.genlayer.com/tx/0x837e4ac6dff3cf41809042e48a05b51a237e1a62f4c013302ec3174f04ff8083
- Safe evaluation: https://explorer-studio.genlayer.com/tx/0xe3eafa06fb15cadf84601e57c45664f7079bce492cb2c5bbc8225cbb0750441a
- Disjoint-scope evaluation: https://explorer-studio.genlayer.com/tx/0xa6e3d972bb3cce3fe038cd0eee8ca5abc9227f893af2878dea7c984e7258970a
- Contradiction evaluation: https://explorer-studio.genlayer.com/tx/0x796786de83f5c4f13bf68a01c4df22cc05fcf4f1274b16c6086686352f1e886b

Every listed write finalized with majority agreement. The safe refinement stored `REFINED / SAME / STRENGTHENED / CLEAR`, activated `safe-v2-portal-0820`, and passes its integrity check. The disjoint travel case stored `UNRELATED / DISJOINT / UNKNOWN / CLEAR` as `REVIEW` and created no travel head. The leveraged-crypto mutation stored `CONTRADICTED / SAME / CONFLICT / CLEAR` as `REVIEW` and did not replace the safe retirement head.

Final state: root and safe-version integrity checks are `true`; retirement head is `safe-v2-portal-0820`; reviewed candidates never become active memory. Reproduce reads with `npm run read:proofs`.

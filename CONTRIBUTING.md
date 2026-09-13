# Contribution workflow

Work in small, reviewable milestones. The GenAI, agentic, LLM, RAG, and conversational components lead the project; every supporting component must have a justified operational purpose.

1. Start with the next milestone in `docs/ROADMAP.md`.
2. Use a focused branch such as `feat/text-task-clarification`.
3. Implement one coherent capability and its meaningful validation.
4. Record observed behavior, limitations, and reproducibility instructions.
5. Update capability status and documentation in the same change.
6. Review before merging; do not overwrite unrelated work or force-push shared history.

Do not commit credentials, private warehouse records, raw operator recordings, generated caches, or model weights. Use synthetic fixtures with documented provenance. Keep deterministic numerical checks outside the LLM. Distinguish implemented, experimental, and planned features explicitly. No software license has been selected yet.

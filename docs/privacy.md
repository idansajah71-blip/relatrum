# Privacy

- API keys server-side only; never exposed to frontend.
- Uploaded documents treated as untrusted input; no execution.
- Workspace scoping enforces tenant isolation.
- Original documents and versions preserved; audit append-only.
- Sensitive data not logged; AI prompts not permanently stored by default.
- Mock mode processes locally; external providers require explicit config.
- Use synthetic data for demos; do not upload real personal data without authorization.

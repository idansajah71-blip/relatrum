# Privacy

- API credentials are server-side only; never exposed to the frontend or client bundle.
- Uploaded documents are treated as untrusted input; no execution, path traversal protection, MIME/size validation.
- Workspace scoping enforces tenant isolation; non-members receive 404 to hide existence.
- Original documents and versions are preserved; historical revisions traceable.
- Audit events and review history are append-only.
- Sensitive data is not included in ordinary application logs; raw prompts are not stored by default.
- Mock mode processes locally; external providers (Gemini/Groq) require explicit configuration and user authorization.
- Use synthetic data for public demonstrations; do not upload real personal data without appropriate authorization.
- Deletion/retention behavior follows cascade rules documented in the data dictionary; destructive actions require confirmation.

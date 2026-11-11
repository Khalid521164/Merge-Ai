# Chat and Live Voice synchronization

## Shared request pipeline

Chat input and Live Voice speech recognition both submit text to
`process_user_turn()` in `app.py`. It delegates answer generation, transcript
persistence, citation storage, and account-memory handling to shared functions.
The model router remains `MergeAI.ask()`; Fast/Deep selection and web-search
settings come from the same Streamlit session state. Kokoro and browser speech
are output adapters around the already-generated assistant answer.

## Context and continuity

`app_context.serialize_conversation()` builds a bounded chronological context
from the active conversation. It prefers recent turns, retains older turns within
the budget, carries safe source URLs forward, and ignores client-supplied file
system paths. The full chat remains persisted in Supabase; the model receives a
bounded context envelope rather than an unbounded transcript.

## Memory and identity

Approved memories remain in the existing Supabase `ma2_memories` table, scoped
by the authenticated Google subject through `CloudHistory`. Both input modes
use the same memory retrieval and opt-in suggestion behavior. No new memory
database is introduced. Anonymous sessions do not read or write account memory.

## Files and documents: current limitation

This repository has no upload interface, file metadata table, object-storage
adapter, or owner-authorized file retrieval API. The synchronization layer will
preserve attachment metadata when it exists, but it cannot yet read PDF, DOCX,
XLSX, or image contents. It deliberately does not trust browser paths or arbitrary
file IDs. Full file parity requires a storage integration that verifies the
authenticated owner's access before returning file bytes to the shared processor.

## Tests

Run `python -m unittest discover -s tests -v`. The tests exercise shared context
serialization and the shared turn helper without API credentials. Actual Google
OAuth, Supabase row-level policies, external search provider calls, and physical
microphone/speaker behavior must be checked in an isolated preview.

## Separate Streamlit preview

1. Create a separate Streamlit app pointing to branch `koko` and entry point
   `app.py`; do not change the production app.
2. Use Python 3.12. Add the existing Supabase and model provider secrets using the
   Streamlit Secrets UI, not source files or chat messages.
3. Register the preview URL as an additional Google OAuth redirect URI where
   required; do not remove the production redirect.
4. Sign in using a test account. Verify chat persistence, Live Voice turn reuse,
   source display, memory opt-in, and Kokoro/browser playback.
5. Do not test cross-account isolation with real user data. Use two disposable
   test accounts and verify each account can only load its own rows.


## Verified project-owner voice identity

Chat and Live Voice now share a verified owner identity context. Configure one
or both of these Streamlit secrets in the deployment settings (never commit
them to the repository):

- `OWNER_GOOGLE_SUBS`: comma-separated Google OAuth subject IDs. This is the
  strongest stable account identifier and does not depend on an email changing.
- `OWNER_EMAILS`: comma-separated Google email addresses. Email matching is
  accepted only when the authenticated Google claim includes
  `email_verified = true`.
- `OWNER_DISPLAY_NAME`: optional name used when addressing the verified owner.

Until at least one allowlist is configured, no signed-in account is treated as
the verified owner. The assistant may describe the project's creator from the
public project facts, but it must not infer that the current speaker is that
creator. A spoken or typed claim such as "I am the owner" never grants access.

Use `owner_auth.require_project_owner(user, secret)` immediately before every
future owner-only backend operation. UI visibility alone is not authorization.
The helper raises `PermissionError` for non-owner accounts. This commit adds
the shared identity context and guard; it does not invent owner-only controls
or enable destructive administrative operations.

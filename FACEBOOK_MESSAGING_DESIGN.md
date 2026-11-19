# Merge AI — Facebook messaging: safe integration design

## Decision: two separate workflows

Merge AI must distinguish a personal Facebook profile from a Facebook Page. They are not interchangeable senders.

### A. Personal Facebook / Messenger — draft and manual handoff only

For a request such as: "Merge, send hi to my dad on Facebook."

1. Detect the user's intent and proposed text.
2. Show the recipient label and exact draft: Dad / Hi!
3. Offer Copy message and Open Messenger.
4. The user chooses the Dad conversation and presses Send in Messenger themselves.

The app will not sign in to a personal Facebook profile, collect passwords/cookies, scrape friends or private conversations, click Send, or claim a message was sent when it was only drafted.

There is no general supported Messenger Platform Send API for sending as a consumer's personal profile to a friend. Keep this manual handoff unless Meta publishes a supported capability for this exact use.

### B. Facebook Page — business inbox replies only

The official Messenger Platform Send API is designed for a Page to respond as that Page to people who contacted that Page. It is not a workaround for sending a personal note from one person to another.

Before any Page reply:
- A project owner configures and controls the Meta developer app and credentials.
- The authorizing person has the Page MESSAGE task.
- The app has the required pages_messaging permission and any other scopes needed by the selected feature.
- The recipient is a valid Page-scoped ID from an inbound Page conversation.
- The recipient has messaged the Page within the standard 24-hour window, or an explicitly permitted opt-in / messaging flow applies.
- The reply is genuinely for the Page's customer-support or business conversation and complies with Meta policies.

Meta policy prohibits using Pages or apps to facilitate person-to-person messaging or relays. Merge AI must not route "tell my dad hi" through a business Page even if the Page API has a message endpoint.

### Confirmation and state model

For every eligible Page reply:
1. DRAFT — no network activity.
2. PREVIEW — show Page identity, recipient/conversation, exact text, and eligibility.
3. USER CONFIRMS — separate click, never inferred from the natural-language command.
4. SEND — server-side request with a Page access token held only in secrets.
5. RESULT — display Meta's message ID on success, or the real error; never report success before Meta confirms.

Allowed states: DRAFT, AWAITING_CONFIRMATION, SENT, FAILED, MANUAL_HANDOFF.

### Credential and privacy rules

- Store App Secret, Page access token, webhook verify token, and signing secrets only in Streamlit secrets / a server-side secret manager.
- Never add secrets to Git, chat logs, source code, client-side HTML, or error messages.
- Verify webhook signatures and OAuth state; validate redirect URIs.
- Use least-privilege permissions and Meta App Review / Advanced Access where required.
- Add disconnect/revoke, audit history, per-account rate limits, and data-retention controls.
- All setup and account authorization must be done by the project owner.

## Current implementation status

This preview branch only documents and displays these two modes. It does not connect to Facebook, access contacts, send messages, or store Meta credentials. Personal Messenger draft handoff and Page inbox replies are future implementation work pending project-owner approval and Meta developer setup.

## Official references

- Messenger Platform Send API: https://developers.facebook.com/docs/messenger-platform/send-messages
- Meta Messenger Platform API collection: https://www.postman.com/meta/messenger-platform-api/documentation/iyp204x/messenger-platform-api
- Page Conversations permissions: https://developers.facebook.com/docs/graph-api/reference/page/conversations
- Meta Developer Policies: https://developers.facebook.com/devpolicy

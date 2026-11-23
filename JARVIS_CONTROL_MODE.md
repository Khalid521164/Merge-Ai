# Merge AI — Jarvis Control Mode (first release)

## What is included

- A **Control mode** entry in the app sidebar and mobile navigation.
- A Start Control screen that asks whether to use a phone or this computer.
- **Phone pairing:** the desktop app creates a cryptographically random 256-bit URL-safe token and a QR code that expires after 10 minutes. The token is stored only as a SHA-256 hash in the shared chat metadata. The phone must sign in with the same Google account and Supabase-backed history enabled.
- The phone opens the same Jarvis conversation and can use the existing Gemini Live voice experience. The desktop can refresh that shared conversation to see the messages.
- **PC mode:** opens a dedicated Jarvis command chat that can coordinate the existing Merge AI features and Agent Team.

## Important capability boundary

This release pairs a phone with a shared Jarvis voice conversation. It does **not** yet control Windows applications, the mouse, keyboard, files, or the operating system. A normal hosted Streamlit page cannot directly control the computer that opened it. That requires a separately installed, locally running desktop companion with a secure relay, explicit user consent, a visible active-session indicator, and an emergency stop.

Do not describe the QR flow as remote desktop control until that companion is implemented and connected.

## Pairing

1. Sign in to Merge AI on the computer with Google.
2. Ensure Supabase cloud history is connected.
3. Open **Control mode → Start Control → Control by phone**.
4. Scan the QR from the phone and sign in with the same Google account.
5. Start the live voice session on the phone. The conversation is stored in the same cloud chat.
6. The QR token expires in 10 minutes. Generate a new QR to rotate it.

Keep the QR private. Anyone who obtains it before expiry and can sign in to the same Google account can join the voice conversation.

## Future desktop companion requirements

Before enabling actual computer actions, implement a signed, short-lived pairing session; outbound encrypted relay; allowlisted actions (never arbitrary shell commands); per-action confirmation for sensitive operations; visible status and an immediate stop button; command audit history; and disconnect/expiry handling. The companion must not expose a local unauthenticated control port.

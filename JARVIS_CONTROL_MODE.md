# Merge AI — Jarvis Control Mode

## What is included

- A **Control mode** entry in the app sidebar and mobile navigation.
- A Start Control screen that asks whether to use a phone or this computer.
- **Phone pairing:** the desktop app creates a cryptographically random 256-bit URL-safe token and a QR code that expires after 10 minutes. The token is stored only as a SHA-256 hash in the shared chat metadata. The phone must sign in with the same Google account and Supabase-backed history enabled.
- The phone opens the same Jarvis conversation and can use the existing Gemini Live voice experience. The desktop can refresh that shared conversation to see the messages.
- **PC mode:** opens a dedicated Jarvis command chat that can coordinate Merge AI, explicitly named specialist agents, and an optional Windows Desktop Bridge.

## Desktop control boundary

The hosted Streamlit page cannot directly control the computer that opened it. Windows control requires the separately installed Desktop Bridge, a pairing file, the user's explicit consent in the companion, a visible active-session indicator, and the emergency stop. Only the bridge's allowlisted application, mouse, keyboard, web-address and screenshot actions are supported. The bridge does not run shell commands, PowerShell, arbitrary executables or file deletion.

The companion must show a fresh heartbeat before Jarvis can queue an action. Jarvis previews every proposed action and waits for approval in the conversation before sending it to the paired PC. Click and Enter actions require a second confirmation because they may submit, send, purchase, delete, or change something. The execution result is copied back into that proposal after the chat refreshes.

## Pairing

1. Sign in to Merge AI on the computer with Google.
2. Ensure Supabase cloud history is connected.
3. Open **Control mode → Start Control → Control by phone**.
4. Scan the QR from the phone and sign in with the same Google account.
5. Start the live voice session on the phone. The conversation is stored in the same cloud chat.
6. The QR token expires in 10 minutes. Generate a new QR to rotate it.

Keep the QR private. Anyone who obtains it before expiry and can sign in to the same Google account can join the voice conversation.

The Windows companion maintains an outbound HTTPS connection to Supabase and does not open a local control port. Pairing details stay in the companion's memory while it is open. The pairing session is linked to the exact Jarvis conversation and is replaced when a new pairing file is generated.

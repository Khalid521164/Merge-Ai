# Merge AI Desktop Bridge

This is a visible Windows companion for the hosted Merge AI app. It enables approved mouse, keyboard, app-launch, scroll, and screenshot commands through an outbound HTTPS connection to Supabase. It does not open a network listener and does not accept arbitrary shell commands.

## 1. Supabase setup

Run the supabase_control_bridge.sql file in the Supabase SQL Editor. This creates private relay tables and three narrowly scoped RPC functions. The tables have RLS enabled and no direct permissions for the anon or authenticated roles; the Windows companion can only call the approved RPC functions with its per-session token hash.

## 2. Streamlit Secrets

Add these keys in Streamlit Community Cloud → App settings → Secrets:

    SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
    SUPABASE_SECRET_KEY = "YOUR_SERVER_SIDE_SUPABASE_SECRET"
    SUPABASE_ANON_KEY = "YOUR_PUBLIC_SUPABASE_ANON_KEY"

Never put the Supabase server secret key in the pairing file or in the Windows companion. Only the public anon key and a short-lived per-session device token are downloaded.

## 3. Build the Windows companion

On a Windows 10/11 PC with Python 3.11 or newer:

1. Download the repository.
2. Run BUILD_DESKTOP_BRIDGE.bat.
3. The program appears at dist\MergeAIDesktopBridge.exe.

You can also run it directly with python desktop_bridge.py.

## 4. Pair

1. Open Merge AI in a full browser tab and sign in with Google.
2. Open Control mode → Start Control.
3. Choose Control by phone or Control on this PC. The PC screen will provide a one-time pairing JSON file.
4. Run MergeAIDesktopBridge.exe, load that pairing file, check the explicit permission box, and press Start secure connection.
5. For phone mode, also scan the phone QR code and sign in with the same Google account.
6. The desktop companion shows a visible ACTIVE status while connected. Press STOP REMOTE CONTROL at any time. Moving the pointer to the top-left corner also activates PyAutoGUI's emergency failsafe.

Pairing config expires after 10 minutes. The active desktop-control session expires after 8 hours. Generate a new pairing file to reconnect.

## Supported actions

- Capture the active monitor (JPEG screenshot).
- Open allowlisted apps: Notepad, Calculator, Paint, File Explorer, Chrome, Edge, and Visual Studio Code.
- Open ordinary HTTP/HTTPS web addresses.
- Move and click at screen coordinates or common screen positions (center/corners).
- Type up to 3,000 characters using the clipboard.
- Press a short allowlisted keyboard shortcut or navigation key.
- Scroll up or down up to 15 steps.

The bridge rejects arbitrary shell commands, arbitrary executable paths, arbitrary keyboard shortcuts, invalid coordinates, oversized text, and non-HTTP(S) URLs. The Merge AI interface must explicitly approve every command before it enters the relay queue.

## Safety and limitations

- Use this only on a computer you own or are authorized to control.
- The bridge window stays visible and has an immediate stop button.
- Do not approve commands that could expose passwords, financial details, private messages, or other sensitive information.
- Screenshots are returned to the Merge AI session only after an approved screenshot command.
- Do not share pairing JSON files; they contain a temporary credential. Delete the downloaded JSON file after loading it into the companion. The companion removes its local saved pairing file when you press STOP or close the window.
- The bridge does not run arbitrary scripts, PowerShell, CMD, shell commands, file deletion, or unattended background tasks.

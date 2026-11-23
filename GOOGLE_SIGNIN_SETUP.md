# Merge AI — Google sign-in and saved agent names

Google sign-in is already wired into `app.py` with Streamlit's `st.login("google")`.
To make it work on Streamlit Community Cloud, configure the private OAuth credentials
in the app's **Settings → Secrets** panel. Do not add these values to GitHub.

## 1. Create or check the Google OAuth client

In Google Cloud Console:

1. Open **Google Auth Platform → Clients**.
2. Create a **Web application** OAuth client (or open the existing Merge AI client).
3. Add this exact **Authorized redirect URI**:

   `https://mergeai.streamlit.app/oauth2callback`

4. Save the client and copy its Client ID and Client secret.

## 2. Add the OIDC secrets to Streamlit Community Cloud

Open the Merge AI app settings, select **Secrets**, and add the following TOML.
Replace the placeholders with the real values from Google Cloud and generate a long,
random cookie secret. Do not reuse the Google client secret.

```toml
[auth]
redirect_uri = "https://mergeai.streamlit.app/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"

[auth.google]
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

The app calls `st.login("google")`, so the named provider configuration
must be under `[auth.google]`.

## 3. Connect account storage

For agent names and custom agent profiles to persist across devices, the app also needs
its existing Supabase server-side secrets in Streamlit Cloud:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

Keep the secret key private. Never paste it into chat, browser code, or GitHub.

## 4. Create the name/agent tables

1. Open your Supabase project → **SQL Editor**.
2. Open the updated `supabase_agents.sql` file in this repository.
3. Run the entire SQL script. It is safe to run again because the tables and indexes
   use `IF NOT EXISTS`.
4. Refresh Merge AI and sign in with Google.

## 5. Assign names

Open **Agents → Personalize agent names**. For example:

- Coding Engineer → Khalid
- Researcher → Ashraf

Click **Save my agent names**. Names are stored against the signed-in Google account,
so each Google account can have its own labels. Agent conversations continue to use
the original specialist instructions and skills.

## Notes

- The app already contains the login button and OIDC login handler. This guide configures
  the credentials required by Streamlit; those private settings cannot be committed to
  this public repository.
- When Google OAuth consent is in Testing mode, only accounts listed as test users can
  sign in. Publish the OAuth app when you are ready for general users.

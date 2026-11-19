# Merge AI — free image generation setup

Merge AI's **Create image** tool uses Cloudflare Workers AI with the FLUX.1 Schnell model.

## Free-plan allowance

Cloudflare Workers AI includes **10,000 neurons per day at no charge** on the Workers Free plan. The allowance is shared with other Workers AI features used by the same Cloudflare account.

Official pricing:
https://developers.cloudflare.com/workers-ai/platform/pricing/

Keep the account on the Workers Free plan. When the daily allowance is exhausted, requests stop until it resets. Do not upgrade to a paid plan unless the account owner separately approves it.

## One-time setup (account owner)

1. Sign in to the Cloudflare dashboard and open **AI → Workers AI**.
2. Select **Use REST API**.
3. Choose **Create a Workers AI API Token**, then create and copy the token.
4. Copy the **Account ID** shown in the Workers AI REST API setup.
5. In the Streamlit Community Cloud settings for the Merge AI app, open **Manage app → Settings → Secrets**.
6. Add the credentials to that exact app's Secrets.

Cloudflare's recommended token template is available from Workers AI → Use REST API. If you create a custom token instead, Cloudflare's REST API guide says it needs **Workers AI – Read** and **Workers AI – Edit** permissions.

Official instructions:
https://developers.cloudflare.com/workers-ai/get-started/rest-api/

## Secrets format

The app accepts either of the following formats.

### Format A — top-level keys

```toml
CLOUDFLARE_ACCOUNT_ID = "your-cloudflare-account-id"
CLOUDFLARE_API_TOKEN = "your-cloudflare-workers-ai-token"
CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
```

### Format B — a cloudflare section

```toml
[cloudflare]
account_id = "your-cloudflare-account-id"
api_token = "your-cloudflare-workers-ai-token"
image_model = "@cf/black-forest-labs/flux-1-schnell"
```

Never put the token in GitHub, source code, screenshots, or chat messages.

## Generate an image

1. Open a Merge AI chat.
2. Press **＋** and choose **Create image**.
3. Describe the image and press **Generate image**.
4. The generated image appears in the chat. Use **Download image** to save it.

Model documentation:
https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

## Troubleshooting

The Create image panel shows only whether each secret is detected, never its value.

- **Account ID missing**: add the account ID to this app's Secrets using either supported format above.
- **API token missing**: add the Workers AI API token to this app's Secrets using either supported format above.
- **401 or 403**: check the account ID and token. For a custom token, check Workers AI Read and Edit permissions.
- **429**: rate limit or free allowance may be exhausted.
- **Other model error**: confirm the model is exactly `@cf/black-forest-labs/flux-1-schnell`.

## Storage behavior

Image bytes are held temporarily in the active Streamlit session. Chat history stores the prompt and an image reference, not the image bytes. If the session ends or the app restarts, the preview may no longer be available.

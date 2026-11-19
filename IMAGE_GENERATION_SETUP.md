# Merge AI — free image generation setup

Merge AI's **Create image** tool uses Cloudflare Workers AI with the FLUX.1 Schnell model.

## Free-plan allowance

Cloudflare Workers AI includes **10,000 neurons per day at no charge** on the Workers Free plan. The allowance is shared with any other Workers AI features used by the same Cloudflare account and resets at 00:00 UTC.

Keep the account on the **Workers Free** plan. When the daily allowance is exhausted, requests stop until it resets. Do not upgrade to a paid plan for this project unless the account owner separately approves it.

Official pricing:
https://developers.cloudflare.com/workers-ai/platform/pricing/

## One-time setup (account owner)

1. Sign in to the Cloudflare dashboard and open **Workers AI**.
2. Select **Use REST API**.
3. Choose **Create a Workers AI API Token**, then create and copy the token. Cloudflare's generated token has the permissions needed for Workers AI. If creating a custom token, Cloudflare documents the required Workers AI permissions.
4. Copy the **Account ID** shown in the Workers AI REST API setup.
5. In the Streamlit Community Cloud dashboard for the Merge AI preview app, open **Settings → Secrets**.
6. Add the following values:

```toml
CLOUDFLARE_ACCOUNT_ID = "your-cloudflare-account-id"
CLOUDFLARE_API_TOKEN = "your-cloudflare-api-token"
CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
```

Never put the API token in GitHub, source code, a screenshot, or a chat message. Only the account owner should create and add this token.

Cloudflare's official REST API setup:
https://developers.cloudflare.com/workers-ai/get-started/rest-api/

Model documentation:
https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

## Generate an image

1. Open a Merge AI chat.
2. Press **＋** and choose **Create image**.
3. Describe the image and press **Generate image**.
4. The generated image appears in the chat. Use **Download image** to save it.

## Important notes

- The image model runs through Cloudflare; it does not use the paid Gemini image API.
- The app makes four-step FLUX.1 Schnell requests for faster generation.
- The 10,000-neuron daily allowance is shared with the rest of the Cloudflare account's Workers AI usage.
- On the Workers Free plan, generation stops when the free daily allowance is used up. There is no automatic paid fallback.
- Image bytes are held temporarily in the active Streamlit session. The chat stores the prompt and an image reference, not the image bytes. If the session ends or the app restarts, the image preview may no longer be available.

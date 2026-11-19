# Merge AI image generation setup

## What it does

The **Create image** tool sends the description to the Gemini image-generation API, displays the returned picture in the chat, and provides a Download image button.

The default model is `gemini-3.1-flash-lite-image`. The account owner can override it with `GEMINI_IMAGE_MODEL`. The integration uses Google's current Gemini Interactions API.

## Important: billing and permission

Image generation is separate from ordinary text chat. Google currently lists no free tier for Gemini 3.1 Flash Lite Image, and API usage can create charges. The account owner should review the current pricing and Google AI Studio billing settings before enabling this feature:

https://ai.google.dev/gemini-api/docs/pricing

The feature is **off by default**. Do not enable it unless the account owner approves the possible charges.

## Enable it

In the Streamlit app's Secrets settings, the account owner should add:

```toml
ENABLE_IMAGE_GENERATION = "true"
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
```

The existing `GEMINI_API_KEY` secret must also be present and have access to the Gemini API.

To turn the feature off again, set `ENABLE_IMAGE_GENERATION = "false"` or remove that setting.

## Use it

1. Open a chat and press the **＋** button.
2. Choose **Create image**.
3. Describe the picture.
4. Press **Generate image**.
5. View the image in the chat and choose **Download image** to save it.

## Storage behavior

Image bytes are kept temporarily in the active Streamlit browser session. Chat history stores the prompt and a reference to the image, not the image bytes. This avoids sending large image files to Supabase. If the browser session ends or the app restarts, the preview may no longer be available, but the prompt remains in chat history.

Only the image-generation prompt is sent to Google for this request. The normal Groq and OpenRouter text-answer pipeline is not used.

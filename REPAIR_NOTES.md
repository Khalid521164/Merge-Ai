# Merge AI: final answers and Kokoro voice

## What was actually found

The inspected GitHub `main` commit was `98178058da234c3e23b26ce2a0903584f8781c30`.

* `kokoro_tts.py` and `packages.txt` were absent. `requirements.txt` contained only the web-app dependencies. `app.py` explicitly passed `kokoro_available=False` and set every voice reply's `audio_b64` to an empty string. Consequently this revision could never generate or deliver Kokoro audio, regardless of microphone permissions. There was no Kokoro model-loading attempt to diagnose in this code path. The remaining `elevenlabs_tts.py` was unused.
* There was no regular-chat Listen control in this revision. The repair adds that small control without changing the surrounding layout.
* Fast mode called `collect_drafts()` and waited for all enabled providers, then selected one result. It paid the multi-provider latency without performing synthesis.
* The output guard mainly matched the word “draft”; it accepted “Gemini says … Groq says …” and provider comparison tables without that word.
* Deep-mode synthesis failure returned an arbitrary draft, even if candidates disagreed. Direct-answer recovery discarded conversation context. The input cutoff could discard the latest question. The UI also discarded source links because the engine returned a string and the UI never read that request's source report.
* `engine()` was a shared Streamlit resource with mutable `last_report`. It is now a lightweight per-request engine so source reports cannot cross sessions. No chat or memory tables were changed.

GitHub exposed no Actions runs, check runs or commit-status logs. The deployed app was inspected as an anonymous visitor; Streamlit's private management/server logs were unavailable. A factual rain question on the original live app did return a coherent answer. Therefore the reported failure is intermittent for synthesis, and this report does **not** claim that a live Streamlit traceback, an out-of-memory event, or a production Python-version mismatch was observed.

## Repair behavior

Fast mode tries the preferred provider first and falls back only on failure or rejected output. Deep mode obtains candidates concurrently, then requests one synthesis with conversation context and web evidence. Candidates are explicitly suggestions, not evidence; unresolved conflicts must be expressed as uncertainty. Failed synthesis does not silently promote one conflicting candidate. Normal output never concatenates candidates, and only validated final content reaches the UI. Greetings bypass paid APIs. Creator questions return “Merge AI was created by Khalid.” Requested public comparisons and ordinary tables/code remain supported.

Brave/Tavily routing, existing model IDs, account/memory behavior, sidebar, green logo, CSS and blue voice modal are retained. OpenRouter participates when its key is configured unless `ENABLE_OPENROUTER="false"` is explicitly set. Provider failures are logged by type/status without exposing raw responses, keys or personal context.

Both Listen and Live Voice use Kokoro `am_liam`, American English, at speed `1.03`. A single CPU pipeline is reused, inference is bounded, and cached model files load without network checks. Audio is one validated mono 24 kHz, 16-bit WAV, with excess boundary silence shortened. Live Voice prepares speech in the background, so the final text can appear immediately. Playback resumes recognition after speech; mute/end stops audio. Autoplay restrictions expose a manual Play button. Missing speech, unsupported languages or playback failures retain browser speech. No transcripts/audio are stored in a global cache or written to Supabase.

## Streamlit Cloud installation

1. Review and merge this repair branch into `main`. Keep the current Streamlit app pointed at `Khalid521164/Merge-Ai`, branch `main`, entry point `app.py`.
2. **Use Python 3.12.** The published `kokoro==0.9.4` package requires Python below 3.13. Check the deployment Python version before merging. If the existing Cloud app needs a runtime change, follow Streamlit's documented Python-upgrade/redeployment flow and preserve the existing app URL and authentication configuration.
3. Keep **all existing Google, Supabase, Gemini, Groq, OpenRouter, Tavily and memory secrets unchanged**. No new API key is required for local Kokoro. Optional root-level secrets are:

   ```toml
   KOKORO_ENABLED = "true"
   ENABLE_OPENROUTER = "true" # only if the configured account/model is usable
   ```

4. Cloud installs `requirements.txt` and Debian packages from `packages.txt`. The requirements select CPU PyTorch, not a CUDA installation. The English spaCy model is installed at build time. Model weights and the Liam voice download from the official Hugging Face repository on first use.
5. Reboot the app after dependency installation. The first voice request may need time to download the model; ordinary chat remains usable and browser speech is the fallback. Subsequent inference reuses the model. Do not treat “configured” as proof that downloading/loading has completed.
6. Open **Manage app → logs** while signed in to Streamlit Community Cloud. Look for `Kokoro loading`, `Kokoro ready`, `Kokoro generated`, or `Kokoro local failed`. Failure logs identify the stage/exception type without logging the user's text. Check build logs for dependency-install errors. Keep keys and auth cookies out of any shared log excerpt.
7. Verify: “Hi”; “What causes rain?” in Fast and Deep; “Why do those droplets grow?”; “Who created Merge AI?”; a coding question; a legitimate comparison. Check citations with web search enabled. Then test Listen and Live Voice in a browser that supports speech recognition. Confirm one final answer, audible speech, and microphone resumption after playback. Finally verify Google sign-in and an existing saved chat/memory on a second device.

Official references: [Kokoro package/Python support](https://pypi.org/project/kokoro/0.9.4/), [Kokoro source](https://github.com/hexgrad/kokoro), [Liam voice listing](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md), [PyTorch CPU installation](https://pytorch.org/get-started/previous-versions/), [Streamlit logs and resource limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app), [changing Cloud Python](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python).

## Local installation and checks

Windows PowerShell, from the repository folder (install Python 3.12 first):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m kokoro_tts --output kokoro-smoke.wav
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Install eSpeak NG from its official Windows distribution for system phonemization if needed; the English phonemizer also ships its library through `espeakng-loader`. On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y espeak-ng libespeak-ng1
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m kokoro_tts --output kokoro-smoke.wav
python -m streamlit run app.py
```

Play `kokoro-smoke.wav` in your audio player. Do not run Python 3.14 for this pinned Kokoro environment. Keep local credentials in the existing ignored `.streamlit/secrets.toml`, never in committed Python files. The unit suite mocks paid providers and inference; it does not need API keys. Optional browser check:

```bash
python -m pip install playwright
python -m playwright install chromium
# Supply the installed Chromium executable path:
python tests/voice_browser_check.py --chromium /path/to/chromium --wav kokoro-smoke.wav
```

## Separate TTS service for limited-memory hosting

Local Kokoro is supported, but free Streamlit resources are variable. Measured local peak RSS reached approximately **1.6 GiB** in a standalone Python process; this is not a measurement of the production Streamlit deployment. A dedicated TTS host with at least 4 GiB RAM is a practical starting point, to be load-tested for the actual audience.

The included optional `tts_service.py` hosts the **same Kokoro code**, with a warm model, bearer authentication, request limits, one inference worker, no browser credentials and no transcript storage. `/healthz` becomes ready after model warmup. Streamlit sends the final answer from its server to `/v1/audio/speech` and receives WAV bytes. Use HTTPS at the service's reverse proxy/platform. This service is an alternative deployment option, not an automatically provisioned or tested cloud deployment.

```bash
docker build -f Dockerfile.tts -t merge-ai-kokoro .
# Supply a random secret of at least 32 characters via the host's secret manager.
docker run --env-file /secure/path/kokoro.env -p 127.0.0.1:8000:8000 merge-ai-kokoro
```

`kokoro.env` contains `KOKORO_TTS_API_KEY=<random-secret>`. Never commit that file. The service container runs as a non-root user. Keep exactly one Uvicorn worker to avoid duplicating the model in RAM; keep a persistent Hugging Face cache or a warm instance to avoid repeated cold downloads. Put a request-size limit, request timeout and rate limit on the public HTTPS reverse proxy. For a non-Docker host install `requirements-tts-service.txt` and run:

```bash
python -m uvicorn tts_service:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Set only these **server-side Streamlit secrets** after that service is ready:

```toml
KOKORO_TTS_URL = "https://YOUR-TTS-HOST"
KOKORO_TTS_API_KEY = "SAME-RANDOM-SERVICE-SECRET"
```

Remote mode does not load local PyTorch. To also avoid installing it on Streamlit, replace the root `requirements.txt` contents with `-r requirements-base.txt` in that deployment. Keep the full CPU requirements on the TTS host. No changes to Google authentication, Supabase or the website layout are needed.

## Rollback

* Quick voice fallback: set `KOKORO_ENABLED="false"` in Streamlit Secrets and reboot. The answer-synthesis repair remains active and browser speech continues.
* Full code rollback: use **Revert** on the merged repair pull request and merge the revert, then reboot Streamlit. Restore any deployment-only Python/dependency settings from your pre-deployment notes. Do not reset the database or delete/recreate Supabase tables.
* The exact pre-repair source is commit `98178058da234c3e23b26ce2a0903584f8781c30`. Prefer reverting the repair commit over resetting `main`, so later unrelated commits are preserved.
* For remote TTS, remove `KOKORO_TTS_URL`/`KOKORO_TTS_API_KEY` to return to local mode, or disable Kokoro for browser-only speech. Restoring local mode also requires the full `requirements.txt` dependencies.

See `VALIDATION.md` for performed checks and remaining production checks.

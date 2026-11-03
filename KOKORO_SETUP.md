# Kokoro voice setup for Merge AI

This change is developed on `koko`, based on `98178058da234c3e23b26ce2a0903584f8781c30`.
Review the `koko` → `main` pull request before approving a production merge. Nothing
in this change requires a database migration or deletion of chats.

## Cause found in the repository

The inspected branch had no `kokoro_tts.py`, no Kokoro/PyTorch dependencies, and no
`packages.txt`. `app.py` passed `kokoro_available=False` and an empty audio payload
to Live Voice. There was no ordinary chat Listen implementation. Consequently the
frontend could never receive Kokoro audio, independently of any hosting problems.

No private Streamlit deployment logs were available during this work, and the
repository had no GitHub Actions runs. A production out-of-memory crash, failed
model download, or dependency-install error has **not** been verified. Do not
diagnose one from the old fallback label alone.

## Files and behavior

| File | Change |
| --- | --- |
| `app.py` | Targeted voice integration: final answer → asynchronous audio job → Live Voice; Listen on assistant messages; audio scoped to account/chat. |
| `voice_chat.py` | Existing HTML/CSS preserved. Kokoro stays selectable; request IDs prevent stale/duplicate playback; mute/end stop speech; microphone resumes after speech. |
| `requirements.txt` | Original requirements preserved; includes `requirements-kokoro.txt`. |
| `kokoro_tts.py` | New shared CPU model loader, cached assets, bounded inference, WAV validation, asynchronous delivery and safe errors. |
| `voice_text.py` | New deterministic speech cleanup; full written answer stays in the chat. Internal provider commentary is blocked at the speech boundary. |
| `voice_config.py` | New defaults and validated server-side overrides. |
| `listen_button.py` | New small Listen/Stop control using the same backend and browser fallback. |
| `requirements-kokoro.txt` | New compatible CPU dependency set, including the English phonemizer data. |
| `packages.txt` | New `espeak-ng` and `libespeak-ng1` system dependencies. |
| `tests/test_kokoro.py`, `tests/test_voice_text.py` | New lightweight unit tests. |
| `tests/voice_browser_check.py` | New opt-in Chromium integration checks with simulated speech input and AI calls. |
| `KOKORO_SETUP.md` | This guide. |

`merge_ai.py`, identity instructions, provider routing, Fast/Deep modes, search,
Google authentication, cloud history and personal-memory modules are unchanged.
Every original top-level function in `app.py` is unchanged. This PR does not repair
or replace the existing final-answer algorithm: only its returned final answer is
handed to speech. Raw provider drafts/comparison tables are rejected by both voice
paths; they are not silently read with browser speech instead.

## Dependencies and Python version

Use **Python 3.12**. The installed metadata for Kokoro 0.9.4 requires Python
`>=3.10,<3.13`; Python 3.13/3.14 will fail this pinned installation.

The tested inference stack is Kokoro 0.9.4, Misaki English 0.9.4, CPU PyTorch
2.9.1, Transformers 4.57.6, NumPy 2.3.5 and `en_core_web_sm` 3.8.0. Existing
Streamlit, requests, Authlib and httpx requirements are retained. The English spaCy
model installs during dependency installation instead of downloading during a
voice turn. Linux/Windows use the PyTorch CPU wheel index; macOS uses its standard
PyTorch wheel. Intel/ARM wheel availability depends on the platform; only Linux
CPU inference was executed here.

Kokoro uses Misaki for pronunciation. The English extra includes phonemizer-fork
and espeakng-loader; system eSpeak NG is also declared for the Linux deployment
and out-of-dictionary pronunciation fallback. The official Kokoro example uses
SoundFile to write WAVs. This implementation uses Python's standard `wave` module,
so neither SoundFile nor libsndfile is required for our output encoder. Real WAV
generation passed in an environment without SoundFile installed.

References: [Kokoro usage](https://pypi.org/project/kokoro/0.9.4/),
[Kokoro source](https://github.com/hexgrad/kokoro).

## Local installation

Clone the existing repository and use the development branch:

```sh
git clone https://github.com/Khalid521164/Merge-Ai.git
cd Merge-Ai
git switch koko
```

On Debian/Ubuntu with Python 3.12 installed:

```sh
sudo apt-get update
sudo apt-get install -y espeak-ng libespeak-ng1
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m kokoro_tts --output kokoro-smoke.wav
.venv/bin/python -m streamlit run app.py
```

On Windows PowerShell, with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m kokoro_tts --output kokoro-smoke.wav
Start-Process .\kokoro-smoke.wav
.\.venv\Scripts\python.exe -m streamlit run app.py
```

These Windows commands do not require activating a PowerShell script. If native
eSpeak loading fails on Windows, install the matching Windows build from the
[official eSpeak NG releases](https://github.com/espeak-ng/espeak-ng/releases)
and retry the smoke test. Windows installation/playback was not executed here.

The smoke command speaks exactly:

> Hello! I'm Merge AI, created by Khalid. How can I help you today?

For another sentence, call `kokoro_tts.synthesize("Your new sentence.")`; it returns
WAV **bytes**. Never pass a filename or provider-response dictionary in place of the
final answer. Models/voice files are downloaded from public Hugging Face assets on
first use; no Kokoro API key is needed. Keep the Hugging Face cache writable and
allow outbound model downloads. Do not commit the cache, audio, virtual environment
or your local `.streamlit/secrets.toml` to GitHub.

## Optional settings

Defaults need no new secrets. Values can be set as environment variables or at the
top level of Streamlit Secrets; Secrets win when both are present.

```toml
KOKORO_ENABLED = true
VOICE_NAME = "am_liam"
VOICE_SPEED = 1.03
KOKORO_THREADS = 2
BROWSER_FALLBACK = true
```

American English (`a`) and mono 24,000 Hz PCM16 WAV output are fixed. Voice names
must be American Kokoro voice identifiers; the default is Liam. Speed is bounded
to 0.5–2.0 and CPU threads to 1–4. Invalid settings use defaults without logging
their supplied values. `HF_HOME` can select a writable model-cache directory.

The existing language selector remains available. This Kokoro voice supports
English; other selected languages use browser speech. Browser speech also remains
an explicit user choice. If automatic browser fallback is disabled, unavailable
audio shows a status instead of speaking. Browser recognition/voices vary by
device and can use the browser vendor's servers.

## Streamlit Community Cloud rollout

1. Review the PR. For a safe trial, deploy a **separate preview app** from branch
   `koko`, entry point `app.py`, using Python **3.12** in Advanced settings.
2. Preserve the production app and its existing authentication/database secrets.
   Copy only the settings required for the preview through Streamlit's Secrets
   interface, never GitHub. OAuth on a different preview URL requires its own
   allowed redirect URL; do not replace the production redirect URL.
3. Community Cloud reads `requirements.txt` and `packages.txt` from the repository.
   Inspect the installation logs, open a normal chat, then try Listen and Live
   Voice. The first voice request loads the model; ordinary chat does not load it.
4. If testing the signed-in path, use a test account and verify history and memory
   without deleting production data. A preview using the production database can
   create real test-account records; no schema changes are needed.
5. Merge into `main` **only after Khalid approves**. Confirm the production app's
   Python version before merging. Dependency changes trigger a rebuild on the
   connected branch. Changing Python on an existing Cloud app can require a new
   deployment; follow [Streamlit's Python-version guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python)
   and preserve the original deployment until the replacement is verified.

Do not paste API keys into chat, source files, PR descriptions, or logs.

## Hosting capacity and performance

The model is loaded once per Python process and reused by Live Voice and Listen.
Cached model assets are checked locally before a network request. A single
inference worker and two bounded delivery slots prevent simultaneous model copies
and an unbounded queue. Busy requests can fall back to browser voice. Audio/text
are not cached globally; only one latest Live Voice result and one latest Listen
result are retained per session. Account/chat changes discard those results.

Measured here on Linux/Python 3.12 with an existing model-file cache:

| Check | Result |
| --- | --- |
| First required greeting, including loading | 13.97 seconds |
| Model initialization within that request | 9.21 seconds |
| New rain explanation, model reused | 4.00 seconds for 4.81 seconds of audio |
| New Tokyo/numeric sentence, model reused | 3.30 seconds for 4.69 seconds of audio |
| Peak process RSS in that smoke run | 1,536 MiB |
| Model weights / Liam voice | About 312 MiB / 0.5 MiB on disk |

These are local observations, **not** guaranteed Streamlit timings. A fresh model
download was not timed in this run. Installation and model downloads need network
access and additional disk space. Application/session memory adds to the model's
measured usage.

[Streamlit documents variable resource limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#resource-limits)
and warns that they can change. Its published approximate historical range is
690 MB–2.7 GB memory and up to 2 CPU cores; that is not a reservation for this app.
The measured 1.5 GiB process is too large for the low end of that range. Production
capacity, cold startup, concurrent sessions and latency therefore need a preview
check before claiming reliable Cloud hosting. A process killed by the host cannot
be caught by Python's fallback handler.

There is no evidence from accessible production logs that an external TTS host is
necessary yet, so this PR does **not** add a server, client, Docker deployment or
new hosting bill. If the preview logs establish repeated OOMs or unacceptable
throttling, the next deployment should isolate the same warmed Kokoro backend in
one CPU API worker on a host with measured memory headroom (start testing at
4 GiB), use an authenticated HTTPS endpoint called only by Streamlit's Python
backend, and keep credentials server-side. Bound request size/concurrency, reject
invalid WAVs, retain browser fallback and disable request-body logging. That
conditional service needs its own integration tests and deployment review; it is
not implemented or required for this local repair. Compute, storage, egress and
availability would depend on the chosen host; free continuous hosting is not
guaranteed. No service has been purchased or deployed.

## Loading, fallback and diagnostics

The full final text appears before audio is ready. Live Voice then displays
`Preparing Kokoro voice…`; ordinary Listen shows `Preparing voice…`. Muting,
closing, changing language, or switching chats prevents late audio from starting.
Autoplay denial offers **Play answer** rather than pretending the model failed.

For bounded resource usage, synthesis waits at most 120 seconds while cold or
90 seconds while warm. A timed-out inference retains the worker slot until it
actually finishes, so retries cannot create additional simultaneous models. A
failure starts a 30-second recovery interval. Audio longer than 10 minutes is
rejected as a whole and uses the full speech text for browser fallback; it is never
silently cut short. Speech cleanup skips code blocks/URLs but preserves prose and
numbers. Neither voice cleanup nor failure modifies the saved answer.

While signed in to the owning Streamlit workspace, open the app and select
**Manage app → logs**; the log menu offers **Download log**. Look for build failures
first, then `Kokoro loading`, `Kokoro ready`, `Kokoro generated`, or `Kokoro failed`.
The backend logs timings, byte counts, exception types and stack locations, not
chat text, API keys or audio. The standalone smoke command enables INFO logging;
Streamlit's logging configuration controls whether informational lines appear.
See [Streamlit's log instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#cloud-logs).

| Symptom | Check |
| --- | --- |
| No matching Kokoro distribution | Python must be 3.12 for this deployment; inspect installation logs. |
| Missing dependencies | Confirm both requirements files and the English spaCy wheel installed. |
| Download/model initialization failure | Check outbound Hugging Face access, writable cache and available disk; retry after recovery interval. |
| Native pronunciation error | Confirm eSpeak NG packages/native loader and CPU architecture. |
| `busy` or `recovering` | Wait for the active job/recovery; the browser fallback avoids adding model workers. |
| Process killed/resource-limit page | Check host memory/CPU; try fewer sessions, or review the external-service contingency above. |
| No sound, but audio is ready | Use Play answer/Listen; check browser/site sound permissions and device volume. |

## Tests performed and remaining checks

- **41 unit tests passed**, including the 7 existing answer-routing tests and 34
  new voice/config tests. Heavy model initialization is mocked in unit tests.
- Real installed Kokoro produced the required greeting and two different new
  sentences. WAV parsing verified 24 kHz, mono PCM16 and nonempty audio. Subsequent
  generations reused the same pipeline object.
- Chromium decoded and played the real generated WAV through both app controls.
  Simulated microphone input and mocked AI/TTS delivery exercised repeat questions,
  mute, reruns without replay, autoplay denial/manual retry, delayed mute/close,
  synthesis-failure fallback, other-language fallback, chat changes and widths of
  390, 768 and 1280 pixels. No JavaScript errors occurred in those checks.
- An additional live turn used **actual installed Kokoro inside the Streamlit
  app**, generated speech from the final mocked-AI answer, played it in Chromium,
  and resumed listening. This verifies the complete audio handoff without claiming
  a real microphone or paid AI-provider call was exercised.
- Syntax compilation passed. Original Live Voice HTML/CSS and all existing app
  functions were compared with the branch baseline and are unchanged.
- **Not verified:** physical microphone/speakers, real mobile Safari/Chrome,
  production Cloud capacity/logs, Google OAuth, Supabase persistence or live
  Gemini/Groq/OpenRouter/search calls. Those integrations were left intact but
  require credentials/device access for an end-to-end deployment check.

Run unit tests with `python -m unittest discover -s tests -v`. The optional browser
test needs Playwright and Chromium (test-only dependencies):

```sh
python -m pip install playwright
python -m playwright install chromium
python -m kokoro_tts --output kokoro-smoke.wav
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
python tests/voice_browser_check.py --chromium /path/printed/above --wav kokoro-smoke.wav --artifacts /tmp/merge-ai-voice-check
```

Add `--real-tts` to that last command to run the additional live turn with the
installed model. This may download model files if they are not cached.

On an actual phone, open the HTTPS preview and allow microphone access. Choose
Kokoro, ask a short question, verify one final answer and Liam's voice, then mute
mid-answer, repeat the same question, close while loading, switch chats, and tap
Listen on an earlier answer. Check landscape/portrait, disabled autoplay, and
another conversation language. Browsers without speech recognition can still use
text chat and Listen; do not claim microphone support there.

## Rollback

Before approval, production `main` is unaffected: stop the preview or close the
unmerged PR. Do not merge just to test.

After an approved deployment, set `KOKORO_ENABLED = false` and
`BROWSER_FALLBACK = true` in Streamlit Secrets, then reboot, to use browser voice
without model loading. If dependency installation prevents startup, this switch
cannot fix installation; use a GitHub revert PR to undo this PR's commit(s), review
it and deploy the previous code/dependencies. Use GitHub's **Revert** action on the
merged PR, or `git revert` on a new rollback branch; do not force-push `main`.

Keep existing secrets, OAuth settings and the Supabase database. No data/schema
rollback is needed. Reverting returns to the previous browser-only voice behavior.

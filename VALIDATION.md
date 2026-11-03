# Validation performed

Base: `98178058da234c3e23b26ce2a0903584f8781c30`. Main was rechecked before preparing this repair.

* Python syntax compilation passed.
* 35 unittest cases passed: original routing regressions, greetings, application identity, Fast single-provider routing/fallback, Deep collection/synthesis, conflicting candidates, rejected provider commentary, requested comparisons/code, conversation context, private-context search isolation, WAV validation, inference failure/busy fallback, and private service authentication/input limits.
* Streamlit AppTest opened the actual app and rendered the greeting without exceptions.
* Real Kokoro 0.9.4 / CPU PyTorch 2.9.1 generated `am_liam` speech at speed 1.03, mono 24 kHz PCM WAV. A greeting generated 111,070 bytes in 25.81 seconds including a fresh model load. Earlier cached-file loading took 8.69 seconds including generation; warm generation of a 9.06-second rain explanation took 5.27 seconds. These are local measurements, not production latency promises.
* Chromium ran the actual Streamlit app with mocked provider responses and speech-recognition events, and played the real generated Kokoro WAV. Listen and Live Voice decoded and finished playback; recognition resumed afterward. Repeated identical spoken questions, mute, autoplay denial/manual recovery, other-language browser fallback and 390/768/1280-pixel widths passed, with no browser JavaScript errors.
* The original app CSS and authentication/cloud/persistence function bodies were compared and are unchanged. Database modules and schemas were not edited.

The automated browser fixture reuses a generated WAV to test transport/playback; it does not run live inference per utterance. Physical microphone/speaker quality, mobile device permissions, subjective voice naturalness, live paid-provider accuracy, production Google login, Supabase persistence and multi-user load were not tested. Provider tests use mocks, so they verify orchestration and safeguards rather than the factual reliability of future model outputs.

Streamlit private server logs were inaccessible in the available anonymous session. GitHub had no workflow/check/status logs. No production OOM or deployment Python mismatch was observed. The original live app answered a rain question coherently; synthesis failures were reproduced at the provider boundary in regression tests.

The optional TTS service's authentication, validation and WAV response contract passed with mocked inference. Its Docker image and external hosting were not deployed or tested. Full instructions, production verification steps and rollback are in `REPAIR_NOTES.md`.

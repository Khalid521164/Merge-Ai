# Merge AI PWA setup

This adds an installable Progressive Web App wrapper around the public Merge AI Streamlit app, using the existing purple M logo.

## Publish

1. Open https://github.com/Khalid521164/Merge-Ai/settings/pages
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Open the Actions tab and run **Deploy Merge AI PWA to GitHub Pages**.
4. After the workflow succeeds, open:

   https://khalid521164.github.io/Merge-Ai/

The repository owner must enable GitHub Pages first. The workflow is included, but the site cannot go live until Pages is enabled.

## Install on iPhone

Open the PWA URL in Safari → Share → Add to Home Screen → Add.

## Install on Android

Open the PWA URL in Chrome → Install app (or ⋮ → Add to Home screen).

## Important notes

- The PWA shell and icons can be cached; AI responses still require internet and the live Streamlit service.
- The Streamlit app is embedded in an iframe using the public-app embed method.
- If Google sign-in or a browser permission does not work in the embedded view, tap **Open full app** to open Streamlit directly.
- This is a PWA, not a native APK/IPA installer. The phone adds it to the home screen from the hosted HTTPS URL.

Streamlit embed documentation: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/embed-your-app
PWA installation guidance: https://web.dev/learn/pwa/installation
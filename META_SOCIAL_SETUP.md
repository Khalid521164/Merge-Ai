# Merge AI Social Hub — implementation plan

This branch contains a safe, non-networking integration foundation. No Meta account is connected and no content is published or messaged.

## Products and phased rollout

### Phase 1 — Facebook Pages
- Owner-authorized Meta OAuth with CSRF state and exact redirect URI validation.
- Discover only Pages the signed-in person is permitted to manage.
- Read Page metadata and permitted insights.
- Draft posts inside Merge AI; publishing requires a separate confirmation click.
- Start with test users / app roles; request Advanced Access and App Review before serving other users.

Likely permissions depend on the exact feature: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_metadata`, and `pages_messaging`. Request only what the selected features need.

### Phase 2 — Instagram Professional
- Support Professional (Business/Creator) accounts only, not personal consumer accounts.
- Choose one supported login configuration deliberately: Instagram Login or Facebook Login. Do not mix their token hosts or permission names.
- Start with profile read and media listing; then add publishing, comments, insights, and messaging only after each permission and review is available.
- Instagram Login permissions include `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, and `instagram_business_manage_messages`.

### Phase 3 — WhatsApp Business
- Use WhatsApp Business Platform / Cloud API, not personal WhatsApp accounts.
- Onboard a WhatsApp Business Account and phone number.
- Add webhook verification and request-signature verification before processing inbound events.
- Respect the customer-service window and approved template rules; never bulk-message or contact people without appropriate opt-in.
- Permissions: `whatsapp_business_management` and `whatsapp_business_messaging`.

## Security requirements before live OAuth/API work
1. A parent/project owner creates and controls the Meta developer app and approves the requested scopes.
2. Keep App Secret, access tokens, webhook secrets, and refresh credentials in Streamlit secrets or a server-side secret manager only. Never commit them, show them in the UI, or send them to the browser.
3. Use OAuth state/CSRF protection, strict redirect URI matching, least-privilege scopes, token expiry handling, and secure token storage.
4. Verify Meta webhook signatures and reject unverified events.
5. Every publish, comment reply, delete, and outbound message must show a preview and require a separate explicit confirmation.
6. Add per-account rate limits, audit logs, disconnect/revoke controls, and data deletion.
7. Test with app-role accounts and test assets first. App Review / Advanced Access may be required for production users.

## Current implementation in this branch
- `social_integrations.py` lists supported products, documentation links, requested-scope planning, and safe readiness checks.
- The app sidebar shows setup status only. It does not make API calls, start OAuth, or send/publish anything.
- No credentials are required for the preview UI.

## Owner setup checklist
- [ ] Project owner creates a Meta developer app.
- [ ] Project owner confirms the public callback URL and webhook URL.
- [ ] Choose Instagram Login vs Facebook Login.
- [ ] Configure secrets in the hosting dashboard, never in GitHub.
- [ ] Configure products, test accounts, permissions, and webhook subscriptions.
- [ ] Complete Meta App Review / business verification where required.

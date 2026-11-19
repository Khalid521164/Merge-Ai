"""Safe configuration registry for Merge AI social integrations.

This module intentionally performs no network requests and never stores tokens.
Real OAuth, API calls, and webhooks are added only after Meta app credentials
and approved redirect/webhook URLs are configured by the project owner.
"""

from __future__ import annotations

PLATFORMS = {
    "facebook": {
        "name": "Facebook Pages",
        "description": "Page publishing, permitted Page insights, and Messenger support.",
        "required_settings": ("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
        "optional_settings": ("META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"),
        "permissions": (
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts",
            "pages_manage_metadata",
            "pages_messaging",
        ),
        "docs_url": "https://developers.facebook.com/docs/pages-api/",
    },
    "instagram": {
        "name": "Instagram",
        "description": "Professional-account publishing, comments, insights, and messaging where approved.",
        "required_settings": ("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
        "optional_settings": ("META_IG_ACCESS_TOKEN", "META_IG_USER_ID"),
        "permissions": (
            "instagram_business_basic",
            "instagram_business_content_publish",
            "instagram_business_manage_comments",
            "instagram_business_manage_messages",
        ),
        "docs_url": "https://developers.facebook.com/docs/instagram-platform/",
    },
    "whatsapp": {
        "name": "WhatsApp Business",
        "description": "Business messaging and inbound webhooks for an onboarded WhatsApp Business account.",
        "required_settings": (
            "META_APP_ID",
            "META_APP_SECRET",
            "META_REDIRECT_URI",
            "META_WHATSAPP_PHONE_NUMBER_ID",
            "META_WHATSAPP_BUSINESS_ACCOUNT_ID",
            "META_WEBHOOK_VERIFY_TOKEN",
        ),
        "optional_settings": ("META_WHATSAPP_ACCESS_TOKEN",),
        "permissions": (
            "whatsapp_business_management",
            "whatsapp_business_messaging",
        ),
        "docs_url": "https://developers.facebook.com/docs/whatsapp/cloud-api/",
    },
}


def get_social_integrations(secret_reader):
    """Return safe readiness metadata; never return secret values."""
    results = {}
    for key, config in PLATFORMS.items():
        missing = [
            setting for setting in config["required_settings"]
            if not secret_reader(setting)
        ]
        results[key] = {
            "name": config["name"],
            "description": config["description"],
            "ready_for_setup": not missing,
            "missing_settings": missing,
            "permissions": config["permissions"],
            "docs_url": config["docs_url"],
        }
    return results


def action_requires_confirmation(action: str) -> bool:
    """All externally visible social actions require explicit user approval."""
    return action in {
        "publish_post",
        "reply_comment",
        "send_message",
        "delete_content",
        "moderate_comment",
    }

"""Account authentication and profile UI. One Account per Streamlit session.

Uses Supabase Auth; passwords are never written to chat tables or local files.
Do not cache Account or its client globally: its JWT belongs to one visitor.
"""
from __future__ import annotations

import base64
import json
import os
from urllib.parse import urlsplit

import streamlit as st
from supabase import ClientOptions, create_client


class AccountError(Exception):
    """Safe, public-facing message with no credentials or response body."""


def setting(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.environ.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        value = os.environ.get(name, default)
    return str(value or "").strip()


def is_configured() -> bool:
    return bool(setting("SUPABASE_URL") and setting("SUPABASE_PUBLISHABLE_KEY"))


def validate_public_key(key: str) -> None:
    # This app deliberately cannot use an administrative key that bypasses RLS.
    if key.startswith("sb_publishable_"):
        return
    try:
        payload = key.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims.get("role") == "anon":
            return
    except (IndexError, ValueError, TypeError):
        pass
    raise AccountError("Account connection is not configured correctly.")


class Account:
    def __init__(self, url: str, key: str):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise AccountError("Account connection is not configured correctly.")
        validate_public_key(key)
        try:
            self.client = create_client(url, key, options=ClientOptions(
                auto_refresh_token=False, persist_session=False,
                postgrest_client_timeout=15, flow_type="implicit",
            ))
        except Exception:
            raise AccountError("Account connection is not configured correctly.") from None
        self.user = None

    def verified_user(self):
        try:
            session = self.client.auth.get_session()  # Refreshes expired tokens.
            if not session:
                self.user = None
                return None
            self.user = self.client.auth.get_user(session.access_token).user
            return self.user
        except Exception:
            self.user = None
            raise AccountError("Please sign in again to access your saved chats.") from None

    def sign_in(self, email: str, password: str):
        try:
            result = self.client.auth.sign_in_with_password({
                "email": email.strip(), "password": password,
            })
            if not result.session:
                raise ValueError("No session")
            return self.verified_user()
        except Exception:
            raise AccountError("Sign-in failed. Check your email and password, and confirm your email first.") from None

    def sign_up(self, email: str, password: str, display_name: str) -> bool:
        if len(password) < 10:
            raise AccountError("Use a password with at least 10 characters.")
        name = display_name.strip()
        if not name or len(name) > 60:
            raise AccountError("Enter a name between 1 and 60 characters.")
        try:
            result = self.client.auth.sign_up({
                "email": email.strip(), "password": password,
                "options": {"data": {"display_name": name}},
            })
            if result.session:
                self.verified_user()
                return True
            return False  # Email confirmation is enabled in production.
        except Exception:
            raise AccountError("Account creation could not finish. Try signing in if you already have an account.") from None

    def request_reset(self, email: str) -> None:
        try:
            self.client.auth.reset_password_email(email.strip())
        except Exception:
            raise AccountError("The reset email could not be sent. Please try again later.") from None

    def reset_password(self, email: str, code: str, password: str) -> None:
        if len(password) < 10:
            raise AccountError("Use a password with at least 10 characters.")
        try:
            self.client.auth.verify_otp({"email": email.strip(), "token": code.strip(), "type": "recovery"})
            self.client.auth.update_user({"password": password})
            self.sign_out()
        except Exception:
            self.sign_out()
            raise AccountError("The reset could not finish. Check the code or request a new one.") from None

    def update_name(self, name: str) -> None:
        if not name.strip() or len(name.strip()) > 60:
            raise AccountError("Enter a name between 1 and 60 characters.")
        try:
            self.user = self.client.auth.update_user({"data": {"display_name": name.strip()}}).user
        except Exception:
            raise AccountError("Your name could not be saved. Please try again.") from None

    def sign_out(self) -> None:
        try:
            self.client.auth.sign_out({"scope": "local"})
        except Exception:
            pass
        finally:
            self.user = None


def display_name(user) -> str:
    metadata = getattr(user, "user_metadata", None) or {}
    return (str(metadata.get("display_name") or "").strip() or "Your account")[:60]


def clear_private_state() -> None:
    """Forget this device's client, chat, password widgets, and pending answer."""
    for key in list(st.session_state):
        if key.startswith(("ma_", "_ma_")) or key in {"engine", "messages", "request_times"}:
            del st.session_state[key]


def render_sign_in(account: Account) -> None:
    st.subheader("Your conversations, wherever you are")
    st.caption("Sign in on any device to continue your saved chats.")
    with st.container(border=True, key="account_form"):
        sign_in, create, reset = st.tabs(["Sign in", "Create account", "Reset password"])
        with sign_in:
            with st.form("ma_signin", clear_on_submit=True):
                email = st.text_input("Email", max_chars=254)
                password = st.text_input("Password", type="password", max_chars=256)
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                try:
                    account.sign_in(email, password)
                    st.rerun()
                except AccountError as exc:
                    st.error(str(exc))
        with create:
            with st.form("ma_signup", clear_on_submit=True):
                name = st.text_input("Display name", max_chars=60)
                email = st.text_input("Email address", max_chars=254)
                password = st.text_input("Create password", type="password", max_chars=256,
                                         help="At least 10 characters.")
                confirm = st.text_input("Confirm password", type="password", max_chars=256)
                submitted = st.form_submit_button("Create account", type="primary", width="stretch")
            if submitted:
                try:
                    if password != confirm:
                        raise AccountError("The passwords do not match.")
                    if account.sign_up(email, password, name):
                        st.rerun()
                    st.success("Check your email to confirm your account. Then return here and sign in.")
                except AccountError as exc:
                    st.error(str(exc))
        with reset:
            with st.form("ma_request_reset", clear_on_submit=True):
                email = st.text_input("Account email", max_chars=254)
                submitted = st.form_submit_button("Send reset code", width="stretch")
            if submitted:
                try:
                    account.request_reset(email)
                    st.success("If this account can receive email, a reset code will arrive shortly.")
                except AccountError as exc:
                    st.error(str(exc))
            with st.expander("I have a reset code"):
                with st.form("ma_reset", clear_on_submit=True):
                    email = st.text_input("Your email", max_chars=254)
                    code = st.text_input("Code from your email", max_chars=20)
                    password = st.text_input("New password", type="password", max_chars=256)
                    confirm = st.text_input("Repeat new password", type="password", max_chars=256)
                    submitted = st.form_submit_button("Update password", width="stretch")
                if submitted:
                    try:
                        if password != confirm:
                            raise AccountError("The passwords do not match.")
                        account.reset_password(email, code, password)
                        st.success("Password updated. Use the Sign in tab.")
                    except AccountError as exc:
                        st.error(str(exc))


def render_account_info(account: Account) -> None:
    user = account.user
    st.subheader("Your account")
    st.caption("Your profile and saved conversations belong to this account.")
    with st.container(border=True):
        st.text(f"Email: {user.email}")
        joined = user.created_at.strftime("%B %d, %Y") if user.created_at else "—"
        st.text(f"Joined: {joined}")
        st.text(f"Account ID: {user.id}")
        with st.form("ma_profile"):
            name = st.text_input("Display name", value=display_name(user), max_chars=60)
            submitted = st.form_submit_button("Save profile", type="primary")
        if submitted:
            try:
                account.update_name(name)
                st.success("Profile saved.")
            except AccountError as exc:
                st.error(str(exc))
    st.caption("Chats stay saved when you sign out. You may need to sign in again after refreshing or closing the browser.")
    st.caption("Your questions are sent to the configured AI services. Web research uses Tavily.")

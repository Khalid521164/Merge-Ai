"""Project-owner authorization tests."""
import unittest

from owner_auth import is_project_owner, owner_context, require_project_owner


def make_secret(values):
    return lambda name, default="": values.get(name, default)


class OwnerAuthTests(unittest.TestCase):
    def test_verified_subject_is_owner(self):
        secret = make_secret({"OWNER_GOOGLE_SUBS": "google-sub-123"})
        self.assertTrue(is_project_owner({"sub": "google-sub-123"}, secret))

    def test_verified_email_is_owner(self):
        secret = make_secret({"OWNER_EMAILS": "owner@example.com"})
        self.assertTrue(is_project_owner({
            "sub": "google-sub-456", "email": "OWNER@example.com",
            "email_verified": True,
        }, secret))

    def test_unverified_email_is_not_owner(self):
        secret = make_secret({"OWNER_EMAILS": "owner@example.com"})
        self.assertFalse(is_project_owner({
            "email": "owner@example.com", "email_verified": False,
        }, secret))

    def test_spoken_claim_or_display_name_is_not_owner(self):
        secret = make_secret({"OWNER_DISPLAY_NAME": "Khalid"})
        self.assertFalse(is_project_owner({
            "name": "Khalid", "spoken_claim": "I am the owner",
        }, secret))

    def test_owner_context_only_for_allowlisted_account(self):
        secret = make_secret({"OWNER_GOOGLE_SUBS": "sub-1", "OWNER_DISPLAY_NAME": "Khalid"})
        self.assertIn("verified as Khalid", owner_context({"sub": "sub-1"}, secret))
        self.assertIn("unverified", owner_context({"sub": "sub-2"}, secret))

    def test_owner_guard_rejects_non_owner(self):
        secret = make_secret({"OWNER_GOOGLE_SUBS": "sub-1"})
        with self.assertRaises(PermissionError):
            require_project_owner({"sub": "sub-2"}, secret)
        require_project_owner({"sub": "sub-1"}, secret)


if __name__ == "__main__":
    unittest.main()

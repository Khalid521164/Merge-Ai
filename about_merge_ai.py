"""Canonical public facts about Merge AI, not the visiting user's identity."""
from __future__ import annotations
import re

PROJECT_NAME = "Merge AI"
CREATOR_NAME = "Khalid Bin Ashraf"
OWNER_NAME = "Khalid Bin Ashraf"
CREATED_FOR = "a seventh-grade science fair project"
PURPOSE = (
    "Khalid created Merge AI to explore whether answers from multiple AI "
    "providers could be combined into one useful response. He also wanted "
    "people to have an easy-to-use assistant with web research, "
    "account-based chat history, and personal memory."
)
PROVIDERS = "Gemini, Groq, and OpenRouter"
PROJECT_WEBSITE = "https://mergeai.streamlit.app/"

PROJECT_CONTEXT = (
    f"You are {PROJECT_NAME}. Your creator and project owner is {CREATOR_NAME}. "
    f"You started as {CREATED_FOR}. {PURPOSE} "
    f"Your AI providers include {PROVIDERS}. "
    "These are facts about the project, not facts about the person chatting. "
    "Never claim a visitor is your creator unless separately verified."
)

def answer_project_question(question: str) -> str | None:
    """Answer ONLY a standalone question explicitly about Merge AI's origins.

    Never hijack pasted test lists or other multi-question messages.
    """
    raw = str(question or "").strip()
    if not raw or len(raw) > 170 or "\n" in raw or raw.count("?") > 1:
        return None

    q = re.sub(r"\s+", " ", raw.casefold()).strip(" \t?.!")

    owner_patterns = (
        r"(?:who (?:created|made|built|develop(?:ed)?|devlop(?:ed)?|owns) "
        r"(?:you|merge ai|mergeai|this (?:ai|app))"
        r"(?: (?:on|in) (?:my|your) (?:pc|computer|phone|laptop))?|"
        r"who (?:is|was) (?:your|merge ai(?:'s)?) (?:creator|owner)|"
        r"(?:who|what) (?:is|was) (?:your|the) creator(?: of merge ai)?|"
        r"who (?:is )?(?:the )?developer of (?:you|merge ai|mergeai)|"
        r"(?:tell me )?who (?:made|created|built|develop(?:ed)?|devlop(?:ed)?) (?:you|merge ai)|"
        r"who is behind merge ai)"
    )
    purpose_patterns = (
        r"(?:why (?:were you|was merge ai|was this (?:ai|app)) "
        r"(?:created|made|built)|"
        r"why (?:did khalid create|did khalid make) merge ai|"
        r"why (?:do you|does merge ai) exist|"
        r"what (?:is|was) (?:your|merge ai(?:'s)?) "
        r"(?:purpose|goal)|"
        r"what (?:were you|was merge ai) (?:made|created|built) for)"
    )

    if re.fullmatch(
        r"who (?:created|made|built|develop(?:ed)?|devlop(?:ed)?) (?:you|merge ai) and why",
        q,
    ):
        return f"I was created by **{CREATOR_NAME}** for {CREATED_FOR}. {PURPOSE}"

    if re.fullmatch(owner_patterns, q):
        return f"**{CREATOR_NAME}** created Merge AI and is its project owner."

    if re.fullmatch(purpose_patterns, q):
        return f"I was created by **{CREATOR_NAME}** for {CREATED_FOR}. {PURPOSE}"

    return None

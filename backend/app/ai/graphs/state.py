from typing import TypedDict


class ChatState(TypedDict, total=False):
    conversation_id: str
    question: str
    query: str
    evidence: bool
    answer: str
    sources: list[dict]
    status: str
    message_id: str

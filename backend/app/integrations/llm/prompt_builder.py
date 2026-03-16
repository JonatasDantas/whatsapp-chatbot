import json

from app.config.settings import _get_settings
from app.domain.models.conversation import Conversation
from app.domain.models.message import Message
from app.integrations.s3.knowledge_base_client import S3KnowledgeBaseClient

_knowledge_base = None


def _get_knowledge_base() -> str:
    global _knowledge_base
    if _knowledge_base is None:
        settings = _get_settings()
        client = S3KnowledgeBaseClient(bucket=settings.knowledge_base_bucket)
        _knowledge_base = client.fetch()
    return _knowledge_base


class PromptBuilder:
    def __init__(self):
        self._kb = _get_knowledge_base()

    def build_system_prompt(self, conversation: Conversation) -> str:
        state = conversation.model_dump(
            exclude={"created_at", "updated_at"},
            exclude_none=True,
        )
        state_json = json.dumps(state, ensure_ascii=False, default=str)
        return (
            f"{self._kb}\n\n"
            f"## Current Conversation State\n\n"
            f"```json\n{state_json}\n```"
        )

    def build_messages(self, messages: list[Message]) -> list[dict]:
        return [
            {"role": msg.role.value, "content": msg.message}
            for msg in messages
        ]

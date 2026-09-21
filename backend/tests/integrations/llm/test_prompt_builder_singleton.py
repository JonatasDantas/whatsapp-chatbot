"""
Tests for the _get_knowledge_base singleton factory in prompt_builder.
Kept in a separate file to avoid the autouse mock fixture in test_prompt_builder.py.
"""
from unittest.mock import MagicMock, patch

import app.integrations.llm.prompt_builder as pb_mod


def test_get_knowledge_base_fetches_from_s3_and_caches():
    """_get_knowledge_base() calls S3 on the first call and returns the cached string after."""
    pb_mod._knowledge_base = None

    fake_settings = MagicMock()
    fake_settings.knowledge_base_bucket = "test-bucket"

    fake_client = MagicMock()
    fake_client.fetch.return_value = "## Property Info"

    with patch("app.integrations.llm.prompt_builder._get_settings", return_value=fake_settings), \
         patch("app.integrations.llm.prompt_builder.S3KnowledgeBaseClient", return_value=fake_client):
        kb1 = pb_mod._get_knowledge_base()
        kb2 = pb_mod._get_knowledge_base()

    assert kb1 == "## Property Info"
    assert kb1 is kb2
    fake_client.fetch.assert_called_once()

    pb_mod._knowledge_base = None

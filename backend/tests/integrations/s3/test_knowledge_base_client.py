import boto3
import pytest
from moto import mock_aws

from app.integrations.s3.knowledge_base_client import S3KnowledgeBaseClient

BUCKET = "chacarada-dantas-whatsapp-chatbot"
KEY = "knowledge-base.md"
CONTENT = "# System Instructions\nBe helpful in Portuguese."


@pytest.fixture
def s3_bucket():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=CONTENT.encode("utf-8"))
        yield s3


def test_fetch_returns_knowledge_base_content(s3_bucket):
    client = S3KnowledgeBaseClient(bucket=BUCKET)
    content = client.fetch()
    assert content == CONTENT


def test_fetch_uses_custom_key(s3_bucket):
    s3_bucket.put_object(Bucket=BUCKET, Key="custom.md", Body=b"Custom content")
    client = S3KnowledgeBaseClient(bucket=BUCKET, key="custom.md")
    assert client.fetch() == "Custom content"

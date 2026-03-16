import boto3
from aws_lambda_powertools import Logger

logger = Logger()


class S3KnowledgeBaseClient:
    def __init__(self, bucket: str, key: str = "knowledge-base.md"):
        self._bucket = bucket
        self._key = key

    def fetch(self) -> str:
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=self._bucket, Key=self._key)
        content = response["Body"].read().decode("utf-8")
        logger.info("knowledge_base_fetched", bucket=self._bucket, key=self._key)
        return content

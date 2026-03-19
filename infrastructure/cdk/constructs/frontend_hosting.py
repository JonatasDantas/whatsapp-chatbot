# infrastructure/cdk/constructs/frontend_hosting.py
# Note: Uses S3 static website hosting instead of CloudFront.
# CloudFront requires account verification from AWS Support.
# For production, replace with the CloudFront version once verified.
from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class FrontendHostingConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "FrontendBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html",  # SPA: all 404s → index.html
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
        )

        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[s3deploy.Source.asset("frontend/out")],
            destination_bucket=bucket,
        )

        self.distribution_url = bucket.bucket_website_url
        self.bucket = bucket

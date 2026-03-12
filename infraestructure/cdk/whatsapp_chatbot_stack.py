from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class WhatsappChatbotStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.Table(
            self,
            "ChatBotTable",
            table_name="WhatsappChatBot",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
        )

        handler = _lambda.Function(
            self,
            "WhatsappWebhookFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.whatsapp_webhook",
            code=_lambda.Code.from_asset("backend/lambdas/webhook"),
            environment={
                "TABLE_NAME": table.table_name,
            },
        )

        table.grant_read_write_data(handler)

        endpoint = apigw.LambdaRestApi(
            self,
            "WhatsappWebhookEndpoint",
            handler=handler,
            rest_api_name="WhatsappWebhookApi",
        )

        webhook = endpoint.root.add_resource("webhook")
        webhook.add_method("POST")


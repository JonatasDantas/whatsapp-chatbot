from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class BackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        conversations_table = self._create_conversations_table()
        messages_table = self._create_messages_table()
        reservations_table = self._create_reservations_table()

        webhook_function = self._create_webhook_function(
            conversations_table, messages_table, reservations_table
        )

        self._create_api_gateway(webhook_function)

    def _create_conversations_table(self) -> dynamodb.Table:
        return dynamodb.Table(
            self,
            "ConversationsTable",
            table_name="Conversations",
            partition_key=dynamodb.Attribute(
                name="phone_number",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_messages_table(self) -> dynamodb.Table:
        return dynamodb.Table(
            self,
            "MessagesTable",
            table_name="Messages",
            partition_key=dynamodb.Attribute(
                name="phone_number",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_reservations_table(self) -> dynamodb.Table:
        return dynamodb.Table(
            self,
            "ReservationsTable",
            table_name="Reservations",
            partition_key=dynamodb.Attribute(
                name="reservation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_webhook_function(
        self,
        conversations_table: dynamodb.Table,
        messages_table: dynamodb.Table,
        reservations_table: dynamodb.Table,
    ) -> _lambda.Function:
        function = _lambda.Function(
            self,
            "WebhookFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset("backend/lambdas/webhook"),
            environment={
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "MESSAGES_TABLE": messages_table.table_name,
                "RESERVATIONS_TABLE": reservations_table.table_name,
                "WHATSAPP_VERIFY_TOKEN": "",
            },
        )

        conversations_table.grant_read_write_data(function)
        messages_table.grant_read_write_data(function)
        reservations_table.grant_read_write_data(function)

        return function

    def _create_api_gateway(self, handler: _lambda.Function) -> apigw.RestApi:
        api = apigw.RestApi(
            self,
            "WebhookApi",
            rest_api_name="ChacaraChatbotApi",
        )

        webhook = api.root.add_resource("webhook")
        webhook.add_method("GET", apigw.LambdaIntegration(handler))
        webhook.add_method("POST", apigw.LambdaIntegration(handler))

        return api

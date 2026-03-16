from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class BackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        conversations_table = self._create_conversations_table()
        messages_table = self._create_messages_table()
        reservations_table = self._create_reservations_table()

        verify_token_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "WhatsappVerifyTokenParam",
            parameter_name="/chacara-chatbot/whatsapp-verify-token",
        )

        openai_key_param, whatsapp_token_param, whatsapp_phone_param, knowledge_base_param = (
            self._create_settings_parameters()
        )

        webhook_function = self._create_webhook_function(
            conversations_table,
            messages_table,
            reservations_table,
            verify_token_param,
            openai_key_param,
            whatsapp_token_param,
            whatsapp_phone_param,
            knowledge_base_param,
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

    def _create_settings_parameters(self) -> tuple:
        openai_key = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "OpenAiApiKeyParam",
            parameter_name="/chacara-chatbot/openai-api-key",
        )
        whatsapp_token = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "WhatsappAccessTokenParam",
            parameter_name="/chacara-chatbot/whatsapp-access-token",
        )
        whatsapp_phone = ssm.StringParameter(
            self,
            "WhatsappPhoneNumberIdParam",
            parameter_name="/chacara-chatbot/whatsapp-phone-number-id",
            string_value="REPLACE_ME",
        )
        knowledge_base = ssm.StringParameter(
            self,
            "KnowledgeBaseBucketParam",
            parameter_name="/chacara-chatbot/knowledge-base-bucket",
            string_value="REPLACE_ME",
        )
        return openai_key, whatsapp_token, whatsapp_phone, knowledge_base

    def _create_webhook_function(
        self,
        conversations_table: dynamodb.Table,
        messages_table: dynamodb.Table,
        reservations_table: dynamodb.Table,
        verify_token_param: ssm.IStringParameter,
        openai_key_param: ssm.IStringParameter,
        whatsapp_token_param: ssm.IStringParameter,
        whatsapp_phone_param: ssm.StringParameter,
        knowledge_base_param: ssm.StringParameter,
    ) -> _lambda.Function:
        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:7",
        )

        function = _lambda.Function(
            self,
            "WebhookFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.webhook.handler.handler",
            code=_lambda.Code.from_asset("backend"),
            layers=[powertools_layer],
            environment={
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "MESSAGES_TABLE": messages_table.table_name,
                "RESERVATIONS_TABLE": reservations_table.table_name,
                "WHATSAPP_VERIFY_TOKEN_PARAM": verify_token_param.parameter_name,
                "OPENAI_API_KEY_PARAM": openai_key_param.parameter_name,
                "WHATSAPP_ACCESS_TOKEN_PARAM": whatsapp_token_param.parameter_name,
                "WHATSAPP_PHONE_NUMBER_ID_PARAM": whatsapp_phone_param.parameter_name,
                "KNOWLEDGE_BASE_BUCKET_PARAM": knowledge_base_param.parameter_name,
            },
        )

        conversations_table.grant_read_write_data(function)
        messages_table.grant_read_write_data(function)
        reservations_table.grant_read_write_data(function)
        verify_token_param.grant_read(function)

        # ssm:GetParameters (plural) for the batched get_parameters() call in Settings
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                resources=[
                    openai_key_param.parameter_arn,
                    whatsapp_token_param.parameter_arn,
                    whatsapp_phone_param.parameter_arn,
                    knowledge_base_param.parameter_arn,
                ],
            )
        )
        # Required for WithDecryption=True on the SecureString params
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=[f"arn:aws:kms:{self.region}:{self.account}:alias/aws/ssm"],
            )
        )

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

from aws_cdk import Duration, RemovalPolicy, Stack
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

        blocked_periods_table = self._create_blocked_periods_table()

        (
            openai_key_param,
            evolution_url_param,
            evolution_key_param,
            evolution_instance_param,
            knowledge_base_param,
            owner_phone_param,
        ) = self._create_settings_parameters()

        webhook_function = self._create_webhook_function(
            conversations_table,
            messages_table,
            reservations_table,
            blocked_periods_table,
            openai_key_param,
            evolution_url_param,
            evolution_key_param,
            evolution_instance_param,
            knowledge_base_param,
            owner_phone_param,
        )

        self._create_api_gateway(webhook_function)

        self.conversations_table = conversations_table
        self.messages_table = messages_table
        self.reservations_table = reservations_table
        self.blocked_periods_table = blocked_periods_table

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

    def _create_blocked_periods_table(self) -> dynamodb.Table:
        return dynamodb.Table(
            self,
            "BlockedPeriodsTable",
            table_name="BlockedPeriods",
            partition_key=dynamodb.Attribute(
                name="period_id",
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
        # SecureString params — managed manually in SSM, must exist before deploying.
        openai_key = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "OpenAiApiKeyParam",
            parameter_name="/chacara-chatbot/openai-api-key",
        )
        evolution_key = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "EvolutionApiKeyParam",
            parameter_name="/chacara-chatbot/evolution-api-key",
        )
        evolution_url = ssm.StringParameter(
            self,
            "EvolutionApiUrlParam",
            parameter_name="/chacara-chatbot/evolution-api-url",
            string_value="REPLACE_ME",
            description="Base URL of the Evolution API EC2 instance (e.g. https://evolution.yourdomain.com)",
        )
        evolution_instance = ssm.StringParameter(
            self,
            "EvolutionInstanceNameParam",
            parameter_name="/chacara-chatbot/evolution-instance-name",
            string_value="REPLACE_ME",
            description="Evolution API instance name (e.g. chacara)",
        )
        knowledge_base = ssm.StringParameter(
            self,
            "KnowledgeBaseBucketParam",
            parameter_name="/chacara-chatbot/knowledge-base-bucket",
            string_value="REPLACE_ME",
        )
        owner_phone = ssm.StringParameter(
            self,
            "OwnerPhoneParam",
            parameter_name="/chacara-chatbot/owner-phone",
            string_value="REPLACE_ME",
            description="Owner's WhatsApp phone number for lead notifications (e.g. +5511999999999)",
        )
        return openai_key, evolution_url, evolution_key, evolution_instance, knowledge_base, owner_phone

    def _create_webhook_function(
        self,
        conversations_table: dynamodb.Table,
        messages_table: dynamodb.Table,
        reservations_table: dynamodb.Table,
        blocked_periods_table: dynamodb.Table,
        openai_key_param: ssm.IStringParameter,
        evolution_url_param: ssm.IStringParameter,
        evolution_key_param: ssm.IStringParameter,
        evolution_instance_param: ssm.IStringParameter,
        knowledge_base_param: ssm.IStringParameter,
        owner_phone_param: ssm.IStringParameter,
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
            timeout=Duration.seconds(60),
            environment={
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "MESSAGES_TABLE": messages_table.table_name,
                "RESERVATIONS_TABLE": reservations_table.table_name,
                "BLOCKED_PERIODS_TABLE": blocked_periods_table.table_name,
                "OPENAI_API_KEY_PARAM": openai_key_param.parameter_name,
                "EVOLUTION_API_URL_PARAM": evolution_url_param.parameter_name,
                "EVOLUTION_API_KEY_PARAM": evolution_key_param.parameter_name,
                "EVOLUTION_INSTANCE_NAME_PARAM": evolution_instance_param.parameter_name,
                "KNOWLEDGE_BASE_BUCKET_PARAM": knowledge_base_param.parameter_name,
                "OWNER_PHONE_PARAM": owner_phone_param.parameter_name,
                "NIGHTLY_RATE": "800.0",
            },
        )

        conversations_table.grant_read_write_data(function)
        messages_table.grant_read_write_data(function)
        reservations_table.grant_read_write_data(function)
        blocked_periods_table.grant_read_write_data(function)

        # ssm:GetParameters (plural) for the batched get_parameters() call in Settings
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                resources=[
                    openai_key_param.parameter_arn,
                    evolution_url_param.parameter_arn,
                    evolution_key_param.parameter_arn,
                    evolution_instance_param.parameter_arn,
                    knowledge_base_param.parameter_arn,
                    owner_phone_param.parameter_arn,
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

        # S3 read access for the knowledge base bucket (fetched at runtime via SSM)
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::*/*"],
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

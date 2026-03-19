# infrastructure/cdk/constructs/admin_api.py
from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class AdminApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        conversations_table: dynamodb.Table,
        messages_table: dynamodb.Table,
        reservations_table: dynamodb.Table,
        whatsapp_token_param: ssm.IStringParameter,
        whatsapp_phone_param: ssm.IStringParameter,
        user_pool: cognito.UserPool,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{Stack.of(self).region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:7",
        )

        function = _lambda.Function(
            self,
            "AdminFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.admin.handler.handler",
            code=_lambda.Code.from_asset("backend"),
            layers=[powertools_layer],
            environment={
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "MESSAGES_TABLE": messages_table.table_name,
                "RESERVATIONS_TABLE": reservations_table.table_name,
                "WHATSAPP_ACCESS_TOKEN_PARAM": whatsapp_token_param.parameter_name,
                "WHATSAPP_PHONE_NUMBER_ID_PARAM": whatsapp_phone_param.parameter_name,
                "ALLOWED_ORIGIN": "*",  # Update post-deploy to CloudFront URL for security
            },
        )

        conversations_table.grant_read_write_data(function)
        messages_table.grant_read_data(function)
        reservations_table.grant_read_data(function)

        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                resources=[
                    whatsapp_token_param.parameter_arn,
                    whatsapp_phone_param.parameter_arn,
                ],
            )
        )
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=[f"arn:aws:kms:{Stack.of(self).region}:{Stack.of(self).account}:alias/aws/ssm"],
            )
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "AdminAuthorizer",
            cognito_user_pools=[user_pool],
        )

        api = apigw.RestApi(
            self,
            "AdminApi",
            rest_api_name="ChacaraAdminApi",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Authorization", "Content-Type"],
            ),
        )

        api_root = api.root.add_resource("api")

        # /api/conversations
        conversations = api_root.add_resource("conversations")
        conversations.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}
        phone_resource = conversations.add_resource("{phone}")
        phone_resource.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}/messages
        messages_resource = phone_resource.add_resource("messages")
        messages_resource.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}/takeover
        takeover_resource = phone_resource.add_resource("takeover")
        takeover_resource.add_method(
            "POST",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/reservations
        reservations = api_root.add_resource("reservations")
        reservations.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        self.api_url = api.url

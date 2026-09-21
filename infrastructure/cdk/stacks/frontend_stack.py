# infrastructure/cdk/stacks/frontend_stack.py
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from cdk.constructs.admin_api import AdminApiConstruct
from cdk.constructs.frontend_hosting import FrontendHostingConstruct
from cdk.stacks.backend_stack import BackendStack


class FrontendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        backend: BackendStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        user_pool = cognito.UserPool(
            self,
            "OwnerUserPool",
            user_pool_name="chacara-owner-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )

        user_pool_client = cognito.UserPoolClient(
            self,
            "OwnerAppClient",
            user_pool=user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
            ),
        )

        whatsapp_token_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "WhatsappAccessTokenParam",
            parameter_name="/chacara-chatbot/whatsapp-access-token",
        )
        whatsapp_phone_param = ssm.StringParameter.from_string_parameter_name(
            self,
            "WhatsappPhoneParam",
            "/chacara-chatbot/whatsapp-phone-number-id",
        )

        admin_api = AdminApiConstruct(
            self,
            "AdminApi",
            conversations_table=backend.conversations_table,
            messages_table=backend.messages_table,
            reservations_table=backend.reservations_table,
            blocked_periods_table=backend.blocked_periods_table,
            whatsapp_token_param=whatsapp_token_param,
            whatsapp_phone_param=whatsapp_phone_param,
            user_pool=user_pool,
        )

        hosting = FrontendHostingConstruct(self, "FrontendHosting")

        CfnOutput(self, "AdminApiUrl", value=admin_api.api_url)
        CfnOutput(self, "FrontendUrl", value=hosting.distribution_url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)

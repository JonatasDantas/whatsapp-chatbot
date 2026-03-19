#!/usr/bin/env python3
import aws_cdk as cdk
from cdk.stacks.backend_stack import BackendStack
from cdk.stacks.frontend_stack import FrontendStack

app = cdk.App()
backend = BackendStack(app, "ChacaraChatbotStack")
FrontendStack(app, "ChacaraFrontendStack", backend=backend)
app.synth()

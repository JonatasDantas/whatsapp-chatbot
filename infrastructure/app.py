#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk.stacks.backend_stack import BackendStack
from cdk.stacks.evolution_stack import EvolutionStack
from cdk.stacks.frontend_stack import FrontendStack

app = cdk.App()

env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))

backend = BackendStack(app, "ChacaraChatbotStack", env=env)
FrontendStack(app, "ChacaraFrontendStack", backend=backend, env=env)
EvolutionStack(app, "ChacaraEvolutionStack", env=env)
app.synth()

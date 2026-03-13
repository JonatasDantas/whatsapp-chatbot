#!/usr/bin/env python3
import aws_cdk as cdk
from cdk.stacks.backend_stack import BackendStack

app = cdk.App()
BackendStack(app, "ChacaraChatbotStack")
app.synth()

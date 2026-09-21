import os

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct


class EvolutionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        sg = ec2.SecurityGroup(self, "EvolutionSg", vpc=vpc, description="Evolution API")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        role = iam.Role(
            self,
            "EvolutionRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/chacara-chatbot/evolution-api-key",
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/chacara-chatbot/evolution-postgres-password",
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=[f"arn:aws:kms:{self.region}:{self.account}:alias/aws/ssm"],
            )
        )

        ubuntu_ami = ec2.MachineImage.lookup(
            name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
            owners=["099720109477"],  # Canonical
        )

        compose_path = os.path.join(os.path.dirname(__file__), "../../evolution/docker-compose.yml")
        with open(compose_path) as f:
            compose_content = f.read()

        nginx_path = os.path.join(os.path.dirname(__file__), "../../evolution/nginx.conf")
        with open(nginx_path) as f:
            nginx_content = f.read()

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "apt-get update -y",
            "apt-get install -y docker.io docker-compose-plugin awscli nginx certbot python3-certbot-nginx",
            "systemctl enable docker && systemctl start docker",
            "mkdir -p /opt/evolution",
            # Write docker-compose.yml
            f"cat > /opt/evolution/docker-compose.yml << 'COMPOSEOF'\n{compose_content}\nCOMPOSEOF",
            # Write nginx config
            f"cat > /etc/nginx/sites-available/evolution << 'NGINXEOF'\n{nginx_content}\nNGINXEOF",
            "ln -sf /etc/nginx/sites-available/evolution /etc/nginx/sites-enabled/evolution",
            "rm -f /etc/nginx/sites-enabled/default",
            "systemctl reload nginx",
            # Fetch secrets from SSM
            "REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)",
            "EVOLUTION_KEY=$(aws ssm get-parameter --name /chacara-chatbot/evolution-api-key --with-decryption --query Parameter.Value --output text --region $REGION)",
            "POSTGRES_PASS=$(aws ssm get-parameter --name /chacara-chatbot/evolution-postgres-password --with-decryption --query Parameter.Value --output text --region $REGION)",
            # Write .env for docker-compose
            "cat > /opt/evolution/.env << ENVEOF",
            "SERVER_URL=https://REPLACE_WITH_YOUR_DOMAIN",
            "AUTHENTICATION_API_KEY=$EVOLUTION_KEY",
            "DATABASE_PROVIDER=postgresql",
            "DATABASE_CONNECTION_URI=postgresql://evolution:${POSTGRES_PASS}@postgres:5432/evolution",
            "POSTGRES_PASSWORD=$POSTGRES_PASS",
            "CACHE_REDIS_URI=redis://redis:6379",
            "CACHE_REDIS_ENABLED=true",
            "DATABASE_SAVE_DATA_NEW_MESSAGE=true",
            "ENVEOF",
            "cd /opt/evolution && docker compose up -d",
        )

        instance = ec2.Instance(
            self,
            "EvolutionInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ubuntu_ami,
            vpc=vpc,
            security_group=sg,
            role=role,
            user_data=user_data,
            # Pre-create this key pair in the EC2 console and download the .pem
            key_name="chacara-evolution-key",
        )

        eip = ec2.CfnEIP(self, "EvolutionEip", instance_id=instance.instance_id)
        CfnOutput(self, "EvolutionPublicIp", value=eip.ref)

# Magento B2B MVP — Single EC2 Test Infrastructure
# Stand up, test connectors, tear down. Not for production.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------- Variables ----------

variable "aws_region" {
  default = "us-east-2"
}

variable "key_name" {
  description = "EC2 key pair name for SSH"
  type        = string
}

variable "my_ip" {
  description = "Your public IP for SSH access (e.g. 203.0.113.5/32)"
  type        = string
}

variable "magento_admin_password" {
  description = "Magento admin panel password"
  type        = string
  sensitive   = true
  default     = "Admin123!@#"
}

variable "magento_repo_public_key" {
  description = "repo.magento.com public key (from marketplace account)"
  type        = string
}

variable "magento_repo_private_key" {
  description = "repo.magento.com private key"
  type        = string
  sensitive   = true
}

# ---------- Data Sources ----------

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# ---------- IAM Role for SSM ----------

resource "aws_iam_role" "ec2_ssm" {
  name = "magento-mvp-ec2-ssm"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = { Name = "magento-mvp-ec2-ssm" }
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_ssm" {
  name = "magento-mvp-ec2-ssm"
  role = aws_iam_role.ec2_ssm.name
}

# ---------- Security Group ----------

resource "aws_security_group" "magento" {
  name        = "magento-mvp"
  description = "Magento B2B test instance"
  vpc_id      = data.aws_vpc.default.id

  # Ingress: SSH from your IP only (for debugging)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
    description = "SSH from admin IP"
  }

  # Egress: HTTPS to anywhere (SSM, Veza cloud, package repos, Docker ECR)
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound (SSM, Veza, repos, ECR)"
  }

  # Egress: HTTP to anywhere (package repos that use HTTP)
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP outbound (package repos)"
  }

  # Egress: DNS
  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS TCP"
  }

  tags = { Name = "magento-mvp" }
}

# ---------- EC2 Instance ----------

resource "aws_instance" "magento" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.medium"
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.magento.id]
  subnet_id              = data.aws_subnets.default.ids[0]
  iam_instance_profile   = aws_iam_instance_profile.ec2_ssm.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = { Name = "magento-b2b-mvp" }
}

# ---------- Auto-Stop on Idle (CPU < 5% for 10 min) ----------

resource "aws_cloudwatch_metric_alarm" "magento_idle" {
  alarm_name          = "magento-mvp-idle-stop"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 5
  alarm_description   = "Stop Magento EC2 when CPU < 5% for 10 min"
  alarm_actions       = ["arn:aws:automate:${var.aws_region}:ec2:stop"]

  dimensions = {
    InstanceId = aws_instance.magento.id
  }
}

# ---------- Outputs ----------

output "magento_public_ip" {
  value = aws_instance.magento.public_ip
}

output "magento_private_ip" {
  value = aws_instance.magento.private_ip
}

output "magento_instance_id" {
  value       = aws_instance.magento.id
  description = "For SSM: aws ssm start-session --target <id>"
}

output "ssm_magento" {
  value = "aws ssm start-session --target ${aws_instance.magento.id} --profile magento-mvp"
}

output "magento_admin_url" {
  value = "http://${aws_instance.magento.public_ip}/admin"
}

output "magento_rest_api" {
  value = "http://${aws_instance.magento.private_ip}/rest/V1/"
}

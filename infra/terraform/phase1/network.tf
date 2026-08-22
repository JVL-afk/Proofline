resource "aws_vpc" "phase1" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "egress" {
  vpc_id = aws_vpc.phase1.id
  tags   = { Name = "${var.name_prefix}-egress-igw" }
}

resource "aws_subnet" "public_egress" {
  vpc_id                  = aws_vpc.phase1.id
  cidr_block              = var.public_egress_subnet_cidr
  availability_zone       = var.availability_zones[0]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name_prefix}-public-egress" }
}

resource "aws_subnet" "private" {
  count                   = 2
  vpc_id                  = aws_vpc.phase1.id
  cidr_block              = var.private_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name_prefix}-private-${count.index + 1}" }
}

resource "aws_eip" "research_egress" {
  domain = "vpc"
  tags   = { Name = "${var.name_prefix}-research-egress" }
}

resource "aws_nat_gateway" "research_egress" {
  allocation_id = aws_eip.research_egress.id
  subnet_id     = aws_subnet.public_egress.id

  depends_on = [aws_internet_gateway.egress]
  tags       = { Name = "${var.name_prefix}-research-egress" }
}

resource "aws_route_table" "public_egress" {
  vpc_id = aws_vpc.phase1.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.egress.id
  }
  tags = { Name = "${var.name_prefix}-public-egress" }
}

resource "aws_route_table_association" "public_egress" {
  subnet_id      = aws_subnet.public_egress.id
  route_table_id = aws_route_table.public_egress.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.phase1.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.research_egress.id
  }
  tags = { Name = "${var.name_prefix}-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "worker" {
  name        = "${var.name_prefix}-worker"
  description = "No ingress; bounded public HTTP egress for the isolated research worker"
  vpc_id      = aws_vpc.phase1.id
  tags        = { Name = "${var.name_prefix}-worker" }
}

resource "aws_security_group" "controlled_egress" {
  name        = "${var.name_prefix}-controlled-egress"
  description = "Application-aware exact-host public research boundary"
  vpc_id      = aws_vpc.phase1.id
  tags        = { Name = "${var.name_prefix}-controlled-egress" }
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name_prefix}-aws-endpoints"
  description = "Private AWS service endpoints used by Phase 1 tasks"
  vpc_id      = aws_vpc.phase1.id
  tags        = { Name = "${var.name_prefix}-aws-endpoints" }
}

resource "aws_vpc_security_group_egress_rule" "worker_to_gateway" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.controlled_egress.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  description                  = "Only the controlled exact-host gateway may perform public research"
}

resource "aws_vpc_security_group_egress_rule" "worker_to_endpoints" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private AWS API endpoints only"
}

resource "aws_vpc_security_group_egress_rule" "worker_to_database" {
  security_group_id            = aws_security_group.worker.id
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "Private PostgreSQL only"
}

resource "aws_vpc_security_group_egress_rule" "worker_dns_udp" {
  security_group_id = aws_security_group.worker.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  description       = "VPC resolver DNS"
}

resource "aws_vpc_security_group_egress_rule" "worker_dns_tcp" {
  security_group_id = aws_security_group.worker.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  description       = "VPC resolver DNS fallback"
}

resource "aws_vpc_security_group_ingress_rule" "gateway_from_worker" {
  security_group_id            = aws_security_group.controlled_egress.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  description                  = "Research worker requests only"
}

resource "aws_vpc_security_group_egress_rule" "gateway_https" {
  security_group_id = aws_security_group.controlled_egress.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Public TLS only after exact-host and public-IP authorization"
}

resource "aws_vpc_security_group_egress_rule" "gateway_http" {
  security_group_id = aws_security_group.controlled_egress.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "Public HTTP only after exact-host and public-IP authorization"
}

resource "aws_vpc_security_group_egress_rule" "gateway_dns_udp" {
  security_group_id = aws_security_group.controlled_egress.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  description       = "VPC resolver DNS"
}

resource "aws_vpc_security_group_egress_rule" "gateway_dns_tcp" {
  security_group_id = aws_security_group.controlled_egress.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  description       = "VPC resolver DNS fallback"
}

resource "aws_vpc_security_group_egress_rule" "gateway_to_endpoints" {
  security_group_id            = aws_security_group.controlled_egress.id
  referenced_security_group_id = aws_security_group.endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private AWS API endpoints only"
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_worker" {
  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_gateway" {
  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = aws_security_group.controlled_egress.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

locals {
  interface_endpoint_services = toset(["ecr.api", "ecr.dkr", "logs", "secretsmanager", "ssm"])
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_endpoint_services
  vpc_id              = aws_vpc.phase1.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = { Name = "${var.name_prefix}-${replace(each.value, ".", "-")}" }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.phase1.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = { Name = "${var.name_prefix}-s3" }
}

resource "aws_security_group" "database" {
  name        = "${var.name_prefix}-database"
  description = "Private PostgreSQL reachable only from the Phase 1 worker"
  vpc_id      = aws_vpc.phase1.id
  tags        = { Name = "${var.name_prefix}-database" }
}

resource "aws_vpc_security_group_ingress_rule" "database_from_worker" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.worker.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

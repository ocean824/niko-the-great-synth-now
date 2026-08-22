data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zones)
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.name}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name}-igw"
  }
}

resource "aws_subnet" "public" {
  for_each = toset(local.azs)

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, index(local.azs, each.value))
  map_public_ip_on_launch = false

  tags = {
    Name                                      = "${var.name}-public-${each.value}"
    "kubernetes.io/role/elb"                 = "1"
    "kubernetes.io/cluster/${var.cluster_tag}" = "shared"
  }
}

resource "aws_subnet" "private" {
  for_each = toset(local.azs)

  vpc_id            = aws_vpc.this.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 16 + index(local.azs, each.value))

  tags = {
    Name                                            = "${var.name}-private-${each.value}"
    "kubernetes.io/role/internal-elb"             = "1"
    "kubernetes.io/cluster/${var.cluster_tag}"    = "shared"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.name}-public"
  }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  for_each = aws_subnet.public
  domain   = "vpc"

  tags = {
    Name = "${var.name}-nat-${each.key}"
  }
}

resource "aws_nat_gateway" "this" {
  for_each = aws_subnet.public

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = each.value.id

  depends_on = [aws_internet_gateway.this]

  tags = {
    Name = "${var.name}-nat-${each.key}"
  }
}

resource "aws_route_table" "private" {
  for_each = aws_subnet.private

  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[each.key].id
  }

  tags = {
    Name = "${var.name}-private-${each.key}"
  }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.name}-vpce-"
  description = "Restricts interface endpoint access to this VPC."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "TLS from workloads within the VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.name}-vpce"
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name       = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for route_table in aws_route_table.private : route_table.id]

  tags = {
    Name = "${var.name}-s3"
  }
}

data "aws_region" "current" {}

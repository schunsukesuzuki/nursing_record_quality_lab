# SCAFFOLD ONLY: HTTP-only public ALB, publicly addressed Fargate tasks, no end-user auth.
# Do not use real clinical data. See README.md and DEPLOY_CHECKLIST.md before apply.

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_ecr_repository" "images" {
  for_each             = toset(["backend", "inference", "ollama-model"])
  name                 = "${var.prefix}-${each.value}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  force_delete = false
}

resource "aws_iam_role" "execution" {
  name               = "${var.prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "backend_task" {
  name               = "${var.prefix}-backend-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role" "inference_task" {
  name               = "${var.prefix}-inference-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_cloudwatch_log_group" "services" {
  for_each          = toset(["backend", "inference"])
  name              = "/ecs/${var.prefix}/${each.value}"
  retention_in_days = 7
}

resource "aws_vpc" "demo" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = cidrsubnet(aws_vpc.demo.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
}

resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name   = "${var.prefix}-alb"
  vpc_id = aws_vpc.demo.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # MOCK ONLY - tighten to CloudFront origin-facing prefix list in production
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "backend" {
  name   = "${var.prefix}-backend"
  vpc_id = aws_vpc.demo.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "inference" {
  name   = "${var.prefix}-inference"
  vpc_id = aws_vpc.demo.id
  ingress {
    from_port       = 8100
    to_port         = 8100
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }
  # Ollama port 11434 is accessible only through task-local loopback.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "nrl.internal"
  vpc  = aws_vpc.demo.id
}

resource "aws_service_discovery_service" "inference" {
  name = "inference"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
}

resource "aws_ecs_cluster" "demo" {
  name = var.prefix
}

locals {
  log_options_backend = {
    awslogs-group         = aws_cloudwatch_log_group.services["backend"].name
    awslogs-region        = var.aws_region
    awslogs-stream-prefix = "backend"
  }
  log_options_inference = {
    awslogs-group         = aws_cloudwatch_log_group.services["inference"].name
    awslogs-region        = var.aws_region
    awslogs-stream-prefix = "inference"
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.backend_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = var.backend_image
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "INFERENCE_URL", value = "http://inference.nrl.internal:8100" },
      { name = "INFERENCE_AUTH_MODE", value = "none" }, # SG isolation only: NOT a production auth scheme
      { name = "INFERENCE_TIMEOUT_SECONDS", value = "195" },
      { name = "CORS_ORIGINS", value = "https://${aws_cloudfront_distribution.frontend.domain_name}" }
    ]
    logConfiguration = { logDriver = "awslogs", options = local.log_options_backend }
  }])
}

resource "aws_ecs_task_definition" "inference" {
  family                   = "${var.prefix}-inference"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048"
  memory                   = "4096"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.inference_task.arn

  # One deploy unit for inference adapter + local Ollama runtime.
  # This stock architecture requires a custom pre-pulled Ollama image.
  container_definitions = jsonencode([
    {
      name      = "inference"
      image     = var.inference_image
      essential = true
      portMappings = [{ containerPort = 8100, hostPort = 8100, protocol = "tcp" }]
      environment = [
        { name = "OLLAMA_URL", value = "http://127.0.0.1:11434" },
        { name = "MODEL_NAME", value = var.model_name },
        { name = "OLLAMA_TIMEOUT_SECONDS", value = "180" }
      ]
      logConfiguration = { logDriver = "awslogs", options = local.log_options_inference }
    },
    {
      name      = "ollama"
      image     = var.ollama_image
      essential = true
      portMappings = [{ containerPort = 11434, hostPort = 11434, protocol = "tcp" }]
      environment = [{ name = "OLLAMA_HOST", value = "127.0.0.1:11434" }]
      logConfiguration = { logDriver = "awslogs", options = local.log_options_inference }
    }
  ])
}

resource "aws_lb" "backend" {
  name               = "${var.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "backend" {
  name        = "${var.prefix}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.demo.id
  health_check {
    path                = "/health/live"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "backend" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP" # MOCK: add ACM and HTTPS listener in production
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

resource "aws_ecs_service" "backend" {
  name            = "${var.prefix}-backend"
  cluster         = aws_ecs_cluster.demo.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = true # MOCK: avoid a paid NAT for this teaching sample
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.backend, aws_iam_role_policy_attachment.execution]
}

resource "aws_ecs_service" "inference" {
  name            = "${var.prefix}-inference"
  cluster         = aws_ecs_cluster.demo.id
  task_definition = aws_ecs_task_definition.inference.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.inference.id]
    assign_public_ip = true # MOCK: no public inbound SG rules
  }
  service_registries {
    registry_arn = aws_service_discovery_service.inference.arn
  }
  depends_on = [aws_iam_role_policy_attachment.execution]
}

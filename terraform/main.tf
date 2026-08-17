terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "admindev"
}

# --- DynamoDB Table ---

resource "aws_dynamodb_table" "nutritrack" {
  name         = "nutritrack-entries"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}

# --- Lambda IAM Role ---

resource "aws_iam_role" "lambda_role" {
  name = "nutritrack-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "nutritrack-lambda-dynamodb"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.nutritrack.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "nutritrack-lambda-bedrock"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Lambda Function ---

resource "aws_lambda_function" "nutritrack" {
  function_name = "nutritrack-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "nutritrack.handler.handler"
  runtime       = "python3.12"
  architectures = ["arm64"]
  memory_size   = 128
  timeout       = 30
  filename      = "../lambda.zip"

  source_code_hash = filebase64sha256("../lambda.zip")

  environment {
    variables = {
      DYNAMODB_TABLE   = "nutritrack-entries"
      BEDROCK_MODEL_ID = var.bedrock_model_id
      APP_AWS_REGION   = var.aws_region
    }
  }
}

# --- API Gateway HTTP API ---

resource "aws_apigatewayv2_api" "nutritrack" {
  name          = "nutritrack-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.nutritrack.id
  name        = "$default"
  auto_deploy = true
}

# --- JWT Authorizer (Cognito) ---

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.nutritrack.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.nutritrack.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.nutritrack.id}"
  }
}

# --- Lambda Integration ---

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.nutritrack.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.nutritrack.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# --- API Routes ---

resource "aws_apigatewayv2_route" "post_entries" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "POST /entries"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "delete_entries" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "DELETE /entries"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "get_summary" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "GET /summary"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "get_profile" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "GET /profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "post_profile" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "POST /profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "put_profile_goal" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "PUT /profile/goal"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "post_weight" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "POST /weight"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "get_weight_history" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "GET /weight/history"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "get_summary_week" {
  api_id             = aws_apigatewayv2_api.nutritrack.id
  route_key          = "GET /summary/week"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "options_cors" {
  api_id    = aws_apigatewayv2_api.nutritrack.id
  route_key = "OPTIONS /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# --- Lambda Permission for API Gateway ---

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.nutritrack.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.nutritrack.execution_arn}/*/*"
}

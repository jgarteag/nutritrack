output "api_url" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.nutritrack.id
}

output "cognito_client_id" {
  description = "Cognito App Client ID"
  value       = aws_cognito_user_pool_client.nutritrack.id
}

output "frontend_bucket_name" {
  description = "S3 bucket name for frontend deployment"
  value       = aws_s3_bucket.frontend.id
}

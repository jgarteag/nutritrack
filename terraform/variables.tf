variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID for food image analysis"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

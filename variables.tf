variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "pipeline_name" {
  description = "Name of the SageMaker pipeline"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket that triggers the Lambda"
  type        = string
}

variable "lambda_zip_path" {
  description = "Path to the Lambda ZIP file"
  type        = string
  default     = "${path.module}/lambda/lambda_start_pipeline.zip"
}

variable "lambda_function_name" {
  description = "Lambda function name"
  type        = string
  default     = "start-fraud-pipeline-on-s3"
}

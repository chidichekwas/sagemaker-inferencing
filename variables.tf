variable "aws_region" {
  type        = string
  description = "AWS region to deploy resources"
}

variable "pipeline_name" {
  type        = string
  description = "Name of the SageMaker pipeline"
}

variable "bucket_name" {
  type        = string
  description = "S3 bucket for pipeline scripts and artifacts"
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "lambda_zip_path" {
  type        = string
  description = "Relative path to the Lambda ZIP file"
  default     = "lambda/lambda_start_pipeline.zip"
}

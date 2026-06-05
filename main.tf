resource "aws_iam_role" "lambda_start_pipeline_role" {
  name = "lambda-start-pipeline-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_start_pipeline_policy" {
  role = aws_iam_role.lambda_start_pipeline_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sagemaker:StartPipelineExecution"]
        Resource = "arn:aws:sagemaker:${var.aws_region}:${var.account_id}:pipeline/${var.pipeline_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "start_pipeline" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_start_pipeline_role.arn
  handler       = "start_pipeline.lambda_handler"
  runtime       = "python3.10"

  filename = var.lambda_zip_path

  environment {
    variables = {
      PIPELINE_NAME = var.pipeline_name
    }
  }
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_pipeline.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.bucket_name}"
}

resource "aws_s3_bucket_notification" "fraud_processed_trigger" {
  bucket = var.bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.start_pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "fraud/processed/"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

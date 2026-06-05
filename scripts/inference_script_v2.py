"""
inference_script_v2.py
Version: 2.2
Purpose: Batch invoke fraud detection endpoint inside a SageMaker Processing job.
"""

import os
import sys
import time
import traceback
from typing import List

import boto3
import pandas as pd
import logging

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

ENDPOINT_NAME = "fraud-detection-2026-05-27-07-42-54"

INPUT_DIR = "/opt/ml/processing/input"
OUTPUT_DIR = "/opt/ml/processing/output"
LOG_DIR = "/opt/ml/processing/logs"

FEATURE_COLS = [f"feature_{i}" for i in range(30)]

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

# ⭐ FIX: Processing containers do NOT have a default region
REGION = os.environ.get("AWS_REGION", "us-east-1")
sm_runtime = boto3.client("sagemaker-runtime", region_name=REGION)


# -------------------------------------------------------------------
# LOGGING SETUP
# -------------------------------------------------------------------

def setup_logger():
    """Configure logger to write to stdout (CloudWatch) and file (S3)."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("fraud_inference_v2")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # avoid duplicate handlers

    # Console handler → CloudWatch
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # File handler → S3 via ProcessingOutput
    fh = logging.FileHandler(os.path.join(LOG_DIR, "inference.log"))
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger


logger = setup_logger()


# -------------------------------------------------------------------
# ENDPOINT INVOCATION
# -------------------------------------------------------------------

def invoke_endpoint_with_retry(payload: str) -> float:
    """Invoke the endpoint with retry logic and return a float prediction."""
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Invoking endpoint (attempt {attempt}/{MAX_RETRIES})")

            response = sm_runtime.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType="text/csv",
                Body=payload,
            )

            body = response["Body"].read().decode("utf-8").strip()
            logger.info(f"Raw endpoint response: '{body}'")

            return float(body)

        except Exception as e:
            last_exc = e
            logger.error(f"Error invoking endpoint: {e}")
            traceback.print_exc()

            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_BACKOFF_SECONDS} seconds...")
                time.sleep(RETRY_BACKOFF_SECONDS)

    raise RuntimeError(
        f"Endpoint invocation failed after {MAX_RETRIES} attempts"
    ) from last_exc


# -------------------------------------------------------------------
# DATA LOADING & VALIDATION
# -------------------------------------------------------------------

def find_parquet_file(input_dir: str) -> str:
    """Return the first parquet file found in the input directory."""
    files = os.listdir(input_dir)
    logger.info(f"Files in input dir '{input_dir}': {files}")

    parquet_files = [f for f in files if f.endswith(".parquet")]
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in {input_dir}")

    parquet_path = os.path.join(input_dir, parquet_files[0])
    logger.info(f"Using parquet file: {parquet_path}")
    return parquet_path


def load_and_validate_data(parquet_path: str) -> pd.DataFrame:
    """Load parquet and validate schema."""
    df = pd.read_parquet(parquet_path)
    logger.info(f"Parquet loaded. Shape: {df.shape}")
    logger.info(f"Columns: {df.columns.tolist()}")

    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected feature columns: {missing}")

    df = df[FEATURE_COLS]
    logger.info(f"Using feature columns: {FEATURE_COLS}")
    logger.info(f"Data shape after filtering: {df.shape}")

    return df


# -------------------------------------------------------------------
# PREDICTION LOOP
# -------------------------------------------------------------------

def run_inference(df: pd.DataFrame) -> List[float]:
    """Invoke endpoint row‑by‑row and return predictions."""
    predictions = []
    total = len(df)

    logger.info(f"Starting inference for {total} rows")

    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        payload = ",".join(str(v) for v in row.values)

        if idx <= 3:
            logger.info(f"Row {idx} payload: {payload}")

        try:
            pred = invoke_endpoint_with_retry(payload)
        except Exception as e:
            logger.error(f"Error on row {idx}: {e}")
            traceback.print_exc()
            raise

        predictions.append(pred)

        if idx % 100 == 0 or idx == total:
            logger.info(f"Processed {idx}/{total} rows")

    logger.info("Inference loop completed")
    return predictions


# -------------------------------------------------------------------
# OUTPUT WRITING
# -------------------------------------------------------------------

def write_output(df: pd.DataFrame, predictions: List[float], output_dir: str) -> str:
    """Write predictions CSV and return its path."""
    os.makedirs(output_dir, exist_ok=True)

    out_df = df.copy()
    out_df["prediction"] = predictions

    output_path = os.path.join(output_dir, "predictions.csv")
    logger.info(f"Writing predictions to: {output_path}")

    out_df.to_csv(output_path, index=False)

    size = os.path.getsize(output_path)
    logger.info(f"Output file size: {size} bytes")

    return output_path


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main():
    logger.info("=== Starting inference_script_v2 (v2.2) ===")
    logger.info(f"Endpoint: {ENDPOINT_NAME}")
    logger.info(f"Input dir: {INPUT_DIR}")
    logger.info(f"Output dir: {OUTPUT_DIR}")
    logger.info(f"Region: {REGION}")

    try:
        parquet_path = find_parquet_file(INPUT_DIR)
        df = load_and_validate_data(parquet_path)
        predictions = run_inference(df)
        output_path = write_output(df, predictions, OUTPUT_DIR)

        logger.info(f"Success. Output written to: {output_path}")
        logger.info("=== inference_script_v2 completed successfully ===")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()
        logger.error("Exiting with code 1")
        sys.exit(1)


# -------------------------------------------------------------------
# ENTRYPOINT
# -------------------------------------------------------------------

if __name__ == "__main__":
    main()

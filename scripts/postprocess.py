import pandas as pd
import os

INPUT = "/opt/ml/processing/input"
OUTPUT = "/opt/ml/processing/output"

def main():
    df = pd.read_csv(f"{INPUT}/predictions.csv")
    summary = df["prediction"].describe()
    summary.to_csv(f"{OUTPUT}/summary.csv")

if __name__ == "__main__":
    main()

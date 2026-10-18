"""Download the real Olist dataset from Kaggle into data/raw.

Needs a Kaggle account and API token (~/.kaggle/kaggle.json):
https://www.kaggle.com/docs/api#authentication

Usage:  pip install kaggle && python -m ecom.download
"""
import subprocess
import sys

from ecom.config import RAW_DIR
from ecom.datasets import KAGGLE_DATASET


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", KAGGLE_DATASET, "-p", str(RAW_DIR), "--unzip"]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        sys.exit("The kaggle CLI is not installed. Run: pip install kaggle")


if __name__ == "__main__":
    main()

"""
This module handles the retrieval of credentials 
required for authentication with GCP services.
"""

import json
import os

# Path to local credentials file, used in local development.
CREDENTIALS_PATH = os.environ.get("CREDENTIALS_PATH")

# Credentials passed as an environment variable, used in deployment.
CREDENTIALS = os.environ.get("CREDENTIALS")


def get_credentials_json():
  if not CREDENTIALS and not CREDENTIALS_PATH:
    raise ValueError(
        "No credentials found. Ensure CREDENTIALS or CREDENTIALS_PATH is set.")

  # Use the environment variable for credentials when a file cannot be used
  # in the environment, as credentials should not be made public.
  if CREDENTIALS:
    return json.loads(CREDENTIALS)

  if not os.path.exists(CREDENTIALS_PATH):
    raise FileNotFoundError(f"Credentials file not found: {CREDENTIALS_PATH}")

  # Set credentials using a file in a local environment.
  with open(CREDENTIALS_PATH, "r", encoding="utf-8") as cred_file:
    return json.load(cred_file)

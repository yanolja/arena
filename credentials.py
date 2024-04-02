"""
This module handles the retrieval of credentials 
required for authentication with GCP services.
"""

import json
import os
import stat
import tempfile

# Path to local credentials file, used in local development.
CREDENTIALS_PATH = os.environ.get("CREDENTIALS_PATH")

# Credentials passed as an environment variable, used in deployment.
CREDENTIALS = os.environ.get("CREDENTIALS")


def set_credentials(credentials: str = None, credentials_path: str = None):
  if not credentials and not credentials_path:
    raise ValueError(
        "No credentials found. Ensure credentials or credentials path is set.")

  if credentials_path:
    if os.path.exists(credentials_path):
      os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
      return
    raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

  # Create a temporary file to store credentials for
  # services that don't accept string format credentials.
  with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                   delete=False) as cred_file:
    cred_file.write(credentials)
    os.chmod(cred_file.name, stat.S_IRUSR)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_file.name


# TODO(#69): Replace get_credentials_json with set_credentials.
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

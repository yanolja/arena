"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import json
import math
import os

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import gradio as gr
import pandas as pd

# Path to local credentials file, used in local development.
CREDENTIALS_PATH = os.environ.get("CREDENTIALS_PATH")

# Credentials passed as an environment variable, used in deployment.
CREDENTIALS = os.environ.get("CREDENTIALS")


def get_credentials():
  # Set credentials using a file in a local environment, if available.
  if CREDENTIALS_PATH and os.path.exists(CREDENTIALS_PATH):
    return credentials.Certificate(CREDENTIALS_PATH)

  # Use environment variable for credentials when the file is not found,
  # as credentials should not be public.
  json_cred = json.loads(CREDENTIALS)
  return credentials.Certificate(json_cred)


# TODO(#21): Fix auto-reload issue related to the initialization of Firebase.
firebase_admin.initialize_app(get_credentials())
db = firestore.client()


class LeaderboardTab(enum.Enum):
  SUMMARIZATION = "Summarization"
  TRANSLATION = "Translation"


# Ref: https://colab.research.google.com/drive/1RAWb22-PFNI-X1gPVzc927SGUdfr6nsR?usp=sharing#scrollTo=QLGc6DwxyvQc pylint: disable=line-too-long
def compute_elo(battles, k=4, scale=400, base=10, initial_rating=1000):
  rating = defaultdict(lambda: initial_rating)

  for model_a, model_b, winner in battles[["model_a", "model_b",
                                           "winner"]].itertuples(index=False):
    rating_a = rating[model_a]
    rating_b = rating[model_b]

    expected_score_a = 1 / (1 + base**((rating_b - rating_a) / scale))
    expected_score_b = 1 / (1 + base**((rating_a - rating_b) / scale))

    scored_point_a = 0.5 if winner == "tie" else int(winner == "model_a")

    rating[model_a] += k * (scored_point_a - expected_score_a)
    rating[model_b] += k * (1 - scored_point_a - expected_score_b)

  return rating


def get_docs(tab):
  if tab == LeaderboardTab.SUMMARIZATION:
    return db.collection("arena-summarizations").order_by("timestamp").stream()

  if tab == LeaderboardTab.TRANSLATION:
    return db.collection("arena-translations").order_by("timestamp").stream()


def load_elo_ratings(tab):
  docs = get_docs(tab)

  battles = []
  for doc in docs:
    data = doc.to_dict()
    battles.append({
        "model_a": data["model_a"],
        "model_b": data["model_b"],
        "winner": data["winner"]
    })

  battles = pd.DataFrame(battles)
  ratings = compute_elo(battles)

  sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
  return [[i + 1, model, math.floor(rating + 0.5)]
          for i, (model, rating) in enumerate(sorted_ratings)]


def load_summarization_elo_ratings():
  return load_elo_ratings(LeaderboardTab.SUMMARIZATION)


def load_translation_elo_ratings():
  return load_elo_ratings(LeaderboardTab.TRANSLATION)


LEADERBOARD_UPDATE_INTERVAL = 600  # 10 minutes
LEADERBOARD_INFO = "The leaderboard is updated every 10 minutes."


def build_leaderboard():
  with gr.Tabs():
    with gr.Tab(LeaderboardTab.SUMMARIZATION.value):
      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=load_summarization_elo_ratings,
                   every=LEADERBOARD_UPDATE_INTERVAL)
      gr.Markdown(LEADERBOARD_INFO)

    # TODO(#9): Add language filter options.
    with gr.Tab(LeaderboardTab.TRANSLATION.value):
      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=load_translation_elo_ratings,
                   every=LEADERBOARD_UPDATE_INTERVAL)
      gr.Markdown(LEADERBOARD_INFO)

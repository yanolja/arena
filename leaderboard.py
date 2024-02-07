"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import math

import gradio as gr
import pandas as pd


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


def get_docs(tab, db):
  if tab.label == LeaderboardTab.SUMMARIZATION.value:
    return db.collection("arena-summarizations").order_by("timestamp").stream()

  if tab.label == LeaderboardTab.TRANSLATION.value:
    return db.collection("arena-translations").order_by("timestamp").stream()


# TODO(#8): Update the value periodically.
def load_elo_ratings(tab, db):
  docs = get_docs(tab, db)

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


def build_leaderboard(db):
  with gr.Tabs():
    with gr.Tab(LeaderboardTab.SUMMARIZATION.value) as summarization_tab:
      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=load_elo_ratings(summarization_tab, db))

    # TODO(#9): Add language filter options.
    with gr.Tab(LeaderboardTab.TRANSLATION.value) as translation_tab:
      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=load_elo_ratings(translation_tab, db))

"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import math

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1 import base_query
import gradio as gr
import lingua
import pandas as pd

from credentials import get_credentials_json

# TODO(#21): Fix auto-reload issue related to the initialization of Firebase.
firebase_admin.initialize_app(credentials.Certificate(get_credentials_json()))
db = firestore.client()

SUPPORTED_TRANSLATION_LANGUAGES = [
    "Korean", "English", "Chinese", "Japanese", "Spanish", "French"
]


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


def get_docs(tab: str,
             summary_lang: str = None,
             source_lang: str = None,
             target_lang: str = None):
  if tab == LeaderboardTab.SUMMARIZATION:
    collection = db.collection("arena-summarizations").order_by("timestamp")

    if summary_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "model_a_response_language", "==", summary_lang.lower())).where(
              filter=base_query.FieldFilter("model_b_response_language", "==",
                                            summary_lang.lower()))

    return collection.stream()

  if tab == LeaderboardTab.TRANSLATION:
    collection = db.collection("arena-translations").order_by("timestamp")

    if source_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "source_language", "==", source_lang.lower()))

    if target_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "target_language", "==", target_lang.lower()))

    return collection.stream()


def load_elo_ratings(tab,
                     summary_lang: str = None,
                     source_lang: str = None,
                     target_lang: str = None):
  docs = get_docs(tab, summary_lang, source_lang, target_lang)

  battles = []
  for doc in docs:
    data = doc.to_dict()
    battles.append({
        "model_a": data["model_a"],
        "model_b": data["model_b"],
        "winner": data["winner"]
    })

  if not battles:
    return

  battles = pd.DataFrame(battles)
  ratings = compute_elo(battles)

  sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
  return [[i + 1, model, math.floor(rating + 0.5)]
          for i, (model, rating) in enumerate(sorted_ratings)]


LEADERBOARD_UPDATE_INTERVAL = 600  # 10 minutes
LEADERBOARD_INFO = "The leaderboard is updated every 10 minutes."

DEFAULT_SUMMARY_LANG_FILTER = "English"
filtered_summarization = gr.DataFrame(
    headers=["Rank", "Model", "Elo rating"],
    datatype=["number", "str", "number"],
    value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION,
                                   DEFAULT_SUMMARY_LANG_FILTER),
    elem_classes="leaderboard")

DEFAULT_FILTER_OPTIONS = {
    "source_language": "English",
    "target_language": "Spanish"
}

filtered_dataframe = gr.DataFrame(
    headers=["Rank", "Model", "Elo rating"],
    datatype=["number", "str", "number"],
    value=lambda: load_elo_ratings(
        LeaderboardTab.TRANSLATION, DEFAULT_FILTER_OPTIONS[
            "source_language"], DEFAULT_FILTER_OPTIONS["target_language"]),
    elem_classes="leaderboard")


def update_filtered_leaderboard(summary_lang: str, source_lang, target_lang):
  new_value = load_elo_ratings(LeaderboardTab.TRANSLATION, summary_lang,
                               source_lang, target_lang)
  return gr.update(value=new_value)


def build_leaderboard():
  with gr.Tabs():
    with gr.Tab(LeaderboardTab.SUMMARIZATION.value):
      with gr.Accordion("Filter", open=False):
        with gr.Row():
          languages = [
              language.name.capitalize() for language in lingua.Language.all()
          ]
          summary_language = gr.Dropdown(choices=languages,
                                         value=DEFAULT_SUMMARY_LANG_FILTER,
                                         label="Summary language",
                                         interactive=True)
          summary_language.change(fn=update_filtered_leaderboard,
                                  inputs=[summary_language],
                                  outputs=filtered_summarization)

        with gr.Row():
          filtered_summarization.render()

      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION),
                   every=LEADERBOARD_UPDATE_INTERVAL,
                   elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

    with gr.Tab(LeaderboardTab.TRANSLATION.value):
      with gr.Accordion("Filter", open=False):
        with gr.Row():
          source_language = gr.Dropdown(
              choices=SUPPORTED_TRANSLATION_LANGUAGES,
              label="Source language",
              value=DEFAULT_FILTER_OPTIONS["source_language"],
              interactive=True)
          target_language = gr.Dropdown(
              choices=SUPPORTED_TRANSLATION_LANGUAGES,
              label="Target language",
              value=DEFAULT_FILTER_OPTIONS["target_language"],
              interactive=True)

          source_language.change(fn=update_filtered_leaderboard,
                                 inputs=[source_language, target_language],
                                 outputs=filtered_dataframe)
          target_language.change(fn=update_filtered_leaderboard,
                                 inputs=[source_language, target_language],
                                 outputs=filtered_dataframe)

        with gr.Row():
          filtered_dataframe.render()

      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=lambda: load_elo_ratings(LeaderboardTab.TRANSLATION),
                   every=LEADERBOARD_UPDATE_INTERVAL,
                   elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

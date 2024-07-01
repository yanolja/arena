"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import math
from typing import Tuple

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1 import base_query
import gradio as gr
import lingua
import pandas as pd

from credentials import get_credentials_json

if gr.NO_RELOAD:
  firebase_admin.initialize_app(credentials.Certificate(get_credentials_json()))
  db = firestore.client()

SUPPORTED_LANGUAGES = [
    language.name.capitalize() for language in lingua.Language.all()
]

ANY_LANGUAGE = "Any"


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

    if summary_lang and (not summary_lang == ANY_LANGUAGE):
      collection = collection.where(filter=base_query.FieldFilter(
          "model_a_response_language", "==", summary_lang.lower())).where(
              filter=base_query.FieldFilter("model_b_response_language", "==",
                                            summary_lang.lower()))

    return collection.stream()

  if tab == LeaderboardTab.TRANSLATION:
    collection = db.collection("arena-translations").order_by("timestamp")

    if source_lang and (not source_lang == ANY_LANGUAGE):
      collection = collection.where(filter=base_query.FieldFilter(
          "source_language", "==", source_lang.lower()))

    if target_lang and (not target_lang == ANY_LANGUAGE):
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

  rank = 0
  last_rating = None
  rating_rows = []
  for index, (model, rating) in enumerate(sorted_ratings):
    int_rating = math.floor(rating + 0.5)
    if int_rating != last_rating:
      rank = index + 1

    rating_rows.append([rank, model, int_rating])
    last_rating = int_rating

  return rating_rows


LEADERBOARD_UPDATE_INTERVAL = 600  # 10 minutes
LEADERBOARD_INFO = "The leaderboard is updated every 10 minutes."


def update_filtered_leaderboard(tab, summary_lang: str, source_lang: str,
                                target_lang: str):
  new_value = load_elo_ratings(tab, summary_lang, source_lang, target_lang)
  return gr.update(value=new_value)


def build_leaderboard():
  with gr.Tabs():

    # Returns (original leaderboard, filtered leaderboard).
    def toggle_leaderboard(language: str) -> Tuple[gr.Dataframe, gr.Dataframe]:
      filter_chosen = language != ANY_LANGUAGE
      return gr.Dataframe(visible=not filter_chosen), gr.Dataframe(
          visible=filter_chosen)

    with gr.Tab(LeaderboardTab.SUMMARIZATION.value):
      summary_language = gr.Dropdown(choices=SUPPORTED_LANGUAGES +
                                     [ANY_LANGUAGE],
                                     value=ANY_LANGUAGE,
                                     label="Summary language",
                                     interactive=True)

      filtered_summarization = gr.DataFrame(
          headers=["Rank", "Model", "Elo rating"],
          datatype=["number", "str", "number"],
          value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION,
                                         ANY_LANGUAGE),
          elem_classes="leaderboard",
          visible=False)

      original_summarization = gr.Dataframe(
          headers=["Rank", "Model", "Elo rating"],
          datatype=["number", "str", "number"],
          value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION),
          every=LEADERBOARD_UPDATE_INTERVAL,
          elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

      summary_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.SUMMARIZATION), summary_language,
              gr.State(None),
              gr.State(None)
          ],
          outputs=filtered_summarization).then(
              fn=toggle_leaderboard,
              inputs=summary_language,
              outputs=[original_summarization, filtered_summarization])

    with gr.Tab(LeaderboardTab.TRANSLATION.value):
      with gr.Row():
        source_language = gr.Dropdown(choices=SUPPORTED_LANGUAGES +
                                      [ANY_LANGUAGE],
                                      label="Source language",
                                      value=ANY_LANGUAGE,
                                      interactive=True)
        target_language = gr.Dropdown(choices=SUPPORTED_LANGUAGES +
                                      [ANY_LANGUAGE],
                                      label="Target language",
                                      value=ANY_LANGUAGE,
                                      interactive=True)

      filtered_translation = gr.DataFrame(
          headers=["Rank", "Model", "Elo rating"],
          datatype=["number", "str", "number"],
          value=lambda: load_elo_ratings(LeaderboardTab.TRANSLATION,
                                         ANY_LANGUAGE, ANY_LANGUAGE),
          elem_classes="leaderboard",
          visible=False)

      original_translation = gr.Dataframe(
          headers=["Rank", "Model", "Elo rating"],
          datatype=["number", "str", "number"],
          value=lambda: load_elo_ratings(LeaderboardTab.TRANSLATION),
          every=LEADERBOARD_UPDATE_INTERVAL,
          elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

      source_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.TRANSLATION),
              gr.State(None), source_language, target_language
          ],
          outputs=filtered_translation).then(
              fn=toggle_leaderboard,
              inputs=source_language,
              outputs=[original_translation, filtered_translation])
      target_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.TRANSLATION),
              gr.State(None), source_language, target_language
          ],
          outputs=filtered_translation).then(
              fn=toggle_leaderboard,
              inputs=target_language,
              outputs=[original_translation, filtered_translation])

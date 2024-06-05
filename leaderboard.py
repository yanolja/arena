"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import math
from typing import Dict, List

import gradio as gr
import lingua

import db
from db import get_battles

SUPPORTED_TRANSLATION_LANGUAGES = [
    language.name.capitalize() for language in lingua.Language.all()
]

ANY_LANGUAGE = "Any"


class LeaderboardTab(enum.Enum):
  SUMMARIZATION = "Summarization"
  TRANSLATION = "Translation"


# Ref: https://colab.research.google.com/drive/1RAWb22-PFNI-X1gPVzc927SGUdfr6nsR?usp=sharing#scrollTo=QLGc6DwxyvQc pylint: disable=line-too-long
def compute_elo(battles: List[db.Battle],
                k=4,
                scale=400,
                base=10,
                initial_rating=1000) -> Dict[str, int]:
  rating = defaultdict(lambda: initial_rating)

  for battle in battles:
    model_a, model_b, winner = battle.model_a, battle.model_b, battle.winner

    rating_a = rating[model_a]
    rating_b = rating[model_b]

    expected_score_a = 1 / (1 + base**((rating_b - rating_a) / scale))
    expected_score_b = 1 / (1 + base**((rating_a - rating_b) / scale))

    scored_point_a = 0.5 if winner == "tie" else int(winner == "model_a")

    rating[model_a] += k * (scored_point_a - expected_score_a)
    rating[model_b] += k * (1 - scored_point_a - expected_score_b)

  return {model: math.floor(rating + 0.5) for model, rating in rating.items()}


def load_elo_ratings(tab, source_lang: str | None, target_lang: str | None):
  category = db.Category.SUMMARIZATION if tab == LeaderboardTab.SUMMARIZATION else db.Category.TRANSLATION

  # TODO(#37): Call db.get_ratings and return the ratings if exists.

  battles = get_battles(category, source_lang, target_lang)
  if not battles:
    return

  computed_ratings = compute_elo(battles)

  db.set_ratings(
      category,
      [db.Rating(model, rating) for model, rating in computed_ratings.items()],
      source_lang, target_lang)

  sorted_ratings = sorted(computed_ratings.items(),
                          key=lambda x: x[1],
                          reverse=True)

  rank = 0
  last_rating = None
  rating_rows = []
  for index, (model, rating) in enumerate(sorted_ratings):
    if rating != last_rating:
      rank = index + 1

    rating_rows.append([rank, model, rating])
    last_rating = rating

  return rating_rows


LEADERBOARD_UPDATE_INTERVAL = 600  # 10 minutes
LEADERBOARD_INFO = "The leaderboard is updated every 10 minutes."

DEFAULT_FILTER_OPTIONS = {
    "summary_language": lingua.Language.ENGLISH.name.capitalize(),
    "source_language": ANY_LANGUAGE,
    "target_language": lingua.Language.ENGLISH.name.capitalize()
}


def update_filtered_leaderboard(tab, source_lang: str, target_lang: str):
  new_value = load_elo_ratings(tab, source_lang, target_lang)
  return gr.update(value=new_value)


def build_leaderboard():
  with gr.Tabs():
    with gr.Tab(LeaderboardTab.SUMMARIZATION.value):
      with gr.Accordion("Filter", open=False) as summarization_filter:
        with gr.Row():
          languages = [
              language.name.capitalize() for language in lingua.Language.all()
          ]
          summary_language = gr.Dropdown(
              choices=languages,
              value=DEFAULT_FILTER_OPTIONS["summary_language"],
              label="Summary language",
              interactive=True)

        with gr.Row():
          filtered_summarization = gr.DataFrame(
              headers=["Rank", "Model", "Elo rating"],
              datatype=["number", "str", "number"],
              value=lambda: load_elo_ratings(
                  LeaderboardTab.SUMMARIZATION, DEFAULT_FILTER_OPTIONS[
                      "summary_language"], None),
              elem_classes="leaderboard")

      summary_language.change(fn=update_filtered_leaderboard,
                              inputs=[
                                  gr.State(LeaderboardTab.SUMMARIZATION),
                                  summary_language,
                                  gr.State()
                              ],
                              outputs=filtered_summarization)

      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION,
                                                  None, None),
                   every=LEADERBOARD_UPDATE_INTERVAL,
                   elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

    with gr.Tab(LeaderboardTab.TRANSLATION.value):
      with gr.Accordion("Filter", open=False) as translation_filter:
        with gr.Row():
          source_language = gr.Dropdown(
              choices=SUPPORTED_TRANSLATION_LANGUAGES + [ANY_LANGUAGE],
              label="Source language",
              value=DEFAULT_FILTER_OPTIONS["source_language"],
              interactive=True)
          target_language = gr.Dropdown(
              choices=SUPPORTED_TRANSLATION_LANGUAGES + [ANY_LANGUAGE],
              label="Target language",
              value=DEFAULT_FILTER_OPTIONS["target_language"],
              interactive=True)

        with gr.Row():
          filtered_translation = gr.DataFrame(
              headers=["Rank", "Model", "Elo rating"],
              datatype=["number", "str", "number"],
              value=lambda: load_elo_ratings(
                  LeaderboardTab.TRANSLATION, DEFAULT_FILTER_OPTIONS[
                      "source_language"], DEFAULT_FILTER_OPTIONS[
                          "target_language"]),
              elem_classes="leaderboard")

          source_language.change(fn=update_filtered_leaderboard,
                                 inputs=[
                                     gr.State(LeaderboardTab.TRANSLATION),
                                     source_language, target_language
                                 ],
                                 outputs=filtered_translation)
          target_language.change(fn=update_filtered_leaderboard,
                                 inputs=[
                                     gr.State(LeaderboardTab.TRANSLATION),
                                     source_language, target_language
                                 ],
                                 outputs=filtered_translation)

      # When filter options are changed, the accordion keeps closed.
      # To avoid this, we open the accordion when the filter options are changed.
      summary_language.change(fn=lambda: gr.Accordion(open=True),
                              outputs=summarization_filter)
      source_language.change(fn=lambda: gr.Accordion(open=True),
                             outputs=translation_filter)
      target_language.change(fn=lambda: gr.Accordion(open=True),
                             outputs=translation_filter)

      gr.Dataframe(headers=["Rank", "Model", "Elo rating"],
                   datatype=["number", "str", "number"],
                   value=lambda: load_elo_ratings(LeaderboardTab.TRANSLATION,
                                                  None, None),
                   every=LEADERBOARD_UPDATE_INTERVAL,
                   elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

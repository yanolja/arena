"""
It provides a leaderboard component.
"""

from collections import defaultdict
import enum
import math
from typing import Dict, List, Tuple

import gradio as gr
import lingua

import db
from db import get_battles

SUPPORTED_LANGUAGES = [
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


def load_elo_ratings(tab, source_lang: str, target_lang: str | None):
  category = db.Category.SUMMARIZATION if tab == LeaderboardTab.SUMMARIZATION else db.Category.TRANSLATION

  # TODO(#37): Call db.get_ratings and return the ratings if exists.

  battles = get_battles(category,
                        None if source_lang == ANY_LANGUAGE else source_lang,
                        None if target_lang == ANY_LANGUAGE else target_lang)
  if not battles:
    return

  computed_ratings = compute_elo(battles)

  db.set_ratings(
      category,
      [db.Rating(model, rating) for model, rating in computed_ratings.items()],
      source_lang, target_lang)

  sorted_ratings = sorted(
      computed_ratings.items(),
      key=lambda x: x[1],  # rating
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


def update_filtered_leaderboard(tab: str, source_lang: str,
                                target_lang: str | None):
  new_value = load_elo_ratings(tab, source_lang, target_lang)
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
                                         ANY_LANGUAGE, None),
          elem_classes="leaderboard",
          visible=False)

      original_summarization = gr.Dataframe(
          headers=["Rank", "Model", "Elo rating"],
          datatype=["number", "str", "number"],
          value=lambda: load_elo_ratings(LeaderboardTab.SUMMARIZATION,
                                         ANY_LANGUAGE, None),
          every=LEADERBOARD_UPDATE_INTERVAL,
          elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

      summary_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.SUMMARIZATION), summary_language,
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
          value=lambda: load_elo_ratings(LeaderboardTab.TRANSLATION,
                                         ANY_LANGUAGE, ANY_LANGUAGE),
          every=LEADERBOARD_UPDATE_INTERVAL,
          elem_classes="leaderboard")
      gr.Markdown(LEADERBOARD_INFO)

      source_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.TRANSLATION), source_language,
              target_language
          ],
          outputs=filtered_translation).then(
              fn=toggle_leaderboard,
              inputs=source_language,
              outputs=[original_translation, filtered_translation])
      target_language.change(
          fn=update_filtered_leaderboard,
          inputs=[
              gr.State(LeaderboardTab.TRANSLATION), source_language,
              target_language
          ],
          outputs=filtered_translation).then(
              fn=toggle_leaderboard,
              inputs=target_language,
              outputs=[original_translation, filtered_translation])

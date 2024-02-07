"""
It provides a platform for comparing the responses of two LLMs. 
"""
import enum
import json
import os
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import gradio as gr

from leaderboard import build_leaderboard
import response
from response import get_responses

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

SUPPORTED_TRANSLATION_LANGUAGES = [
    "Korean", "English", "Chinese", "Japanese", "Spanish", "French"
]


class VoteOptions(enum.Enum):
  MODEL_A = "Model A is better"
  MODEL_B = "Model B is better"
  TIE = "Tie"


def vote(vote_button, response_a, response_b, model_a_name, model_b_name,
         user_prompt, instruction, category, source_lang, target_lang):
  doc_id = uuid4().hex
  winner = VoteOptions(vote_button).name.lower()

  doc = {
      "id": doc_id,
      "prompt": user_prompt,
      "instruction": instruction,
      "model_a": model_a_name,
      "model_b": model_b_name,
      "model_a_response": response_a,
      "model_b_response": response_b,
      "winner": winner,
      "timestamp": firestore.SERVER_TIMESTAMP
  }

  if category == response.Category.SUMMARIZE.value:
    doc_ref = db.collection("arena-summarizations").document(doc_id)
    doc_ref.set(doc)
    return

  if category == response.Category.TRANSLATE.value:
    doc_ref = db.collection("arena-translations").document(doc_id)
    doc["source_lang"] = source_lang.lower()
    doc["target_lang"] = target_lang.lower()
    doc_ref.set(doc)


with gr.Blocks(title="Arena") as app:
  with gr.Row():
    category_radio = gr.Radio(
        [category.value for category in response.Category],
        label="Category",
        info="The chosen category determines the instruction sent to the LLMs.")

    source_language = gr.Dropdown(
        choices=SUPPORTED_TRANSLATION_LANGUAGES,
        label="Source language",
        info="Choose the source language for translation.",
        interactive=True,
        visible=False)
    target_language = gr.Dropdown(
        choices=SUPPORTED_TRANSLATION_LANGUAGES,
        label="Target language",
        info="Choose the target language for translation.",
        interactive=True,
        visible=False)

    def update_language_visibility(category):
      visible = category == response.Category.TRANSLATE.value
      return {
          source_language: gr.Dropdown(visible=visible),
          target_language: gr.Dropdown(visible=visible)
      }

    category_radio.change(update_language_visibility, category_radio,
                          [source_language, target_language])

  model_names = [gr.State(None), gr.State(None)]
  response_boxes = [gr.State(None), gr.State(None)]

  prompt = gr.TextArea(label="Prompt", lines=4)
  submit = gr.Button()

  with gr.Row():
    response_boxes[0] = gr.Textbox(label="Model A", interactive=False)
    response_boxes[1] = gr.Textbox(label="Model B", interactive=False)

  # TODO(#5): Display it only after the user submits the prompt.
  # TODO(#6): Block voting if the category is not set.
  # TODO(#6): Block voting if the user already voted.
  with gr.Row():
    option_a = gr.Button(VoteOptions.MODEL_A.value)
    option_b = gr.Button("Model B is better")
    tie = gr.Button("Tie")

  # TODO(#7): Hide it until the user votes.
  with gr.Accordion("Show models", open=False):
    with gr.Row():
      model_names[0] = gr.Textbox(label="Model A", interactive=False)
      model_names[1] = gr.Textbox(label="Model B", interactive=False)

  instruction_state = gr.State("")

  submit.click(get_responses,
               [prompt, category_radio, source_language, target_language],
               response_boxes + model_names + [instruction_state])

  common_inputs = response_boxes + model_names + [
      prompt, instruction_state, category_radio, source_language,
      target_language
  ]
  option_a.click(vote, [option_a] + common_inputs)
  option_b.click(vote, [option_b] + common_inputs)
  tie.click(vote, [tie] + common_inputs)

  build_leaderboard(db)

if __name__ == "__main__":
  # We need to enable queue to use generators.
  app.queue()
  app.launch(debug=True)

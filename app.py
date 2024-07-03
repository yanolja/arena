"""
It provides a platform for comparing the responses of two LLMs. 
"""
import enum
from uuid import uuid4

from firebase_admin import firestore
import gradio as gr
import lingua

from leaderboard import build_leaderboard
from leaderboard import db
from leaderboard import SUPPORTED_LANGUAGES
from model import check_models
from model import supported_models
from rate_limit import set_token
import response
from response import get_responses

detector = lingua.LanguageDetectorBuilder.from_all_languages().build()


class VoteOptions(enum.Enum):
  MODEL_A = "Model A is better"
  MODEL_B = "Model B is better"
  TIE = "Tie"


def vote(vote_button, response_a, response_b, model_a_name, model_b_name,
         prompt, instruction, category, source_lang, target_lang):
  doc_id = uuid4().hex
  winner = VoteOptions(vote_button).name.lower()

  deactivated_buttons = [gr.Button(interactive=False) for _ in range(3)]
  outputs = deactivated_buttons + [gr.Row(visible=True)]

  doc = {
      "id": doc_id,
      "prompt": prompt,
      "instruction": instruction,
      "model_a": model_a_name,
      "model_b": model_b_name,
      "model_a_response": response_a,
      "model_b_response": response_b,
      "winner": winner,
      "timestamp": firestore.SERVER_TIMESTAMP
  }

  if category == response.Category.SUMMARIZE.value:
    language_a = detector.detect_language_of(response_a)
    language_b = detector.detect_language_of(response_b)

    doc_ref = db.collection("arena-summarizations").document(doc_id)
    doc["model_a_response_language"] = language_a.name.lower()
    doc["model_b_response_language"] = language_b.name.lower()
    doc_ref.set(doc)

    return outputs

  if category == response.Category.TRANSLATE.value:
    if not source_lang or not target_lang:
      raise gr.Error("Please select source and target languages.")

    doc_ref = db.collection("arena-translations").document(doc_id)
    doc["source_language"] = source_lang.lower()
    doc["target_language"] = target_lang.lower()
    doc_ref.set(doc)

    return outputs

  raise gr.Error("Please select a response type.")


# Removes the persistent orange border from the leaderboard, which
# appears due to the 'generating' class when using the 'every' parameter.
css = """
.leaderboard .generating {
  border: none;
}
"""

with gr.Blocks(title="Yanolja Arena", css=css) as app:
  set_token(app)

  with gr.Row():
    gr.HTML("""
    <h1 style="text-align: center; font-size: 28px; margin-bottom: 16px">Yanolja Arena</h1>
    <p style="text-align: center; font-size: 16px">Yanolja Arena helps find the best LLMs for summarizing and translating text. We compare two random models at a time and use an ELO rating system to score them.</p>
    <p style="text-align: center; font-size: 16px">This is an open-source project. Check it out on <a href="https://github.com/yanolja/arena">GitHub</a>.</p>
    """)
  with gr.Accordion("How to Use", open=False):
    gr.Markdown("""
      1. **For Summaries:**
        - Enter the text you want summarized into the prompt box.

      2. **For Translations:**
        - Choose the language you're translating from and to.
        - Enter the text you want translated into the prompt box.

      3. **Voting:**
        - After you see both results, pick which one you think is better.
      """)

  with gr.Row():
    category_radio = gr.Radio(
        choices=[category.value for category in response.Category],
        value=response.Category.SUMMARIZE.value,
        label="Category",
        info="The chosen category determines the instruction sent to the LLMs.")

    source_language = gr.Dropdown(
        choices=SUPPORTED_LANGUAGES,
        value="English",
        label="Source language",
        info="Choose the source language for translation.",
        interactive=True,
        visible=False)
    target_language = gr.Dropdown(
        choices=SUPPORTED_LANGUAGES,
        value="Spanish",
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

  prompt_textarea = gr.TextArea(label="Prompt", lines=4)
  submit = gr.Button()

  with gr.Group():
    with gr.Row():
      response_boxes[0] = gr.Textbox(label="Model A", interactive=False)

      response_boxes[1] = gr.Textbox(label="Model B", interactive=False)

    with gr.Row(visible=False) as model_name_row:
      model_names[0] = gr.Textbox(show_label=False)
      model_names[1] = gr.Textbox(show_label=False)

  with gr.Row(visible=False) as vote_row:
    option_a = gr.Button(VoteOptions.MODEL_A.value)
    option_b = gr.Button(VoteOptions.MODEL_B.value)
    tie = gr.Button(VoteOptions.TIE.value)

  instruction_state = gr.State("")

  # The following elements need to be reset when the user changes
  # the category, source language, or target language.
  ui_elements = [
      response_boxes[0], response_boxes[1], model_names[0], model_names[1],
      instruction_state, model_name_row, vote_row
  ]

  def reset_ui():
    return [gr.Textbox(value="") for _ in range(4)
           ] + [gr.State(""),
                gr.Row(visible=False),
                gr.Row(visible=False)]

  category_radio.change(fn=reset_ui, outputs=ui_elements)
  source_language.change(fn=reset_ui, outputs=ui_elements)
  target_language.change(fn=reset_ui, outputs=ui_elements)

  submit_event = submit.click(
      fn=lambda: [
          gr.Radio(interactive=False),
          gr.Dropdown(interactive=False),
          gr.Dropdown(interactive=False),
          gr.Button(interactive=False),
          gr.Row(visible=False),
          gr.Row(visible=False),
      ] + [gr.Button(interactive=True) for _ in range(3)],
      outputs=[
          category_radio, source_language, target_language, submit, vote_row,
          model_name_row, option_a, option_b, tie
      ]).then(fn=get_responses,
              inputs=[
                  prompt_textarea, category_radio, source_language,
                  target_language
              ],
              outputs=response_boxes + model_names + [instruction_state])
  submit_event.success(fn=lambda: gr.Row(visible=True), outputs=vote_row)
  submit_event.then(
      fn=lambda: [
          gr.Radio(interactive=True),
          gr.Dropdown(interactive=True),
          gr.Dropdown(interactive=True),
          gr.Button(interactive=True)
      ],
      outputs=[category_radio, source_language, target_language, submit])

  def deactivate_after_voting(option_button: gr.Button):
    option_button.click(
        fn=vote,
        inputs=[option_button] + response_boxes + model_names + [
            prompt_textarea, instruction_state, category_radio, source_language,
            target_language
        ],
        outputs=[option_a, option_b, tie, model_name_row]).then(
            fn=lambda: [gr.Button(interactive=False) for _ in range(3)],
            outputs=[option_a, option_b, tie])

  for option in [option_a, option_b, tie]:
    deactivate_after_voting(option)

  build_leaderboard()

if __name__ == "__main__":
  check_models(supported_models)

  # We need to enable queue to use generators.
  app.queue(api_open=False)
  app.launch(debug=True, show_api=False)

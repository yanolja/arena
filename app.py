"""
It provides a platform for comparing the responses of two LLMs. 
"""
import enum
from uuid import uuid4

from firebase_admin import firestore
import gradio as gr

from leaderboard import build_leaderboard
from leaderboard import db
from leaderboard import SUPPORTED_TRANSLATION_LANGUAGES
from models import check_models
from models import supported_models
import response
from response import get_responses


class VoteOptions(enum.Enum):
  MODEL_A = "Model A is better"
  MODEL_B = "Model B is better"
  TIE = "Tie"


def vote(vote_button, response_a, response_b, model_a_name, model_b_name,
         user_prompt, instruction, category, source_lang, target_lang):
  doc_id = uuid4().hex
  winner = VoteOptions(vote_button).name.lower()

  deactivated_buttons = [gr.Button(interactive=False) for _ in range(3)]
  outputs = deactivated_buttons + [gr.Row(visible=True)]

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


def scroll_to_bottom_js(elem_id):
  return f"""
  () => {{
    const element = document.querySelector("#{elem_id} textarea");
    element.scrollTop = element.scrollHeight;
  }}
  """


# Removes the persistent orange border from the leaderboard, which
# appears due to the 'generating' class when using the 'every' parameter.
css = """
.leaderboard .generating {
  border: none;
}
"""

with gr.Blocks(title="Arena", css=css) as app:
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

  with gr.Group():
    with gr.Row():
      response_a_elem_id = "responseA"
      response_a_textbox = gr.Textbox(label="Model A",
                                      interactive=False,
                                      elem_id=response_a_elem_id)
      response_a_textbox.change(fn=None,
                                js=scroll_to_bottom_js(response_a_elem_id))
      response_boxes[0] = response_a_textbox

      response_b_elem_id = "responseB"
      response_b_textbox = gr.Textbox(label="Model B",
                                      interactive=False,
                                      elem_id=response_b_elem_id)
      response_b_textbox.change(fn=None,
                                js=scroll_to_bottom_js(response_b_elem_id))
      response_boxes[1] = response_b_textbox

    with gr.Row(visible=False) as model_name_row:
      model_names[0] = gr.Textbox(show_label=False)
      model_names[1] = gr.Textbox(show_label=False)

  with gr.Row(visible=False) as vote_row:
    option_a = gr.Button(VoteOptions.MODEL_A.value)
    option_b = gr.Button(VoteOptions.MODEL_B.value)
    tie = gr.Button(VoteOptions.TIE.value)

  vote_buttons = [option_a, option_b, tie]
  instruction_state = gr.State("")

  submit.click(
      fn=get_responses,
      inputs=[prompt, category_radio, source_language, target_language],
      outputs=response_boxes + model_names + [instruction_state]).success(
          fn=lambda: [gr.Row(visible=True)
                     ] + [gr.Button(interactive=True) for _ in range(3)],
          outputs=[vote_row] + vote_buttons).then(
              fn=lambda: [gr.Button(interactive=True)], outputs=[submit])

  submit.click(fn=lambda: [
      gr.Button(interactive=False),
      gr.Row(visible=False),
      gr.Row(visible=False)
  ],
               outputs=[submit, vote_row, model_name_row])

  common_inputs = response_boxes + model_names + [
      prompt, instruction_state, category_radio, source_language,
      target_language
  ]
  common_outputs = vote_buttons + [model_name_row]
  option_a.click(vote, [option_a] + common_inputs, common_outputs)
  option_b.click(vote, [option_b] + common_inputs, common_outputs)
  tie.click(vote, [tie] + common_inputs, common_outputs)

  build_leaderboard()

if __name__ == "__main__":
  check_models(supported_models)

  # We need to enable queue to use generators.
  app.queue()
  app.launch(debug=True)

"""
This module handles the management of the database.
"""
import enum
import os
from typing import List

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1 import base_query
import gradio as gr

from credentials import get_credentials_json


def get_environment_variable(name: str) -> str:
  value = os.getenv(name)
  if value is None:
    raise ValueError(f"Environment variable {name} is not set")
  return value


RATINGS_COLLECTION = get_environment_variable("RATINGS_COLLECTION")
SUMMARIZATIONS_COLLECTION = get_environment_variable(
    "SUMMARIZATIONS_COLLECTION")
TRANSLATIONS_COLLECTION = get_environment_variable("TRANSLATIONS_COLLECTION")


class Category(enum.Enum):
  SUMMARIZATION = "summarization"
  TRANSLATION = "translation"


if gr.NO_RELOAD:
  firebase_admin.initialize_app(credentials.Certificate(get_credentials_json()))
  db = firestore.client()


class Rating:

  def __init__(self, model: str, rating: int):
    self.model = model
    self.rating = rating


def get_ratings(category: Category, source_lang: str | None,
                target_lang: str | None) -> List[Rating] | None:
  doc_id = "#".join([category.value] +
                    [lang for lang in (source_lang, target_lang) if lang])
  doc_dict = db.collection(RATINGS_COLLECTION).document(doc_id).get().to_dict()
  if doc_dict is None:
    return None

  # TODO(#37): Return the timestamp as well.
  doc_dict.pop("timestamp")

  return [Rating(model, rating) for model, rating in doc_dict.items()]


def set_ratings(category: Category, ratings: List[Rating],
                source_lang: str | None, target_lang: str | None):
  doc_id = "#".join([category.value] +
                    [lang for lang in (source_lang, target_lang) if lang])
  doc_ref = db.collection(RATINGS_COLLECTION).document(doc_id)

  batch = db.batch()
  for rating in ratings:
    batch.set(doc_ref, {rating.model: rating.rating}, merge=True)
  batch.set(doc_ref, {"timestamp": firestore.SERVER_TIMESTAMP}, merge=True)
  batch.commit()


class Battle:

  def __init__(self, model_a: str, model_b: str, winner: str):
    self.model_a = model_a
    self.model_b = model_b
    self.winner = winner


def get_battles(category: Category, source_lang: str | None,
                target_lang: str | None) -> List[Battle]:
  lower_source_lang = source_lang.lower() if source_lang else None
  lower_target_lang = target_lang.lower() if target_lang else None

  if category == Category.SUMMARIZATION:
    collection = db.collection(SUMMARIZATIONS_COLLECTION).order_by("timestamp")

    if lower_source_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "model_a_response_language", "==", lower_source_lang)).where(
              filter=base_query.FieldFilter("model_b_response_language", "==",
                                            lower_source_lang))

  elif category == Category.TRANSLATION:
    collection = db.collection(TRANSLATIONS_COLLECTION).order_by("timestamp")

    if lower_source_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "source_language", "==", lower_source_lang))

    if lower_target_lang:
      collection = collection.where(filter=base_query.FieldFilter(
          "target_language", "==", lower_target_lang))

  docs = collection.stream()
  battles = []
  for doc in docs:
    data = doc.to_dict()
    battles.append(Battle(data["model_a"], data["model_b"], data["winner"]))
  return battles

"""
This module handles the management of the database.
"""
from dataclasses import dataclass
import enum
import os
from typing import List

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1 import base_query
import gradio as gr

from credentials import get_credentials_json


def get_required_env(name: str) -> str:
  value = os.getenv(name)
  if value is None:
    raise ValueError(f"Environment variable {name} is not set")
  return value


RATINGS_COLLECTION = get_required_env("RATINGS_COLLECTION")
SUMMARIZATIONS_COLLECTION = get_required_env("SUMMARIZATIONS_COLLECTION")
TRANSLATIONS_COLLECTION = get_required_env("TRANSLATIONS_COLLECTION")

if gr.NO_RELOAD:
  firebase_admin.initialize_app(credentials.Certificate(get_credentials_json()))
  db = firestore.client()


class Category(enum.Enum):
  SUMMARIZATION = "summarization"
  TRANSLATION = "translation"


@dataclass
class Rating:
  model: str
  rating: int


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


def set_ratings(category: Category, ratings: List[Rating], source_lang: str,
                target_lang: str | None):
  lower_source_lang = source_lang.lower()
  lower_target_lang = target_lang.lower() if target_lang else None

  doc_id = "#".join([category.value, lower_source_lang] +
                    ([lower_target_lang] if lower_target_lang else []))
  doc_ref = db.collection(RATINGS_COLLECTION).document(doc_id)

  new_ratings = {rating.model: rating.rating for rating in ratings}
  new_ratings["timestamp"] = firestore.SERVER_TIMESTAMP
  doc_ref.set(new_ratings, merge=True)


@dataclass
class Battle:
  model_a: str
  model_b: str
  winner: str


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

  else:
    raise ValueError(f"Invalid category: {category}")

  docs = collection.stream()
  battles = []
  for doc in docs:
    data = doc.to_dict()
    battles.append(Battle(data["model_a"], data["model_b"], data["winner"]))
  return battles

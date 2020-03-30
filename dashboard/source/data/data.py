from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from random import choices
from typing import List
from urllib.parse import quote

import numpy as np
import requests
from imageio import imread

from .labels import CLASSES

# IMAGE_URL_INTERNAL = 'http://nginx/Raw/'
IMAGE_URL_INTERNAL = IMAGE_URL_EXTERNAL = 'http://localhost:1234/Raw/'
PREDICTION_URL_INTERNAL = 'http://tf_serving'


@dataclass
class GameData:
    items: List[Item] = field(init=False)
    current_round = 0
    max_rounds: int = 3
    validation_error: bool = False

    def __post_init__(self) -> None:
        self.items = self.get_raw_data()

    def get_raw_data(self) -> List[Item]:
        items = []

        # Send a requests to the static web server to retrieve a list with the content
        folder_content = requests.get(IMAGE_URL_INTERNAL).json()

        # Extract a list with all files in the folder
        file_list = [file['name'] for file in folder_content if file['type'] == 'file']

        # Sample randomly max rounds images from the list
        image_list = choices(file_list, k=self.max_rounds + 1)

        # Extract ground truth from the file name
        def extract_ground_truth(image_name: str) -> ItemLabel:
            print(image_name)
            image_parts = str.split(image_name, '_')
            return ItemLabel(image_parts[0], image_parts[1])

        ground_truth = map(extract_ground_truth, image_list)

        for image, truth in zip(image_list, ground_truth):
            prediction_ai = []

            for _ in range(5):
                # TODO: Fetch top 5 preds
                label = self.get_ai_prediction(image)
                # label = self.get_fake_label()
                # label.certainty = random()
                prediction_ai.append(label)

            items.append(
                Item(IMAGE_URL_EXTERNAL + image, 'TODO: explained image', prediction_ai,
                     truth))

        return items

    def get_ai_prediction(self, image_name: str) -> ItemLabel:
        # TODO: Return top 5 predictions for chart

        # Download Picture
        img_url = IMAGE_URL_EXTERNAL + quote(image_name)
        print('url', img_url)
        img = imread(img_url)

        # Get Prediction from TF Serving
        # Preprocess and reshape data
        img = img.reshape(-1, *img.shape)

        # Send data as list to TF serving via json dump
        request_url = 'http://localhost:8501/v1/models/resnet_unfreeze_all_filtered:predict'
        request_body = json.dumps({
            "signature_name": "serving_default",
            "instances": img.tolist()
        })
        request_headers = {"content-type": "application/json"}
        json_response = requests.post(request_url,
                                      data=request_body,
                                      headers=request_headers)
        response_body = json.loads(json_response.text)
        predictions = response_body['predictions']

        label = CLASSES[int(np.argmax(predictions, axis=1))]
        label_comp = label.split('_')
        brand = label_comp[0]
        model = label_comp[1]
        certainty = np.max(predictions)

        print('Input Image:', image_name)
        print('Prediction Brand:', brand)
        print('Prediction Model:', model)
        print('Certainty:', certainty)
        print('Raw Predictions:')
        print(predictions)

        return ItemLabel(brand, model, certainty)


@dataclass
class Item:
    picture_raw: Path
    picture_explained: Path
    prediction_ai: List[ItemLabel]
    ground_truth: ItemLabel
    prediction_user: ItemLabel = field(init=False)


@dataclass
class ItemLabel:
    brand: str
    model: str
    certainty: float = 1

    def __eq__(self, other) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        return (self.brand, self.model) == (other.brand, other.model)

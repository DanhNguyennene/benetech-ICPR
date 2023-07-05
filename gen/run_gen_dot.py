import argparse
import glob
import json
import os
import random
import sys
import warnings
from copy import deepcopy

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from src.dot_plot_base import BasicDotPlot
from src.dot_xy_generation import generate_from_synthetic
from src.generator_utils import generate_random_string, is_numeric
from tqdm.auto import tqdm

warnings.filterwarnings("ignore")


STOPWORDS = [
    "ISBN",
    "exit",
    "edit",
]


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


def generate_plot_data(cfg, synthetic_generator):
    generator = synthetic_generator

    try:
        data = next(generator)
    except Exception as e:
        data = next(synthetic_generator)

    x_series = list(deepcopy(data['x_series']))
    y_series = list(deepcopy(data['y_series']))

    # process underlying data ---

    if is_numeric(x_series):
        x_series = [float(x) for x in x_series]
        x_series = sorted(x_series)

    else:
        x_series = [str(x) for x in x_series]
        x_series = [x_val[:cfg.max_chars] for x_val in x_series]
        x_series = list(set(x_series))

    y_series = y_series[:len(x_series)]

   # max data points in a plot
    x_series = x_series[:cfg.max_points]
    y_series = y_series[:cfg.max_points]

    data['x_series'] = list(x_series)
    data['y_series'] = list(y_series)
    return data


def generate_annotation(data):
    data = deepcopy(data)
    x_mga = data['x_series']
    y_mga = data['y_series']

    chart_type = 'dot'
    if is_numeric(x_mga):
        x_type = 'numerical'
    else:
        x_type = 'categorical'

    y_type = 'numerical'

    data_series = []
    for xi, yi in zip(x_mga, y_mga):
        data_series.append(
            {
                'x': xi,
                'y': yi,
            }
        )

    annotation = dict()
    annotation['chart-type'] = chart_type

    annotation['axes'] = dict()
    annotation['axes']['x-axis'] = dict()
    annotation['axes']['x-axis']['values-type'] = x_type

    annotation['axes']['y-axis'] = dict()
    annotation['axes']['y-axis']['values-type'] = y_type

    annotation['data-series'] = data_series
    return annotation


def main(args, cfg):
    stem_df = pd.read_pickle(args.stem_path)
    stem_bank = dict(zip(stem_df["title"], stem_df["keywords"]))

    # process stem bank
    processed_stem_bank = dict()
    for key, values in stem_bank.items():
        key = key.replace("_", " ")
        values = [v for v in values if not v.startswith("[")]
        values = [v for v in values if not v in STOPWORDS]

        if len(values) >= 4:
            processed_stem_bank[key] = list(set(values))

    print(f"stem bank size: {len(processed_stem_bank)}")
    synthetic_generator = generate_from_synthetic(processed_stem_bank)

    # -- input/output ---
    os.makedirs(cfg.output.image_dir, exist_ok=True)
    os.makedirs(cfg.output.annotation_dir, exist_ok=True)
    texture_files = glob.glob(f"{args.texture_dir}/*.png")
    print(f"# texture files: {len(texture_files)}")

    p_bar = tqdm(range(cfg.num_images))
    for _ in range(cfg.num_images):
        base_image_id = f'syn_dot_{generate_random_string()}'
        the_example = generate_plot_data(cfg, synthetic_generator)

        # cast in the format of MGA
        mga_anno = generate_annotation(the_example)
        anno_path = os.path.join(cfg.output.annotation_dir, f"{base_image_id}.json")
        image_id = f"{base_image_id}"
        try:
            BasicDotPlot(cfg, the_example, texture_files=texture_files).make_dot_plot(image_id)
            with open(anno_path, "w") as f:
                json.dump(mga_anno, f, cls=NpEncoder)

        except Exception as e:
            print(e)
            print("--"*40)
            print(the_example)
            print("--"*40)
        p_bar.update()
    p_bar.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stem_path', type=str, required=True)
    ap.add_argument('--conf_path', type=str, required=True)
    ap.add_argument('--texture_dir', type=str, required=True)

    args = ap.parse_args()
    cfg = OmegaConf.load(args.conf_path)

    main(args, cfg)

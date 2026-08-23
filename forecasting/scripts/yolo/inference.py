from __future__ import annotations


import json

from pathlib import Path


import joblib

import numpy as np

import torch


from model import TrafficLSTM


from config import (

    MODEL_FILE,

    SCALER_FILE,

    METADATA_FILE,

)


class TrafficForecaster:

    def __init__(
        self,
        device=None,
    ):

        # ====================================================
        # DEVICE
        # ====================================================

        if device is None:

            device = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )


        self.device = torch.device(
            device
        )


        # ====================================================
        # METADATA
        # ====================================================

        if not METADATA_FILE.exists():

            raise FileNotFoundError(
                "Metadata model tidak ditemukan:\n"
                f"{METADATA_FILE}\n\n"
                "Jalankan train.py terlebih dahulu."
            )


        with open(
            METADATA_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            self.metadata = json.load(
                file
            )


        # ====================================================
        # CONFIG
        # ====================================================

        self.features = (
            self.metadata[
                "features"
            ]
        )


        self.input_size = (
            self.metadata[
                "input_size"
            ]
        )


        self.lookback = (
            self.metadata[
                "lookback"
            ]
        )


        self.horizon = (
            self.metadata[
                "horizon"
            ]
        )


        hidden_size = (
            self.metadata[
                "hidden_size"
            ]
        )


        num_layers = (
            self.metadata[
                "num_layers"
            ]
        )


        dropout = (
            self.metadata[
                "dropout"
            ]
        )


        # ====================================================
        # SCALER
        # ====================================================

        if not SCALER_FILE.exists():

            raise FileNotFoundError(
                "Scaler tidak ditemukan:\n"
                f"{SCALER_FILE}\n\n"
                "Jalankan train.py terlebih dahulu."
            )


        self.scaler = joblib.load(
            SCALER_FILE
        )


        # ====================================================
        # MODEL
        # ====================================================

        if not MODEL_FILE.exists():

            raise FileNotFoundError(
                "Model tidak ditemukan:\n"
                f"{MODEL_FILE}\n\n"
                "Jalankan train.py terlebih dahulu."
            )


        self.model = TrafficLSTM(

            input_size=self.input_size,

            hidden_size=hidden_size,

            num_layers=num_layers,

            horizon=self.horizon,

            output_size=self.input_size,

            dropout=dropout,

        )


        self.model.load_state_dict(
            torch.load(
                MODEL_FILE,
                map_location=self.device,
            )
        )


        self.model.to(
            self.device
        )


        self.model.eval()


    # ========================================================
    # PREDICT
    # ========================================================

    def predict(
        self,
        values,
    ):

        values = np.asarray(
            values,
            dtype=np.float32,
        )


        # ----------------------------------------------------
        # Validate shape
        # ----------------------------------------------------

        if values.ndim != 2:

            raise ValueError(
                "Input harus berbentuk "
                "[lookback, features]."
            )


        if values.shape[0] != (
            self.lookback
        ):

            raise ValueError(
                f"Dibutuhkan {self.lookback} "
                "timestep."
            )


        if values.shape[1] != (
            self.input_size
        ):

            raise ValueError(
                f"Dibutuhkan {self.input_size} "
                "features."
            )


        # ----------------------------------------------------
        # SCALE
        # ----------------------------------------------------

        scaled = (
            self.scaler.transform(
                values
            )
        )


        tensor = torch.tensor(
            scaled,
            dtype=torch.float32,
        )


        tensor = tensor.unsqueeze(
            0
        )


        tensor = tensor.to(
            self.device
        )


        # ----------------------------------------------------
        # PREDICT
        # ----------------------------------------------------

        with torch.no_grad():

            prediction = self.model(
                tensor
            )


        prediction = (
            prediction
            .cpu()
            .numpy()
            [0]
        )


        # ----------------------------------------------------
        # INVERSE SCALE
        # ----------------------------------------------------

        prediction = (
            self.scaler
            .inverse_transform(
                prediction
            )
        )


        # ----------------------------------------------------
        # CLAMP
        # ----------------------------------------------------

        prediction = np.maximum(
            prediction,
            0,
        )


        return prediction


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    forecaster = (
        TrafficForecaster()
    )


    print(
        "=" * 70
    )

    print(
        "TRAFFIC FORECASTER"
    )

    print(
        "Lookback:",
        forecaster.lookback,
    )

    print(
        "Horizon:",
        forecaster.horizon,
    )

    print(
        "Features:",
        forecaster.input_size,
    )

    print(
        "Device:",
        forecaster.device,
    )

    print(
        "=" * 70
    )
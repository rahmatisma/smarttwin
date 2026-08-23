from __future__ import annotations

import torch
import torch.nn as nn


class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        horizon: int,
        output_size: int,
        dropout: float = 0.2,
    ):

        super().__init__()

        self.horizon = horizon

        self.output_size = output_size

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=(
                dropout
                if num_layers > 1
                else 0.0
            ),
        )

        self.fc = nn.Sequential(
            nn.Linear(
                hidden_size,
                hidden_size,
            ),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(
                hidden_size,
                horizon * output_size,
            ),
        )

    def forward(self, x):

        output, _ = self.lstm(x)

        last_output = output[:, -1, :]

        prediction = self.fc(last_output)

        prediction = prediction.reshape(
            x.size(0),
            self.horizon,
            self.output_size,
        )

        return prediction
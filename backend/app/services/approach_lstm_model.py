from __future__ import annotations

from typing import Any
import torch
import torch.nn as nn


class SharedApproachLSTM(nn.Module):
    """Arsitektur serving yang sama dengan script training per-approach."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.output_steps = int(config["outputSteps"])
        self.output_size = int(config["outputSize"])
        num_layers = int(config["numLayers"])
        self.lstm = nn.LSTM(
            input_size=int(config["inputSize"]),
            hidden_size=int(config["hiddenSize"]),
            num_layers=num_layers,
            batch_first=True,
            dropout=float(config.get("dropout", 0.0)) if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(
            int(config["hiddenSize"]),
            self.output_steps * self.output_size,
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        sequence, _ = self.lstm(values)
        prediction = self.fc(sequence[:, -1, :])
        return prediction.view(-1, self.output_steps, self.output_size)



from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


class SumoController:
    """
    Controller untuk menjalankan SUMO dan berkomunikasi
    menggunakan TraCI.

    SUMO belum menjadi dependency wajib backend.
    Controller baru digunakan ketika SUMO integration
    sudah diaktifkan.
    """

    def __init__(
        self,
        sumo_binary: str = "sumo",
        config_file: str | Path | None = None,
        seed: int | None = None,
    ):
        self.sumo_binary = sumo_binary
        self.config_file = (
            Path(config_file)
            if config_file
            else None
        )
        self.seed = seed

        self.process = None
        self.traci = None

    def start(self) -> None:
        """
        Menjalankan SUMO melalui TraCI.
        """

        if self.config_file is None:
            raise ValueError(
                "config_file SUMO belum diberikan."
            )

        if not self.config_file.exists():
            raise FileNotFoundError(
                f"SUMO config tidak ditemukan: "
                f"{self.config_file}"
            )

        try:
            import traci
        except ImportError as exc:
            raise RuntimeError(
                "TraCI belum tersedia. "
                "Install package traci atau gunakan "
                "SUMO environment."
            ) from exc

        command = [
            self.sumo_binary,
            "-c",
            str(self.config_file),
        ]

        if self.seed is not None:
            command.extend(
                [
                    "--seed",
                    str(self.seed),
                ]
            )

        traci.start(command)

        self.traci = traci

    def set_traffic_state(
        self,
        demand: list[dict[str, Any]],
    ) -> None:
        """
        Mengirim traffic demand ke SUMO.

        Implementasi detail insertion/rerouting kendaraan
        bergantung pada route dan edge configuration SUMO.
        
        bagian set_traffic_state() belum kita isi penuh
        
        Kita belum tahu:

        edge ID
        lane ID
        route ID
        traffic light ID
        phase ID
        """

        if self.traci is None:
            raise RuntimeError(
                "SUMO belum dijalankan. "
                "Panggil start() terlebih dahulu."
            )

        for item in demand:

            edge_id = item["edge_id"]
            volume = int(item["volume"])

            # -------------------------------------------------
            # TODO:
            #
            # Cara memasukkan kendaraan ke SUMO harus mengikuti
            # route/flow configuration dari network kalian.
            #
            # Jangan langsung membuat vehicle setiap frame,
            # karena volume merupakan agregasi selama window.
            # -------------------------------------------------

            print(
                f"[SUMO] edge={edge_id} "
                f"volume={volume}"
            )

    def simulation_step(
        self,
        steps: int = 1,
    ) -> None:

        if self.traci is None:
            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        for _ in range(steps):
            self.traci.simulationStep()

    def close(self) -> None:

        if self.traci is not None:
            self.traci.close()
            self.traci = None
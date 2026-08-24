import traci
import time
import os
import shutil
import threading
from pathlib import Path

cache_dir = Path("cache/simulation")
cache_dir.mkdir(parents=True, exist_ok=True)
frame_path = cache_dir / "frame.jpg"

command = [
    "sumo-gui",
    "-c", "d:/project_smarttwin/smarttwin/simulation/network/simpang4_pingit.sumocfg",
    "--step-length", "1",
    "--no-step-log",
    "--seed", "42",
    "--delay", "100"
]

traci.start(command)
print("TraCI Started")
try:
    for i in range(10):
        traci.simulationStep()
        try:
            traci.gui.screenshot("View #0", str(frame_path.absolute()))
            print(f"Screenshot {i} saved. Exists: {frame_path.exists()}")
        except Exception as e:
            print(f"Failed screenshot: {e}")
        time.sleep(1)
finally:
    traci.close()

"""
Ambil snapshot data ASLI dari simulasi Pingit (bukan API/koneksi live —
ini cuma "jalanin sekali, ambil angkanya, tempel manual ke dashboard").

Cara pakai:
  cd simulation
  python snapshot_dashboard_data.py
"""
import os
import sys
import json
import math

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import traci
import sumolib

NET_PATH = "network/simpang4_pingit.net.xml.gz"
ROUTE_FILES = ",".join([
    "outputs/demo_motor.rou.xml",
    "outputs/demo_mobil.rou.xml",
    "outputs/demo_truk.rou.xml",
    "outputs/demo_bus.rou.xml",
])
CENTER_NODE_ID = "SIMPANG_CENTER"
SIM_DURATION_S = 300  # 5 menit simulasi


def classify_direction(angle_deg):
    """0 derajat = utara, searah jarum jam (konvensi kompas)."""
    if 45 <= angle_deg < 135:
        return "east"
    elif 135 <= angle_deg < 225:
        return "south"
    elif 225 <= angle_deg < 315:
        return "west"
    return "north"


def main():
    net = sumolib.net.readNet(NET_PATH)
    center = net.getNode(CENTER_NODE_ID)
    cx, cy = center.getCoord()

    edge_direction = {}
    edge_length_km = {}
    edge_lanes = {}
    for edge in net.getEdges():
        if edge.getToNode().getID() == CENTER_NODE_ID:
            fx, fy = edge.getFromNode().getCoord()
            angle = math.degrees(math.atan2(fx - cx, fy - cy)) % 360
            edge_direction[edge.getID()] = classify_direction(angle)
            edge_length_km[edge.getID()] = edge.getLength() / 1000
            edge_lanes[edge.getID()] = edge.getLaneNumber()

    print("Edge -> arah terdeteksi:")
    for eid, d in edge_direction.items():
        print(f"  {eid} -> {d}")
    if len(set(edge_direction.values())) < 4:
        print(
            "\nPERINGATAN: tidak semua 4 arah (utara/selatan/timur/barat) "
            "terdeteksi punya edge approach. Cek manual dengan netedit "
            "sebelum lanjut."
        )

    traci.start(["sumo", "-n", NET_PATH, "-r", ROUTE_FILES, "--no-warnings"])

    stats = {
        d: {
            "distinct_vehicles": set(),  # -> volume asli, bukan hitung ulang
            "speeds": [],
            "densities": [],
            "queue_max": 0,
        }
        for d in ["north", "south", "east", "west"]
    }

    for _ in range(SIM_DURATION_S):
        traci.simulationStep()
        for edge_id, direction in edge_direction.items():
            n = traci.edge.getLastStepVehicleNumber(edge_id)
            speed = traci.edge.getLastStepMeanSpeed(edge_id)
            halting = traci.edge.getLastStepHaltingNumber(edge_id)
            ids = traci.edge.getLastStepVehicleIDs(edge_id)

            stats[direction]["distinct_vehicles"].update(ids)
            if speed > 0:
                stats[direction]["speeds"].append(speed)
            stats[direction]["densities"].append(
                n / edge_length_km[edge_id] / edge_lanes[edge_id]
            )
            stats[direction]["queue_max"] = max(
                stats[direction]["queue_max"], halting
            )

    traci.close()

    result = []
    for d, s in stats.items():
        avg_speed_kmh = (
            (sum(s["speeds"]) / len(s["speeds"])) * 3.6 if s["speeds"] else 0
        )
        avg_density = (
            sum(s["densities"]) / len(s["densities"]) if s["densities"] else 0
        )
        result.append(
            {
                "approach": d,
                "volume": len(s["distinct_vehicles"]),  # kendaraan UNIK, bukan hitung ulang tiap detik
                "queueLengthM": round(s["queue_max"] * 7, 1),  # asumsi ~7m/kendaraan, dari titik antrean terpanjang teramati
                "densityVehPerKm": round(avg_density, 1),
                "avgSpeedKmh": round(avg_speed_kmh, 1),
            }
        )

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/approach_snapshot.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\nHasil (juga tersimpan di outputs/approach_snapshot.json):")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
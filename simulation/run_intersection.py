import os, sys

if "SUMO_HOME" not in os.environ:
    sys.exit("SUMO_HOME belum di-set — cek langkah 3")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import traci

net_path = "network/simpang4.net.xml.gz"
traci.start(["sumo", "-n", net_path, "--no-warnings"])

tls_id = traci.trafficlight.getIDList()[0]
print("Traffic light ID:", tls_id)
print("Fase sekarang:", traci.trafficlight.getPhase(tls_id))
print("State RYG:", traci.trafficlight.getRedYellowGreenState(tls_id))

for _ in range(10):
    traci.simulationStep()

traci.trafficlight.setPhase(tls_id, 0)
print("Setelah setPhase(0):", traci.trafficlight.getPhase(tls_id))

traci.close()
print("OK — koneksi TraCI, step simulasi, dan kontrol fase manual semua jalan")
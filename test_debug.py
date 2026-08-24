import traci
import time

command = ['sumo-gui', '-c', 'D:\\project_smarttwin\\smarttwin\\simulation\\network\\simpang4_pingit.sumocfg', '--step-length', '1', '--no-step-log', '--seed', '42']
print("Starting TraCI...")
traci.start(command)
print("TraCI Connected!")
tls = traci.trafficlight.getIDList()
print("Traffic lights:", tls)
print("Simulation step...")
traci.simulationStep()
print("Step success!")
traci.close()
print("Done")

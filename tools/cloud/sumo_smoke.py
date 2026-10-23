"""Build a tiny network and verify SUMO through its TraCI API."""
from pathlib import Path
import subprocess
import traci
import sumolib

root = Path('/workspace/lans-setup/sumo-demo')
root.mkdir(parents=True, exist_ok=True)
(root / 'nodes.nod.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="500" y="0"/><node id="c" x="1000" y="0"/></nodes>')
(root / 'edges.edg.xml').write_text('<edges><edge id="ab" from="a" to="b" numLanes="2" speed="13.9"/><edge id="bc" from="b" to="c" numLanes="2" speed="13.9"/></edges>')
subprocess.run([sumolib.checkBinary('netconvert'), '--node-files', str(root / 'nodes.nod.xml'), '--edge-files', str(root / 'edges.edg.xml'), '--output-file', str(root / 'network.net.xml')], check=True)
(root / 'routes.rou.xml').write_text('<routes><vType id="car" accel="2.6" decel="4.5" length="5" maxSpeed="13.9"/><route id="main" edges="ab bc"/><flow id="traffic" type="car" route="main" begin="0" end="30" number="10"/></routes>')
(root / 'demo.sumocfg').write_text('<configuration><input><net-file value="network.net.xml"/><route-files value="routes.rou.xml"/></input><time><begin value="0"/><end value="180"/></time></configuration>')
traci.start([sumolib.checkBinary('sumo'), '-c', str(root / 'demo.sumocfg'), '--tripinfo-output', str(root / 'tripinfo.xml'), '--no-step-log', 'true'])
departed = arrived = 0
observed_movement = False
try:
    print('Connected to SUMO:', traci.getVersion())
    for _ in range(180):
        traci.simulationStep()
        departed += traci.simulation.getDepartedNumber()
        arrived += traci.simulation.getArrivedNumber()
        for vehicle in traci.vehicle.getIDList():
            observed_movement |= traci.vehicle.getSpeed(vehicle) > 0
        if departed == 10 and traci.simulation.getMinExpectedNumber() == 0:
            break
    assert departed == 10 and arrived == 10 and observed_movement, (departed, arrived)
    print(f'PASS: {departed} vehicles departed, {arrived} arrived; movement verified via TraCI')
finally:
    traci.close()

"""
Ratakan roundabout jadi 1 junction tunggal, biar netconvert bisa generate
TLS default yang bersih (kayak simpang 4 biasa), bukan ring rumit.

Cara pakai:
  python flatten_roundabout.py network/simpang4_pingit.net.xml.gz
"""
import glob
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import sumolib

net_path = sys.argv[1]
prefix = "_flatten_tmp"

net = sumolib.net.readNet(net_path)
roundabouts = net.getRoundabouts()
if not roundabouts:
    sys.exit("Tidak ada roundabout terdeteksi di file ini — tidak perlu diratakan.")

rb = roundabouts[0]
ring_ids = set(rb.getNodes())
ring_edge_ids = set(rb.getEdges())
print(f"Node ring terdeteksi: {ring_ids}")
print(f"Edge ring terdeteksi: {ring_edge_ids}")

subprocess.run(
    ["netconvert", "--sumo-net-file", net_path, "--plain-output-prefix", prefix],
    check=True,
)

CENTER_ID = "SIMPANG_CENTER"

tree = ET.parse(f"{prefix}.nod.xml")
root = tree.getroot()
xs, ys = [], []
for node in list(root.findall("node")):
    if node.get("id") in ring_ids:
        xs.append(float(node.get("x")))
        ys.append(float(node.get("y")))
        root.remove(node)
cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
new_node = ET.SubElement(root, "node")
new_node.set("id", CENTER_ID)
new_node.set("x", f"{cx:.2f}")
new_node.set("y", f"{cy:.2f}")
new_node.set("type", "priority")
tree.write(f"{prefix}_flat.nod.xml", encoding="UTF-8", xml_declaration=True)

tree2 = ET.parse(f"{prefix}.edg.xml")
root2 = tree2.getroot()
for edge in list(root2.findall("edge")):
    if edge.get("id") in ring_edge_ids:
        root2.remove(edge)
        continue
    if edge.get("from") in ring_ids:
        edge.set("from", CENTER_ID)
    if edge.get("to") in ring_ids:
        edge.set("to", CENTER_ID)
for r in list(root2.findall("roundabout")):
    root2.remove(r)
tree2.write(f"{prefix}_flat.edg.xml", encoding="UTF-8", xml_declaration=True)

subprocess.run(
    [
        "netconvert",
        "--node-files", f"{prefix}_flat.nod.xml",
        "--edge-files", f"{prefix}_flat.edg.xml",
        "-o", net_path,
        "--tls.set", CENTER_ID,
        "--lefthand",
    ],
    check=True,
)
print(f"\nSelesai. Network ditulis ulang ke {net_path}, junction tunggal id='{CENTER_ID}'.")

# Bersihkan file perantara punya sendiri — kalau tidak, sisa _flatten_tmp*
# menumpuk di simulation/ tiap kali script ini dijalankan.
for f in glob.glob(f"{prefix}*"):
    os.remove(f)
print(f"File temporary ({prefix}*) sudah dibersihkan otomatis.")
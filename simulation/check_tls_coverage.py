import sumolib

net = sumolib.net.readNet("network/simpang4_pingit.net.xml.gz")
node = net.getNode("SIMPANG_CENTER")

conns = node.getConnections()
covered = [c for c in conns if c.getTLSID()]
uncovered = [c for c in conns if not c.getTLSID()]
major_uncovered = [c for c in uncovered if c.getState() == "M"]

print(f"Total koneksi fisik di junction: {len(conns)}")
print(f"Dikontrol TLS (aman, diatur lampu): {len(covered)}")
print(f"TIDAK dikontrol TLS (jalan prioritas M/m): {len(uncovered)}")
print(f"  -- dari situ, yang 'M' (major, gak pernah ngalah): {len(major_uncovered)}")
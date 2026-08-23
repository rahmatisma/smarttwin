import gzip
import xml.etree.ElementTree as ET

tree = ET.parse(gzip.open('d:/project_smarttwin/smarttwin/simulation/network/simpang4_pingit.net.xml.gz', 'rb'))
root = tree.getroot()
conns = root.findall('connection')

tls_conns = [c for c in conns if c.get('tl') == 'SIMPANG_CENTER']
tls_conns.sort(key=lambda x: int(x.get('linkIndex', -1)))

for c in tls_conns:
    print(f"Link {c.get('linkIndex')}: from {c.get('from')} to {c.get('to')} dir {c.get('dir')}")

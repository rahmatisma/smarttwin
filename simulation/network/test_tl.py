import gzip
import re
with gzip.open('simpang4_pingit.net.xml.gz', 'rt') as f:
    content = f.read()
connections = re.findall(r'<connection [^>]*tl="SIMPANG_CENTER"[^>]*>', content)
for c in connections:
    print(c)

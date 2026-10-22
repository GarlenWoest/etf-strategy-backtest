"""Crude standard-library PDF text extractor used in Phase 0.5 research.

Usage: python3 -I tools/pdftxt.py PAPER.pdf [MAX_CHARS] > trading-research/tmp/out.txt
Only handles FlateDecode streams with plain Tj/TJ text; font-encoded or
image-based PDFs come out empty or garbled. Treat output as approximate and
check numbers against the original. Read-only: never writes files itself.
"""
import re,sys,zlib
data=open(sys.argv[1],'rb').read()
out=[]
for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream',data,re.S):
    s=m.group(1)
    try: s=zlib.decompress(s)
    except Exception: continue
    # text in TJ/Tj operators
    for blk in re.findall(rb'BT(.*?)ET',s,re.S):
        parts=re.findall(rb'\((.*?)(?<!\\)\)|\[(.*?)\]\s*TJ',blk,re.S)
        line=b''
        for a,b in parts:
            if a: line+=a
            elif b: line+=b''.join(re.findall(rb'\((.*?)(?<!\\)\)',b))
        if line: out.append(line.decode('latin-1'))
txt='\n'.join(out)
print(txt[:int(sys.argv[2]) if len(sys.argv)>2 else 20000])

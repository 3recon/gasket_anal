"""Download a Google Patents page and dump every table as tab-separated text.
Usage: python patent_tables.py US7678858B2 [outdir]
Writes <outdir>/<id>.html and <outdir>/<id>_tables.txt and prints the tables.
"""
import sys, os, re, html, urllib.request
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")

class TP(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.stack=[]; self.cell=None; self.row=None
    def handle_starttag(self, tag, a):
        if tag=="table": self.stack.append([])
        elif tag=="tr" and self.stack: self.row=[]
        elif tag in("td","th") and self.stack: self.cell=[]
        elif tag in ("br","p") and self.cell is not None: self.cell.append(" ")
    def handle_endtag(self, tag):
        if tag in("td","th") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+"," ","".join(self.cell)).strip()); self.cell=None
        elif tag=="tr" and self.row is not None and self.stack:
            self.stack[-1].append(self.row); self.row=None
        elif tag=="table" and self.stack:
            self.tables.append(self.stack.pop())
    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)

def fetch(pid, outdir):
    os.makedirs(outdir, exist_ok=True)
    fn=os.path.join(outdir, pid+".html")
    if not os.path.exists(fn):
        url=f"https://patents.google.com/patent/{pid}/en"
        req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r: open(fn,"wb").write(r.read())
    return open(fn,encoding="utf-8",errors="ignore").read()

if __name__=="__main__":
    pid=sys.argv[1]; outdir=sys.argv[2] if len(sys.argv)>2 else "pat"
    h=fetch(pid,outdir)
    title=re.search(r"<title>(.*?)</title>",h,re.S)
    p=TP(); p.feed(h)
    out=[f"# {pid} :: {html.unescape(title.group(1).strip()) if title else ''}"]
    for i,t in enumerate(p.tables):
        if not t: continue
        out.append(f"\n=== TABLE {i} ({len(t)} rows) ===")
        for r in t: out.append("\t".join(html.unescape(c) for c in r))
    s="\n".join(out)
    open(os.path.join(outdir,pid+"_tables.txt"),"w",encoding="utf-8").write(s)
    print(s)

import sys
sys.path.insert(0, ".")
from collections import Counter
from pathlib import Path
from app import db
from app.config import get_settings

conn = db.connect(get_settings().database_url)
in_db = {Path(p).as_posix() for p in db.ingested_files(conn)}

def top(p, depth=7):
    parts = Path(p).parts
    return "/".join(parts[:depth])

disk = Counter()
for f in Path("data/raw/kafka/clients/src/main").rglob("*"):
    if f.suffix in (".java", ".scala"):
        disk[top(f.relative_to("data/raw/kafka"))] += 1
have = Counter(top(p) for p in in_db if p.startswith("clients/src/main"))
print("directory: in database / on disk")
for d in sorted(disk):
    print(f"{d}: {have.get(d, 0)} / {disk[d]}")

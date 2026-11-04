import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app import db
from app.config import get_settings

conn = db.connect(get_settings().database_url)
print("chunks per module:", db.count_chunks(conn))
indexed = {Path(p).name for p in db.ingested_files(conn)}
print("distinct files with embeddings:", len(indexed))
print()

total = have = 0
for key_path in sorted(Path("eval/answer_keys").glob("q*.json")):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    files = sorted({Path(s["file"]).name for s in key.get("steps", [])})
    if not files:
        continue
    missing = [f for f in files if f not in indexed]
    total += len(files)
    have += len(files) - len(missing)
    print(key_path.stem, f"in database {len(files) - len(missing)}/{len(files)}",
          ("missing: " + ", ".join(missing)) if missing else "")
print()
print(f"overall: {have}/{total} key files are in the database")

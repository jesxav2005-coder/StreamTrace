# Progress

## Week 1: project card and README
- Chose the project: StreamTrace, which follows a message through Apache Kafka's code across many modules.
- README written in the template's section order (problem, who it is for, signature feature, hardest problem, dataset, 10 real questions, run it, live link).
- Repo created from the GenAI starter template, with a live link on Render.

## Week 2: FastAPI app and CI
- FastAPI app with `/health`, `/chat` (primary model with a fallback model) and `/usage` (token and cost log).
- Tests and GitHub Actions CI (ruff and pytest) in place.
- Questions and a first set of answer keys written.

## Week 3: ingestion, search and planner

**Done**
- Chunker splits each Java and Scala file into chunks of about 60 lines that overlap by 10. It skips Kafka's licence header, but line numbers still count from the top of the file, so citations stay correct.
- Embeddings use `gemini-embedding-001` (768 dimensions) through an OpenAI-compatible client, with waits and retries when the API is rate limited.
- Chunks are stored in Postgres with pgvector (Docker, port 5433). `python -m app.ingest` is safe to stop and rerun, because it skips files that are already stored.
- Endpoints: `/search` (closest chunks with file and line citations), `/ask` (one search, then a cited step list) and `/trace` (planner splits the question into sub-questions, searches each one, then writes one cited path).
- 35 tests pass and CI is green.
- Answer keys for 10 questions are in `eval/answer_keys/`.

**Numbers so far**
- Stored: 414 files and 1,965 chunks (clients 208 files, core 67, storage 139).
- A single broad question ("what happens with acks=all") returned mostly the right files once `ReplicaManager.scala` and `KafkaApis.scala` were stored, but it missed the log write and the replication wait. That is why the planner exists.

**Problems found**
- The Gemini free tier allows 30,000 embedding tokens per minute and 1,000 requests per day, so ingestion takes several days. The ingest code now waits out the per-minute limit.
- Gemini sometimes leaves the embedding `index` empty, which crashed sorting. Fixed.
- The Docker database container stops when the computer restarts. Restart it with `docker start streamtrace-db`.

**Next**
- Reach 500+ files, then run the 10 questions through `/trace` and fill in `EVAL_v0.md`.
- Check that citations point to real file and line ranges.
- Add the raft and coordinator modules once the quota allows.

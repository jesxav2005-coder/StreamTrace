# StreamTrace design

Status: Week 3. Sections marked current exist in the code today. Sections marked planned are the design for later weeks and may change.

## Overview

StreamTrace answers questions about how a request moves through the Apache Kafka source code. An engineer asks a question, and StreamTrace returns a numbered step list where each step cites a file and line range.

Week 2 built the foundation: a FastAPI service that calls a language model reliably (with a fallback model), tracks tokens and cost, and runs in Docker with CI.

Week 3 adds the code index and search: Kafka source files are split into chunks, embedded, stored in Postgres with pgvector, and searched. A planner splits a broad question into sub-questions and searches for each one.

## How a question is answered (current)

1. **Plan.** The LLM splits the question into 3 to 5 short search questions, in the order the request flows through the system, each with an optional module hint (clients, core or storage). If the plan cannot be read, the original question is searched instead.
2. **Retrieve.** Each sub-question is embedded and compared with the stored chunks by cosine similarity, limited to the hinted modules.
3. **Join.** Duplicate chunks are removed and the rest are numbered [1], [2], and so on.
4. **Answer.** The LLM writes a numbered step list from those chunks only, citing each step as [n]. If the chunks do not cover part of the question, it says what is missing instead of guessing.

`/search` runs step 2 only. `/ask` runs one search and step 4. `/trace` runs all four steps.

## API endpoints (current)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | /health | Liveness check. Fast, never calls the LLM or the database. |
| POST | /chat | Send a prompt to the primary model, fall back to the second model if it fails. |
| POST | /search | Embed the question and return the closest code chunks with file and line citations. |
| POST | /ask | One search, then the LLM writes a cited step list from the chunks found. |
| POST | /trace | Plan sub-questions, search for each, merge the chunks, then write one cited step list. |
| GET | /usage | Totals for calls, tokens and cost, plus the most recent calls. |

### GET /health

Response 200:

```json
{"status": "ok", "app": "examate-rag", "environment": "local"}
```

### POST /chat

Request:

```json
{"prompt": "Say hello in one sentence", "system": null}
```

- `prompt`: required, 1 to 8,000 characters.
- `system`: optional, up to 4,000 characters.

Response 200:

```json
{
  "answer": "Hello there!",
  "model": "gemini-2.5-flash",
  "fallback_used": false,
  "prompt_tokens": 8,
  "completion_tokens": 3,
  "cost_usd": 0.0,
  "latency_ms": 2638
}
```

Errors:

| Code | Meaning |
| ---- | ------- |
| 422 | The request body is invalid (for example an empty prompt). |
| 502 | The primary and fallback models both failed. |
| 503 | The LLM is not configured (no API key or primary model). |

### POST /search, /ask and /trace

All three take the same request:

```json
{"question": "Where is log retention enforced?", "k": 8, "modules": ["storage", "core"]}
```

- `question`: required, at least 3 characters.
- `k`: how many chunks to return, 1 to 20, default 8. (`/trace` uses 4 per sub-question.)
- `modules`: optional list to search only some modules. Leave it out to search everything.

`/search` returns `{"question": "...", "results": [Source, ...]}`.

`/ask` returns `{"question": "...", "answer": "...", "model": "...", "sources": [Source, ...]}`.

`/trace` returns the same as `/ask`, plus `"plan"`: the list of sub-questions that were searched.

Each Source:

```json
{
  "n": 1,
  "module": "core",
  "file_path": "core/src/main/scala/kafka/cluster/Partition.scala",
  "start_line": 1020,
  "end_line": 1076,
  "citation": "core/src/main/scala/kafka/cluster/Partition.scala:1020-1076",
  "score": 0.77,
  "content": "...the chunk text..."
}
```

`score` is cosine similarity. Scores close together (for example all between 0.65 and 0.69) mean the search did not find a clear match.

Errors:

| Code | Meaning |
| ---- | ------- |
| 404 | No code has been ingested yet (`/ask` and `/trace`). |
| 422 | The request body is invalid. |
| 429 | The embedding quota is used up. Try again later. |
| 502 | The primary and fallback models both failed (`/ask` and `/trace`). |
| 503 | The search or the LLM is not configured or not reachable. |

### GET /usage

Query parameter `recent` (0 to 100, default 10) sets how many recent calls to return.

Response 200:

```json
{
  "total_calls": 7,
  "successful_calls": 2,
  "failed_calls": 5,
  "fallback_calls": 3,
  "prompt_tokens": 16,
  "completion_tokens": 12,
  "total_tokens": 28,
  "cost_usd": 0.0,
  "recent": [
    {
      "timestamp": 1793082686.97,
      "role": "fallback",
      "model": "gemini-3.5-flash-lite",
      "ok": true,
      "prompt_tokens": 8,
      "completion_tokens": 9,
      "cost_usd": 0.0,
      "latency_ms": 931,
      "error": null
    }
  ]
}
```

Each model attempt counts as one call, so a request that falls back counts as two. Embedding calls are not counted here.

## LLM calls and fallback (current)

- `LLMService.complete()` calls the primary model.
- If the call fails (any error from the API client), the failure is logged and the fallback model is tried.
- If both fail, the endpoint returns 502.
- The provider is any OpenAI-compatible API. It is set by `LLM_BASE_URL`. Today it is Google's Gemini endpoint.
- The client does not retry on its own (`max_retries=0`), so a failure moves to the fallback straight away.
- The log stores only the error class name, never the API key or the prompt text.

## Ingestion and search (current)

### Chunking

Each Java and Scala file is split into chunks of about 60 lines that overlap by 10 lines. Kafka's licence header is skipped, but line numbers still count from the top of the file, so a citation matches the real file. Test folders are skipped unless asked for.

### Embeddings

Chunks are embedded with `gemini-embedding-001` at 768 dimensions, through the same OpenAI-compatible client. The text that is embedded starts with the file path and line range, so file and class names help the match. When the API is rate limited the code waits (15 seconds, then longer, up to 65 seconds) and retries up to 8 times. Questions use 2 tries so a used-up quota fails quickly.

### Ingest command

```
python -m app.ingest --modules core storage clients --max-files 120
```

- `--dry-run` counts files, chunks and tokens without calling the API.
- Files that are already stored are skipped, so the command is safe to stop and rerun.
- All chunks of a file are stored together, so a file is either fully stored or not stored.

### Search

`db.search()` returns the k chunks with the smallest cosine distance to the question's embedding, optionally limited to some modules. An HNSW index keeps this fast.

## Data

### Usage log (current)

One JSON object per line in `logs/usage.jsonl`. The file is read at startup so totals survive a restart. It is not committed to Git.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| timestamp | float | Unix time of the call. |
| role | string | primary or fallback. |
| model | string | Model name that was called. |
| ok | bool | Whether the call succeeded. |
| prompt_tokens | int | Input tokens (0 on failure). |
| completion_tokens | int | Output tokens (0 on failure). |
| cost_usd | float | Tokens times the configured price per million tokens. |
| latency_ms | int | Time taken by the call. |
| error | string or null | Error class name when ok is false. |

### chunks table (current)

Stored in Postgres 16 with the pgvector extension, running in Docker on port 5433.

| Column | Type | Notes |
| ------ | ---- | ----- |
| id | bigserial | Primary key. |
| module | text | For example clients, core, storage. Used to search one module at a time. |
| file_path | text | Path inside the Kafka repository. |
| start_line | integer | First line of the chunk. Needed for citations. |
| end_line | integer | Last line of the chunk. |
| content | text | The code itself. |
| embedding | vector(768) | For vector search (pgvector). |

- Unique on (file_path, start_line, end_line), so reruns never create duplicates.
- Indexes: one on `module`, and an HNSW index on `embedding` using cosine distance.
- The earlier draft had a `symbol` column (class or method name). It was dropped for now to keep chunking simple.

### Planned tables

`eval_questions` and `eval_runs`: the hand-written answer key and the scored results for the 60-question evaluation. Today the first 10 answer keys are JSON files in `eval/answer_keys/`.

## Configuration (current)

All settings are environment variables, read from `.env` locally. Real values are never committed. Hosts get them from their own settings page.

| Variable | Purpose |
| -------- | ------- |
| LLM_API_KEY | Provider API key. |
| LLM_BASE_URL | Provider endpoint. Empty uses the default. |
| LLM_PRIMARY_MODEL | Model tried first. |
| LLM_FALLBACK_MODEL | Model tried if the primary fails (optional). |
| LLM_TIMEOUT_SECONDS | Per-call timeout. Default 30. |
| PRIMARY_INPUT_PRICE_PER_M, PRIMARY_OUTPUT_PRICE_PER_M | Primary model price in USD per

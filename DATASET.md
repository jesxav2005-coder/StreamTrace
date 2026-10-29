# Dataset

| File | Source URL | Pages | Licence / terms | Downloaded on |
| ---- | ---------- | ----- | --------------- | ------------- |
| Apache Kafka source code (Java and Scala), `trunk` branch | https://github.com/apache/kafka | n/a (source code, 6,528 Java and Scala files) | Apache-2.0 | 23 Oct 2026 |

Full data lives in `data/raw/` (not committed). A 2–3 file sample is in `data/sample/`.

## What the data is

The public source code of Apache Kafka. StreamTrace answers questions about how a request moves through this code, so the dataset is the code itself, not documents or pages.

- **Language:** Java and Scala.
- **Size:** 6,528 `.java` and `.scala` files across the whole repository (about 7,400 files in total, including build and config files).
- **Version:** latest `trunk` commit on the download date, `b860fd33a700d18f4203d1553f878bd66059e539`.
- **Modules used first:** `clients`, `core`, `storage`.
- **Modules added later:** `raft`, `group-coordinator`, `connect`, `streams`, and broker folders such as `server`, `server-common` and `metadata`.

## Sample files (committed)

Three small, unmodified files in `data/sample/`, one per starting module:

| File | Module |
| ---- | ------ |
| `Partitioner.java` | clients |
| `Server.scala` | core |
| `RemoteLogReader.java` | storage |

Each file keeps Kafka's Apache-2.0 licence header.

## How to download the full data

The full source is not stored in this repository. To get it:

```
git clone --depth 1 https://github.com/apache/kafka data/raw/kafka
```

Or run the downloader, which also writes a record of every file to `data/manifest.csv`:

```
python tool/download.py
```

`data/raw/` is listed in `.gitignore`, so it never gets committed.

## What is included and excluded

**Included**

- All `.java` and `.scala` files in the repository, including test code. Tests show how the main code is used, so they are kept in the 6,528 files. Retrieval can filter by path (for example, skip `src/test`) when a question is about production code.

**Excluded**

- The top-level `tests/` folder (Kafka's system-test setup). It contains a test SSH key that GitHub's push protection blocks, and it has no Java or Scala files.
- Build output, generated files, docs and scripts.

## Terms and attribution

Apache Kafka is licensed under Apache-2.0, which allows use and redistribution with the licence and notices kept. StreamTrace is not affiliated with or endorsed by the Apache Software Foundation. Apache, Apache Kafka and Kafka are trademarks of the Apache Software Foundation.

## Notes

- Line numbers change between Kafka releases, so the commit above is pinned. Citations in answers refer to that version.
- The file count was taken from a copy at that commit. Re-run the count on your own `data/raw/kafka` if you change the version:
  ```
  Get-ChildItem data/raw/kafka -Recurse -Include *.java,*.scala | Measure-Object
  ```

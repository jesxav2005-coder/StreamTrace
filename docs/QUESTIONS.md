| # | Question | Modules likely involved |
|---|----------|-------------------------|
| 1 | Trace what happens inside the broker when a producer sends a batch with acks=all. | clients, core, storage, server |
| 2 | Which code path triggers a consumer group rebalance when a member stops sending heartbeats? | clients, group-coordinator |
| 3 | Where is log retention enforced, and what decides which segment gets deleted? | storage, core |
| 4 | How does the producer client batch records and decide when to send them (batch size and linger time)? | clients |
| 5 | How is a consumer fetch request served, from the request arriving at the broker to the response leaving? | clients, core, storage |
| 6 | What happens when a partition leader fails, and how is a new leader chosen through KRaft? | metadata, raft, core |
| 7 | How does the broker detect and drop duplicate records from an idempotent producer? | clients, storage, core |
| 8 | Where are consumer offset commits handled, and where are they stored? | clients, group-coordinator, coordinator-common, core |
| 9 | When does a follower get removed from the in-sync replica set, and which code decides it? | core, server, metadata |
| 10 | What is the monthly cost of running a three-broker Kafka cluster on AWS? | none (cannot be answered from the code) |
| 11 | What happens in the broker when a producer calls `commitTransaction()`? | clients, transaction-coordinator, core, storage |
| 12 | How does a producer get its producer ID and epoch when idempotence is enabled? | clients, core, transaction-coordinator |
| 13 | Where is `delivery.timeout.ms` enforced, and what happens to a batch that expires? | clients |
| 14 | After a leader change, how does a follower detect that its log diverged and truncate it? | core, storage |
| 15 | What happens inside the broker during a controlled shutdown, from the shutdown request to the leaders moving away? | core, metadata |
| 16 | How is the high watermark advanced on the leader, and where is it checkpointed to disk? | core, storage |
| 17 | How does the log cleaner choose which log to compact, and how does it rewrite segments? | storage, core |
| 18 | After an unclean shutdown, how does the broker recover its log segments and rebuild indexes? | storage, core |
| 19 | How does the server-side consumer group assignor (new protocol) assign partitions when a new member joins? | group-coordinator, clients |
| 20 | How does a new broker register with the KRaft controller at startup and receive its metadata? | core, metadata, raft, server |

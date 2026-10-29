# 10 real questions

Questions an on-call engineer would ask about Apache Kafka. Questions 1 to 9 need steps from several modules, so no single file answers them. Question 10 cannot be answered from the source code, and StreamTrace should say so instead of guessing.

| # | Question | Modules likely involved |
| - | -------- | ----------------------- |
| 1 | Trace what happens inside the broker when a producer sends a batch with acks=all. | clients, core, storage |
| 2 | Which code path triggers a consumer group rebalance when a member stops sending heartbeats? | clients, group-coordinator |
| 3 | Where is log retention enforced, and what decides which segment gets deleted? | storage, core |
| 4 | How does the producer client batch records and decide when to send them (batch size and linger time)? | clients |
| 5 | How is a consumer fetch request served, from the request arriving at the broker to the response leaving? | clients, core, storage |
| 6 | What happens when a partition leader fails, and how is a new leader chosen through KRaft? | raft, core |
| 7 | How does the broker detect and drop duplicate records from an idempotent producer? | clients, core, storage |
| 8 | Where are consumer offset commits handled, and where are they stored? | clients, group-coordinator |
| 9 | When does a follower get removed from the in-sync replica set, and which code decides it? | core, server |
| 10 | What is the monthly cost of running a three-broker Kafka cluster on AWS? | none (cannot be answered from the code) |

## How these will be used

- Questions 1 to 9 each get a hand-written answer key: the correct ordered steps, with file references.
- StreamTrace's answer is scored on whether the step chain is complete and correct.
- Question 10 checks that StreamTrace says "I don't know" when the code has no answer, instead of inventing one.
- The 60-question evaluation set extends these 10.

## Notes

- The modules column is my first guess. Check it against the real code when you write the answer key.
- Questions 1 to 3 come from the project card.

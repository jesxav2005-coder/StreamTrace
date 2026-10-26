10 real questions my user will ask

StreamTrace | Apache Kafka source-code tracing | Week 1

Written as realistic questions from an on-call engineer. Questions 1–9 require code-backed answers; question 10 is intentionally outside the source-code dataset.

#

Question

Where the answer is (document, page)

Needs more than one page?

1

Our shipment producer uses acks=all. Where does its batch go from KafkaProducer.send() to the broker log, and when does Kafka send success back?

clients/.../KafkaProducer.java; clients/.../Sender.java; core/.../KafkaApis.scala; core/.../ReplicaManager.scala; delayed produce handling

Yes

2

One of our shipment-tracking consumers stopped heartbeating. Which code detects the timeout and starts a group rebalance?

clients/.../ConsumerCoordinator.java; group-coordinator/.../GroupMetadataManager.java (version-dependent)

Yes

3

Our brokers are running out of disk space. Where does Kafka check retention.ms and retention.bytes, and how does it choose segments to delete?

storage/.../UnifiedLog.java; storage/.../LocalLog.java; broker log-retention scheduler (version-dependent)

Yes

4

A broker that leads a shipment topic went offline. How does KRaft elect a replacement leader and tell the other brokers?

metadata/.../ReplicationControlManager.java; raft/.../KafkaRaftClient.java; broker metadata processing

Yes

5

A producer got NOT_ENOUGH_REPLICAS. Which code checks min.insync.replicas, and why does it reject the write?

core/.../ReplicaManager.scala; storage/.../UnifiedLog.java; produce error handling

Yes

6

Our producer keeps retrying a failed send. Which methods decide whether an error is retriable and when the next attempt happens?

clients/.../Sender.java; clients/.../RecordAccumulator.java; producer retry configuration

Yes

7

A consumer committed an offset but restarted at an older position. How does the offset commit reach the coordinator and get stored?

clients/.../ConsumerCoordinator.java; group-coordinator/.../OffsetMetadataManager.java; __consumer_offsets

Yes

8

A follower replica is lagging behind the leader. Which code fetches new records and updates replication progress?

core/.../ReplicaFetcherThread.scala; core/.../ReplicaManager.scala; storage log append code

Yes

9

We enabled compression on the producer. Where is the record batch compressed, and how is it validated and appended by the broker?

clients/.../MemoryRecordsBuilder.java; clients/.../Sender.java; storage/.../UnifiedLog.java

Yes

10

What is the current CPU usage and free RAM of our production Kafka broker in Chennai?

None — live monitoring/metrics required; not answerable from the Kafka source repository

No

Source-location note: Kafka uses source files and line ranges rather than document pages. The paths above are candidate starting points, not verified citations. Replace them with exact paths and line ranges from your pinned Kafka commit after inspecting the code.


# 10 real questions my user will ask

Write them the way your user would type them. At least 3 must need more than one page to answer, and at least 1 must be a question your documents cannot answer.

| # | Question | Where the answer is (document, page) | Needs more than one page? |
|---|---|---|---|
| 1 | What happens inside Kafka when a producer sends a batch with acks=all? Which files handle the request from the producer client to the broker and disk? | KafkaProducer.java, Sender.java, KafkaApis.scala, ReplicaManager.scala, DelayedProduce.scala | Yes |
| 2 | My Kafka consumer stopped sending heartbeats. Which code detects the timeout, and how does it trigger a consumer group rebalance? | AbstractCoordinator.java, ConsumerCoordinator.java, GroupCoordinatorService.java, GroupMetadataManager.java | Yes |
| 3 | Kafka is deleting old messages from my topic. Where is log retention enforced, and how does Kafka decide which log segments to delete? | UnifiedLog.java, LocalLog.java, LogManager.java | Yes |
| 4 | A Kafka broker suddenly crashes. How does Kafka recover its partition logs and restore broker state after restarting? | LogManager.java, UnifiedLog.java, ReplicaManager.scala | Yes |
| 5 | My Kafka producer keeps retrying failed messages. Which functions handle retries, and how does Kafka decide when to stop retrying? | KafkaProducer.java, Sender.java, RecordAccumulator.java | Yes |
| 6 | When a consumer commits an offset, which functions process the request, and where does Kafka store the committed offset? | KafkaConsumer.java, ConsumerCoordinator.java, GroupCoordinatorService.java, OffsetMetadataManager.java | Yes |
| 7 | How does Kafka replicate messages from a leader partition to follower replicas, and which code tracks replication progress? | ReplicaManager.scala, Partition.scala, ReplicaFetcherThread.scala | Yes |
| 8 | When I enable compression in a Kafka producer, where does Kafka compress the records, and how does the broker handle the compressed batch? | KafkaProducer.java, ProducerBatch.java, MemoryRecordsBuilder.java, LogValidator.java | Yes |
| 9 | When a Kafka partition leader becomes unavailable, how does the KRaft controller elect a new leader and update the brokers? | QuorumController.java, ReplicationControlManager.java, BrokerHeartbeatManager.java | Yes |
| 10 | What is the current CPU usage and available memory of our production Kafka broker in Chennai? | None - cannot be answered from the Apache Kafka source code. Requires live monitoring data such as Prometheus or Grafana. | No |

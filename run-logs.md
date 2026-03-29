Query: Run service chaos in the production namespace and send telemetry to ES

Searching for: Run service chaos in the production namespace and send telemetry to ES
Loading Cross-Encoder: BAAI/bge-reranker-v2-m3
Loading Qwen Embedding Model: Qwen/Qwen3-Embedding-0.6B
Retriever loaded successfully


```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Service Disruption Scenarios             | Cross-Encoder: -1.9590 | FAISS:  0.5632
  [2] Syn Flood                                | Cross-Encoder: -2.6388 | FAISS:  0.4827
  [3] Application Outages                      | Cross-Encoder: -3.1779 | FAISS:  0.5182
  [4] Container Scenarios                      | Cross-Encoder: -3.3520 | FAISS:  0.4944
  [5] Time Scenarios                           | Cross-Encoder: -3.5725 | FAISS:  0.4731
===============================================================================================
```

Query: Filter node traffic and monitor with Prometheus metrics and critical alert checks

Searching for: Filter node traffic and monitor with Prometheus metrics and critical alert checks

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Network Filter                      | Cross-Encoder: -2.1580 | FAISS:  0.5988
  [2] Pod Network Filter                       | Cross-Encoder: -3.8584 | FAISS:  0.5384
  [3] Network Chaos                            | Cross-Encoder: -4.1199 | FAISS:  0.4939
  [4] Node Memory Hog                          | Cross-Encoder: -5.4642 | FAISS:  0.4427
  [5] Node Cpu Hog                             | Cross-Encoder: -5.4780 | FAISS:  0.4505
===============================================================================================
```


Query: Block ingress and egress traffic for pods labeled app=frontend

Searching for: Block ingress and egress traffic for pods labeled app=frontend

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pod Network Chaos                        | Cross-Encoder:  0.6883 | FAISS:  0.6316
  [2] Pod Network Filter                       | Cross-Encoder: -0.7051 | FAISS:  0.5736
  [3] Zone Outages                             | Cross-Encoder: -0.8007 | FAISS:  0.4968
  [4] Pod Scenarios                            | Cross-Encoder: -0.8962 | FAISS:  0.5131
  [5] Application Outages                      | Cross-Encoder: -2.1193 | FAISS:  0.5441
===============================================================================================
```

Query: Testing node termination in a multi-cloud setup using Azure credentials.

Searching for: Testing node termination in a multi-cloud setup using Azure credentials.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Scenarios                           | Cross-Encoder: -3.0443 | FAISS:  0.5188
  [2] Node Io Hog                              | Cross-Encoder: -5.7985 | FAISS:  0.4119
  [3] Zone Outages                             | Cross-Encoder: -5.9164 | FAISS:  0.5360
  [4] Power Outages                            | Cross-Encoder: -6.0752 | FAISS:  0.4982
  [5] Node Network Filter                      | Cross-Encoder: -6.0788 | FAISS:  0.4365
===============================================================================================
```

Query: how do I delete a kubevirt VM named test-vm in the dev namespace?

Searching for: how do I delete a kubevirt VM named test-vm in the dev namespace?

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Kubevirt Outage                          | Cross-Encoder:  1.4661 | FAISS:  0.7148
  [2] Service Disruption Scenarios             | Cross-Encoder: -2.2618 | FAISS:  0.5827
  [3] Pod Scenarios                            | Cross-Encoder: -3.8972 | FAISS:  0.5110
  [4] Node Scenarios                           | Cross-Encoder: -5.3056 | FAISS:  0.4624
  [5] Pvc Scenarios                            | Cross-Encoder: -5.6613 | FAISS:  0.4480
===============================================================================================
```

Query: If the underlying daemon executing the database hangs, will the orchestrator detect it and restart it?

Searching for: If the underlying daemon executing the database hangs, will the orchestrator detect it and restart it?

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Scenarios                           | Cross-Encoder: -4.7676 | FAISS:  0.4564
  [2] Pod Network Chaos                        | Cross-Encoder: -6.0927 | FAISS:  0.4385
  [3] Container Scenarios                      | Cross-Encoder: -6.5094 | FAISS:  0.4507
  [4] Node Io Hog                              | Cross-Encoder: -6.6320 | FAISS:  0.4457
  [5] Application Outages                      | Cross-Encoder: -7.1986 | FAISS:  0.4605
===============================================================================================
```

Query: Ensure the physical host machines reject all incoming administrative connections.

Searching for: Ensure the physical host machines reject all incoming administrative connections.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pod Network Chaos                        | Cross-Encoder: -3.3980 | FAISS:  0.4361
  [2] Pod Network Filter                       | Cross-Encoder: -3.7405 | FAISS:  0.3901
  [3] Node Network Filter                      | Cross-Encoder: -3.9016 | FAISS:  0.4759
  [4] Network Chaos                            | Cross-Encoder: -5.6877 | FAISS:  0.4108
  [5] Application Outages                      | Cross-Encoder: -6.2459 | FAISS:  0.3383
===============================================================================================
```

Query: Test if our microservices properly validate JWTs when a compromised internal service returns spoofed authentication tokens.

Searching for: Test if our microservices properly validate JWTs when a compromised internal service returns spoofed authentication tokens.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Service Hijacking                        | Cross-Encoder: -1.7211 | FAISS:  0.5228
  [2] Service Disruption Scenarios             | Cross-Encoder: -5.3048 | FAISS:  0.3630
  [3] Pod Network Chaos                        | Cross-Encoder: -5.5461 | FAISS:  0.3692
  [4] Time Scenarios                           | Cross-Encoder: -5.6085 | FAISS:  0.3812
  [5] Application Outages                      | Cross-Encoder: -6.7921 | FAISS:  0.3621
===============================================================================================
```

Query: Check if the scheduled nightly backups trigger at the wrong hour due to a daylight savings bug.

Searching for: Check if the scheduled nightly backups trigger at the wrong hour due to a daylight savings bug.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Time Scenarios                           | Cross-Encoder: -5.9922 | FAISS:  0.4423
  [2] Application Outages                      | Cross-Encoder: -7.2304 | FAISS:  0.3246
  [3] Power Outages                            | Cross-Encoder: -7.4389 | FAISS:  0.3252
  [4] Node Scenarios                           | Cross-Encoder: -7.5448 | FAISS:  0.3083
  [5] Zone Outages                             | Cross-Encoder: -7.7123 | FAISS:  0.3523
===============================================================================================
```

Query: Replicate the storage latency caused by a noisy neighbor running massive database dumps on the same physical SAN.

Searching for: Replicate the storage latency caused by a noisy neighbor running massive database dumps on the same physical SAN.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Io Hog                              | Cross-Encoder: -1.6595 | FAISS:  0.4627
  [2] Pvc Scenarios                            | Cross-Encoder: -5.8289 | FAISS:  0.3808
  [3] Node Memory Hog                          | Cross-Encoder: -5.9607 | FAISS:  0.3536
  [4] Network Chaos                            | Cross-Encoder: -6.0546 | FAISS:  0.4391
  [5] Pod Network Chaos                        | Cross-Encoder: -6.4338 | FAISS:  0.3512
===============================================================================================
```

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Service Disruption Scenarios             | Cross-Encoder: -1.9590 | FAISS:  0.5632
  [2] Syn Flood                                | Cross-Encoder: -2.6388 | FAISS:  0.4827
  [3] Application Outages                      | Cross-Encoder: -3.1779 | FAISS:  0.5182
  [4] Container Scenarios                      | Cross-Encoder: -3.3520 | FAISS:  0.4944
  [5] Time Scenarios                           | Cross-Encoder: -3.5725 | FAISS:  0.4731
===============================================================================================
```

Query: Filter node traffic and monitor with Prometheus metrics and critical alert checks

Searching for: Filter node traffic and monitor with Prometheus metrics and critical alert checks

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Network Filter                      | Cross-Encoder: -2.1580 | FAISS:  0.5988
  [2] Pod Network Filter                       | Cross-Encoder: -3.8584 | FAISS:  0.5384
  [3] Network Chaos                            | Cross-Encoder: -4.1199 | FAISS:  0.4939
  [4] Node Memory Hog                          | Cross-Encoder: -5.4642 | FAISS:  0.4427
  [5] Node Cpu Hog                             | Cross-Encoder: -5.4780 | FAISS:  0.4505
===============================================================================================
```

Query: Block ingress and egress traffic for pods labeled app=frontend

Searching for: Block ingress and egress traffic for pods labeled app=frontend

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pod Network Chaos                        | Cross-Encoder:  0.6883 | FAISS:  0.6316
  [2] Pod Network Filter                       | Cross-Encoder: -0.7051 | FAISS:  0.5736
  [3] Zone Outages                             | Cross-Encoder: -0.8007 | FAISS:  0.4968
  [4] Pod Scenarios                            | Cross-Encoder: -0.8962 | FAISS:  0.5131
  [5] Application Outages                      | Cross-Encoder: -2.1193 | FAISS:  0.5441
===============================================================================================
```

Query: Testing node termination in a multi-cloud setup using Azure credentials.

Searching for: Testing node termination in a multi-cloud setup using Azure credentials.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Scenarios                           | Cross-Encoder: -3.0443 | FAISS:  0.5188
  [2] Node Io Hog                              | Cross-Encoder: -5.7985 | FAISS:  0.4119
  [3] Zone Outages                             | Cross-Encoder: -5.9164 | FAISS:  0.5360
  [4] Power Outages                            | Cross-Encoder: -6.0752 | FAISS:  0.4982
  [5] Node Network Filter                      | Cross-Encoder: -6.0788 | FAISS:  0.4365
===============================================================================================
```

Query: how do I delete a kubevirt VM named test-vm in the dev namespace?

Searching for: how do I delete a kubevirt VM named test-vm in the dev namespace?


```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Kubevirt Outage                          | Cross-Encoder:  1.4661 | FAISS:  0.7148
  [2] Service Disruption Scenarios             | Cross-Encoder: -2.2618 | FAISS:  0.5827
  [3] Pod Scenarios                            | Cross-Encoder: -3.8972 | FAISS:  0.5110
  [4] Node Scenarios                           | Cross-Encoder: -5.3056 | FAISS:  0.4624
  [5] Pvc Scenarios                            | Cross-Encoder: -5.6613 | FAISS:  0.4480
===============================================================================================
```

Query: If the underlying daemon executing the database hangs, will the orchestrator detect it and restart it?

Searching for: If the underlying daemon executing the database hangs, will the orchestrator detect it and restart it?

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Scenarios                           | Cross-Encoder: -4.7676 | FAISS:  0.4564
  [2] Pod Network Chaos                        | Cross-Encoder: -6.0927 | FAISS:  0.4385
  [3] Container Scenarios                      | Cross-Encoder: -6.5094 | FAISS:  0.4507
  [4] Node Io Hog                              | Cross-Encoder: -6.6320 | FAISS:  0.4457
  [5] Application Outages                      | Cross-Encoder: -7.1986 | FAISS:  0.4605
===============================================================================================
```

Query: Ensure the physical host machines reject all incoming administrative connections.

Searching for: Ensure the physical host machines reject all incoming administrative connections.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pod Network Chaos                        | Cross-Encoder: -3.3980 | FAISS:  0.4361
  [2] Pod Network Filter                       | Cross-Encoder: -3.7405 | FAISS:  0.3901
  [3] Node Network Filter                      | Cross-Encoder: -3.9016 | FAISS:  0.4759
  [4] Network Chaos                            | Cross-Encoder: -5.6877 | FAISS:  0.4108
  [5] Application Outages                      | Cross-Encoder: -6.2459 | FAISS:  0.3383
===============================================================================================
```

Query: Test if our microservices properly validate JWTs when a compromised internal service returns spoofed authentication tokens.

Searching for: Test if our microservices properly validate JWTs when a compromised internal service returns spoofed authentication tokens.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Service Hijacking                        | Cross-Encoder: -1.7211 | FAISS:  0.5228
  [2] Service Disruption Scenarios             | Cross-Encoder: -5.3048 | FAISS:  0.3630
  [3] Pod Network Chaos                        | Cross-Encoder: -5.5461 | FAISS:  0.3692
  [4] Time Scenarios                           | Cross-Encoder: -5.6085 | FAISS:  0.3812
  [5] Application Outages                      | Cross-Encoder: -6.7921 | FAISS:  0.3621
===============================================================================================
```

Query: Check if the scheduled nightly backups trigger at the wrong hour due to a daylight savings bug.

Searching for: Check if the scheduled nightly backups trigger at the wrong hour due to a daylight savings bug.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Time Scenarios                           | Cross-Encoder: -5.9922 | FAISS:  0.4423
  [2] Application Outages                      | Cross-Encoder: -7.2304 | FAISS:  0.3246
  [3] Power Outages                            | Cross-Encoder: -7.4389 | FAISS:  0.3252
  [4] Node Scenarios                           | Cross-Encoder: -7.5448 | FAISS:  0.3083
  [5] Zone Outages                             | Cross-Encoder: -7.7123 | FAISS:  0.3523
===============================================================================================
```

Query: Replicate the storage latency caused by a noisy neighbor running massive database dumps on the same physical SAN.

Searching for: Replicate the storage latency caused by a noisy neighbor running massive database dumps on the same physical SAN.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Io Hog                              | Cross-Encoder: -1.6595 | FAISS:  0.4627
  [2] Pvc Scenarios                            | Cross-Encoder: -5.8289 | FAISS:  0.3808
  [3] Node Memory Hog                          | Cross-Encoder: -5.9607 | FAISS:  0.3536
  [4] Network Chaos                            | Cross-Encoder: -6.0546 | FAISS:  0.4391
  [5] Pod Network Chaos                        | Cross-Encoder: -6.4338 | FAISS:  0.3512
===============================================================================================
```

Query: A rogue Java process with a massive heap leak starts thrashing the host.

Searching for: A rogue Java process with a massive heap leak starts thrashing the host.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Memory Hog                          | Cross-Encoder: -3.4333 | FAISS:  0.4813
  [2] Container Scenarios                      | Cross-Encoder: -3.9504 | FAISS:  0.4246
  [3] Node Io Hog                              | Cross-Encoder: -4.0826 | FAISS:  0.4286
  [4] Node Cpu Hog                             | Cross-Encoder: -4.5709 | FAISS:  0.4862
  [5] Network Chaos                            | Cross-Encoder: -4.9979 | FAISS:  0.3855
===============================================================================================
```

Query: Find out if our financial transaction logs get out of order if the master server's clock drifts backward.

Searching for: Find out if our financial transaction logs get out of order if the master server's clock drifts backward.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Time Scenarios                           | Cross-Encoder: -1.1789 | FAISS:  0.4816
  [2] Node Scenarios Bm                        | Cross-Encoder: -8.5704 | FAISS:  0.3253
  [3] Node Scenarios                           | Cross-Encoder: -9.0680 | FAISS:  0.3099
  [4] Syn Flood                                | Cross-Encoder: -9.3638 | FAISS:  0.3229
  [5] Power Outages                            | Cross-Encoder: -9.5909 | FAISS:  0.3150
===============================================================================================
```
Query: I want to test the log rotation alerting. What happens if a log file grows infinitely and consumes all available space?

Searching for: I want to test the log rotation alerting. What happens if a log file grows infinitely and consumes all available space?

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pvc Scenarios                            | Cross-Encoder: -2.0219 | FAISS:  0.3922
  [2] Node Memory Hog                          | Cross-Encoder: -3.1011 | FAISS:  0.3785
  [3] Node Io Hog                              | Cross-Encoder: -7.0016 | FAISS:  0.3808
  [4] Node Cpu Hog                             | Cross-Encoder: -7.4434 | FAISS:  0.3325
  [5] Node Scenarios                           | Cross-Encoder: -8.4675 | FAISS:  0.3169
===============================================================================================
```
Query: Evict the currently running instances of the frontend deployment.

Searching for: Evict the currently running instances of the frontend deployment.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Pod Scenarios                            | Cross-Encoder:  0.5005 | FAISS:  0.4848
  [2] Pod Network Chaos                        | Cross-Encoder: -3.3519 | FAISS:  0.4188
  [3] Application Outages                      | Cross-Encoder: -3.9045 | FAISS:  0.4382
  [4] Node Scenarios                           | Cross-Encoder: -4.9544 | FAISS:  0.3945
  [5] Kubevirt Outage                          | Cross-Encoder: -5.2204 | FAISS:  0.4451
===============================================================================================
```
Query: Spike the read and write operations on the underlying host to create a bottleneck.

Searching for: Spike the read and write operations on the underlying host to create a bottleneck.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Node Io Hog                              | Cross-Encoder: -2.1809 | FAISS:  0.4346
  [2] Network Chaos                            | Cross-Encoder: -4.4419 | FAISS:  0.3513
  [3] Node Cpu Hog                             | Cross-Encoder: -5.4870 | FAISS:  0.3718
  [4] Node Memory Hog                          | Cross-Encoder: -7.5400 | FAISS:  0.3327
  [5] Node Network Filter                      | Cross-Encoder: -7.6852 | FAISS:  0.3070
===============================================================================================
```
Query: Corrupt the network link by introducing massive packet drops on the interface.

Searching for: Corrupt the network link by introducing massive packet drops on the interface.

```
===============================================================================================
RERANKED RESULTS (Top-K)
===============================================================================================
  [1] Network Chaos                            | Cross-Encoder:  0.8751 | FAISS:  0.5079
  [2] Pod Network Filter                       | Cross-Encoder: -2.1470 | FAISS:  0.4128
  [3] Node Network Filter                      | Cross-Encoder: -3.9432 | FAISS:  0.4589
  [4] Zone Outages                             | Cross-Encoder: -4.0879 | FAISS:  0.3739
  [5] Node Scenarios Bm                        | Cross-Encoder: -6.4544 | FAISS:  0.3393
===============================================================================================
```
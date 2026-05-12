[KRKN-AI] Ready to profile your cluster. What should we test?

(type 'exit' to quit)
>> Simulate a node network interface failure on a worker node for 5 minutes.
      Step time: 299ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-interface-down             ████████░░    0.789   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=116  rerank=91  total=209  reranked=6
>> Bring down the eth0 interface on one Kubernetes node and restore it automatically.
      Step time: 314ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-interface-down             ████████░░    0.814   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=117  rerank=108  total=227  reranked=7
>> Test node-level network partition by disabling NICs temporarily.
      Step time: 318ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-interface-down             ███████░░░    0.669   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=121  rerank=106  total=229  reranked=7
>> Run a chaos scenario that disconnects a node from the cluster network.
      Step time: 311ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-scenarios                  ████████░░    0.808   │
  │[2]   network-chaos                   ████████░░    0.789   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=115  rerank=105  total=222  reranked=7
>> Simulate loss of connectivity on a target node by shutting down its network interface.
      Step time: 301ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-interface-down             █████████░    0.935   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=119  rerank=93  total=214  reranked=6
>> Simulate an AWS EFS outage on selected Kubernetes nodes.
      Step time: 334ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   efs-disruption                  ████████░░    0.784   │
  │[2]   zone-outages                    ███████░░░    0.676   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=136  rerank=103  total=241  reranked=7
>> Simulate a temporary storage connectivity issue on a subset of nodes.
      Step time: 305ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-interface-down             █████░░░░░    0.521   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=110  rerank=105  total=217  reranked=7
>> Run a chaos experiment where applications lose access to mounted file systems
      Step time: 312ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   pod-scenarios                   █████░░░░░    0.454   │
  │[2]   efs-disruption                  ████░░░░░░    0.406   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=116  rerank=104  total=222  reranked=7
>> Test how workloads behave when shared storage suddenly becomes unreachable.
      Step time: 308ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-io-hog                     █████░░░░░    0.519   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=113  rerank=104  total=219  reranked=7
>> Simulate storage bottlenecks on worker nodes for a short duration.
      Step time: 300ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-io-hog                     ███████░░░    0.685   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=117  rerank=91  total=210  reranked=6
>> Stress node storage to validate monitoring and alerting behavior.
      Step time: 303ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-io-hog                     █████░░░░░    0.493   │
  │[2]   node-memory-hog                 █████░░░░░    0.463   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=122  rerank=92  total=216  reranked=6
>> Run a chaos experiment that creates sustained disk write pressure.
      Step time: 298ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   node-io-hog                     ████░░░░░░    0.400   │
  │[2]   node-scenarios                  ██░░░░░░░░    0.161   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=108  rerank=102  total=212  reranked=7
>> Simulate a temporary failure between pods and backend SQL databases.
      Step time: 318ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   pod-scenarios                   ███████░░░    0.750   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=123  rerank=103  total=227  reranked=7
>> Validate retry and failover behavior during database network interruptions
      Step time: 309ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   network-chaos                   ███░░░░░░░    0.333   │
  │[2]   pod-scenarios                   ███░░░░░░░    0.285   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=116  rerank=104  total=222  reranked=7
>> This scenario blocks outbound MySQL and PostgreSQL traffic from targeted pods
      Step time: 291ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   aurora-disruption               ██████████    0.955   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=114  rerank=90  total=206  reranked=6
>> disrupt standard MySQL and PostgreSQL database connections
      Step time: 300ms

  Searching 226 scenarios...  done in 0.3s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   aurora-disruption               █████████░    0.911   │
  └────────────────────────────────────────────────────────────┘

  Model ms: retrieve=108  rerank=103  total=213  reranked=7
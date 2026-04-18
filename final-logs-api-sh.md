~ ❯ plz skew time on pods with label app=frontend                                                                     ravielluri@Ravis-Mac-mini
~ ❯ clear                                                                                                       ✘ INT ravielluri@Ravis-Mac-mini
~ ❯ curl -sS -X POST http://127.0.0.1:18080/retrieve \                                                                ravielluri@Ravis-Mac-mini
  -H 'content-type: application/json' \
  -d '{"query":"plz skew time on pods with label app=frontend","k":10,"rerank_k":5}' | python3 -m json.tool
{
    "query": "plz skew time on pods with label app=frontend",
    "results": [
        {
            "id": "time-scenarios",
            "name": "Time Scenarios",
            "retrieval_score": 0.7135,
            "rerank_score": -0.5111,
            "final_score": 0.4426,
            "score_percent": 44.3
        },
        {
            "id": "pod-scenarios",
            "name": "Pod Scenarios",
            "retrieval_score": 0.5863,
            "rerank_score": -3.8297,
            "final_score": 0.1343,
            "score_percent": 13.4
        },
        {
            "id": "pod-network-chaos",
            "name": "Pod Network Chaos",
            "retrieval_score": 0.5813,
            "rerank_score": -3.9341,
            "final_score": 0.1316,
            "score_percent": 13.2
        },
        {
            "id": "application-outages",
            "name": "Application Outages",
            "retrieval_score": 0.5478,
            "rerank_score": -3.9491,
            "final_score": 0.1247,
            "score_percent": 12.5
        },
        {
            "id": "container-scenarios",
            "name": "Container Scenarios",
            "retrieval_score": 0.5315,
            "rerank_score": -6.3326,
            "final_score": 0.1077,
            "score_percent": 10.8
        }
    ],
    "top_match": "time-scenarios",
    "message": "Found 5 relevant scenarios"
}
~ ❯ curl -sS -X POST http://127.0.0.1:18080/retrieve \                                                             3s ravielluri@Ravis-Mac-mini
  -H 'content-type: application/json' \
  -d '{"query":"Could you show me the krknctl command to delete pods with label app=api in namespace kube-system?","k":10,"rerank_k":5}' | python3 -m json.tool
{
    "query": "Could you show me the krknctl command to delete pods with label app=api in namespace kube-system?",
    "results": [
        {
            "id": "pod-scenarios",
            "name": "Pod Scenarios",
            "retrieval_score": 0.7098,
            "rerank_score": -0.6717,
            "final_score": 0.4125,
            "score_percent": 41.2
        },
        {
            "id": "service-disruption-scenarios",
            "name": "Service Disruption Scenarios",
            "retrieval_score": 0.6659,
            "rerank_score": -1.7724,
            "final_score": 0.2494,
            "score_percent": 24.9
        },
        {
            "id": "time-scenarios",
            "name": "Time Scenarios",
            "retrieval_score": 0.5635,
            "rerank_score": -2.2603,
            "final_score": 0.1883,
            "score_percent": 18.8
        },
        {
            "id": "container-scenarios",
            "name": "Container Scenarios",
            "retrieval_score": 0.6093,
            "rerank_score": -2.5441,
            "final_score": 0.1801,
            "score_percent": 18.0
        },
        {
            "id": "pod-network-chaos",
            "name": "Pod Network Chaos",
            "retrieval_score": 0.6172,
            "rerank_score": -3.0765,
            "final_score": 0.1587,
            "score_percent": 15.9
        }
    ],
    "top_match": "pod-scenarios",
    "message": "Found 5 relevant scenarios"
}
~ ❯ curl -sS -X POST http://127.0.0.1:18080/retrieve \                                                             3s ravielluri@Ravis-Mac-mini
  -H 'content-type: application/json' \
  -d '{"query":"Execute the traffic outage scenario in namespace infra for 30 minutes with wait after each run.","k":10,"rerank_k":5}' | python3 -m json.tool
{
    "query": "Execute the traffic outage scenario in namespace infra for 30 minutes with wait after each run.",
    "results": [
        {
            "id": "application-outages",
            "name": "Application Outages",
            "retrieval_score": 0.6921,
            "rerank_score": -4.5908,
            "final_score": 0.1464,
            "score_percent": 14.6
        },
        {
            "id": "zone-outages",
            "name": "Zone Outages",
            "retrieval_score": 0.6592,
            "rerank_score": -4.6087,
            "final_score": 0.1397,
            "score_percent": 14.0
        },
        {
            "id": "power-outages",
            "name": "Power Outages",
            "retrieval_score": 0.6535,
            "rerank_score": -6.2726,
            "final_score": 0.1322,
            "score_percent": 13.2
        },
        {
            "id": "network-chaos",
            "name": "Network Chaos",
            "retrieval_score": 0.6557,
            "rerank_score": -7.0489,
            "final_score": 0.1318,
            "score_percent": 13.2
        },
        {
            "id": "service-disruption-scenarios",
            "name": "Service Disruption Scenarios",
            "retrieval_score": 0.6216,
            "rerank_score": -5.238,
            "final_score": 0.1285,
            "score_percent": 12.9
        }
    ],
    "top_match": "application-outages",
    "message": "Found 5 relevant scenarios"
}
~ ❯ ./scripts/pipeline_retrieve_only.sh                                                                            3s ravielluri@Ravis-Mac-mini
zsh: no such file or directory: ./scripts/pipeline_retrieve_only.sh
~ ❯ cd ir-chaos                                                                                                       ravielluri@Ravis-Mac-mini
~/ir-chaos retrieval-only !1 ❯ ./scripts/pipeline_retrieve_only.sh                                                    ravielluri@Ravis-Mac-mini

[KRKN-AI] Ready to profile your cluster. What should we test?

(type 'exit' to quit)
>> plz skew time on pods with label app=frontend

  Searching 20 scenarios...  done in 0.1s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   time-scenarios                  ████░░░░░░    0.443   │
  └────────────────────────────────────────────────────────────┘
>> ^C
~/ir-chaos retrieval-only !1 ❯ ./scripts/pipeline_retrieve_only.sh                                          ✘ INT 26s ravielluri@Ravis-Mac-mini

[KRKN-AI] Ready to profile your cluster. What should we test?

(type 'exit' to quit)
>> Could you show me the krknctl command to delete pods with label app=api in namespace kube-system?

  Searching 20 scenarios...  done in 0.1s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   pod-scenarios                   ████░░░░░░    0.412   │
  │[2]   service-disruption-scenarios    ██░░░░░░░░    0.249   │
  └────────────────────────────────────────────────────────────┘
>> Execute the traffic outage scenario in namespace infra for 30 minutes with wait after each run.

  Searching 20 scenarios...  done in 0.1s

  ┌─ Suggested Chaos Experiments ────────────────────────────────┐
  │OPT   ACTION                          FITMENT       MATCH   │
  │[1]   application-outages             █░░░░░░░░░    0.146   │
  │[2]   zone-outages                    █░░░░░░░░░    0.140   │
  └────────────────────────────────────────────────────────────┘
>>
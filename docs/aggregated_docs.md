### Pod Network Chaos Scenarios
This scenario runs network chaos at the pod level on a Kubernetes/OpenShift cluster.

#### Run

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-chaos
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-chaos
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-chaos

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
NAMESPACE               | Required - Namespace of the pod to which filter need to be applied    | ""                                     |
LABEL_SELECTOR          | Label of the pod(s) to target                                         | ""                                   | 
POD_NAME                | When label_selector is not specified, pod matching the name will be selected for the chaos scenario | "" |
INSTANCE_COUNT          | Number of pods to perform action/select that match the label selector | 1 |
TRAFFIC_TYPE            | List of directions to apply filters - egress/ingress ( needs to be a list ) | [ingress, egress] |
INGRESS_PORTS           | Ingress ports to block ( needs to be a list ) | [] i.e all ports |
EGRESS_PORTS            | Egress ports to block ( needs to be a list ) | [] i.e all ports |
WAIT_DURATION           | Ensure that it is at least about twice of test_duration | 300 |
TEST_DURATION           | Duration of the test run | 120 |

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-chaos
```


### Node Scenarios
This scenario disrupts the node(s) matching the label on a Kubernetes/OpenShift cluster. Actions/disruptions supported are listed [here](https://github.com/krkn-chaos/krkn/blob/master/docs/node_scenarios.md)

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
ACTION                  | Action can be one of the [following](https://github.com/krkn-chaos/krkn/blob/master/docs/node_scenarios.md) | node_stop_start_scenario for aws and vmware-node-reboot for vmware, ibmcloud-node-reboot for ibmcloud |
LABEL_SELECTOR          | Node label to target                                                  | node-role.kubernetes.io/worker       |
NODE_NAME               | Node name to inject faults in case of targeting a specific node; Can set multiple node names separated by a comma      | ""                                   |
INSTANCE_COUNT          | Targeted instance count matching the label selector                   | 1                                    |
RUNS                    | Iterations to perform action on a single node                         | 1                                    |
PARALLEL                | Run action on label or node name in parallel or sequential, set to true for parallel | false                 |
CLOUD_TYPE              | Cloud platform on top of which cluster is running, supported platforms - aws, vmware, ibmcloud, bm           | aws |
TIMEOUT                 | Duration to wait for completion of node scenario injection             | 180                                |
DURATION                | Duration to stop the node before running the start action - not supported for vmware and ibm cloud type             | 120                                |
VERIFY_SESSION          | Only needed for vmware - Set to True if you want to verify the vSphere client session using certificates    | False                               |
SKIP_OPENSHIFT_CHECKS   | Only needed for vmware - Set to True if you don't want to wait for the status of the nodes to change on OpenShift before passing the scenario  | False |
BMC_USER                 | Only needed for Baremetal ( bm ) - IPMI/bmc username | "" | 
BMC_PASSWORD             | Only needed for Baremetal ( bm ) - IPMI/bmc password | "" |
BMC_ADDR                 | Only needed for Baremetal ( bm ) - IPMI/bmc username | "" |

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/ANZY7HhPdWTNaWt4xMFanF6Q5)


The following environment variables need to be set for the scenarios that requires intereacting with the cloud platform API to perform the actions:

Amazon Web Services
```
$ export AWS_ACCESS_KEY_ID=<>
$ export AWS_SECRET_ACCESS_KEY=<>
$ export AWS_DEFAULT_REGION=<>
```

VMware Vsphere
```
$ export VSPHERE_IP=<vSphere_client_IP_address>

$ export VSPHERE_USERNAME=<vSphere_client_username>

$ export VSPHERE_PASSWORD=<vSphere_client_password>

```


Ibmcloud 
```
$ export IBMC_URL=https://<region>.iaas.cloud.ibm.com/v1

$ export IBMC_APIKEY=<ibmcloud_api_key>

```

Baremetal <br/>
See [bare metal documentation](node-scenarios-bm.md)

Google Cloud Platform
```
TBD
```

Azure
```
export AZURE_TENANT_ID=<>
export AZURE_CLIENT_SECRET=<>
export AZURE_CLIENT_ID=<>

```

OpenStack

```
TBD
```

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios


### Node CPU hog scenario
This scenario hogs the cpu on the specified node on a Kubernetes/OpenShift cluster for a specified duration. For more information refer the following [documentation](https://github.com/krkn-chaos/krkn/blob/main/docs/hog_scenarios.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-cpu-hog
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-cpu-hog
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-cpu-hog

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

| Parameter            | Description                                             | Default
|----------------------|---------------------------------------------------------| ------------------------------------                   |
| TOTAL_CHAOS_DURATION | Set chaos duration (in sec) as desired                  | 60                                  |
| NODE_CPU_CORE        | Number of cores (workers) of node CPU to be consumed    | 2                                    |
| NODE_CPU_PERCENTAGE  | Percentage of total cpu to be consumed                  | 50                                   |
| NAMESPACE            | Namespace where the scenario container will be deployed | default |
| NODE_SELECTOR        | defines the node selector for choosing target nodes. If not specified, one schedulable node in the cluster will be chosen at random. If multiple nodes match the selector, all of them will be subjected to stress. If number-of-nodes is specified, that many nodes will be randomly selected from those identified by the selector.                                     | "" |                             |
| NUMBER_OF_NODES      | restricts the number of selected nodes by the selector                                     | "" |                             |
| IMAGE                | the container image of the stress workload|quay.io/krkn-chaos/krkn-hog||

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-cpu-hog
```

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/452762)


### Syn Flood scenario
This scenario simulates a user-defined surge of TCP SYN requests directed at one or more services deployed within the cluster or an external target reachable by the cluster.
For more details, please refer to the following [documentation](https://github.com/krkn-chaos/krkn/blob/main/docs/syn_flood_scenarios.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z 
-e TARGET_PORT=<target_port> \
-e NAMESPACE=<target_namespace> \
-e TOTAL_CHAOS_DURATION=<duration> \
-e TARGET_SERVICE=<target_service> \
-e NUMBER_OF_PODS=10 \
-e NODE_SELECTORS=<key>=<value>;<key>=<othervalue> \
-d 
quay.io/krkn-chaos/krkn-hub:syn-flood

$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z
-e TARGET_PORT=<target_port> \
-e NAMESPACE=<target_namespace> \
-e TOTAL_CHAOS_DURATION=<duration> \
-e TARGET_SERVICE=<target_service> \
-e NUMBER_OF_PODS=10 \
-e NODE_SELECTORS=<key>=<value>;<key>=<othervalue> \ 
-d 
quay.io/krkn-chaos/krkn-hub:syn-flood

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables


|Parameter | Description                                                                                                                                                                                                                                                                                                 | Default |
|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
|PACKET_SIZE| The size in bytes of the SYN packet                                                                                                                                                                                                                                                                         |120|
|WINDOW_SIZE| The TCP window size between packets in bytes                                                                                                                                                                                                                                                                |64|
|TOTAL_CHAOS_DURATION| The number of seconds the chaos will last                                                                                                                                                                                                                                                                   |120|
|NAMESPACE| The namespace containing the target service and where the attacker pods will be deployed                                                                                                                                                                                                                    |default|
|TARGET_SERVICE| The service name (or the hostname/IP address in case an external target will be hit) that will be affected by the attack. Must be empty if TARGET_SERVICE_LABEL will be set                                                                                                                                 ||
|TARGET_PORT| The TCP port that will be targeted by the attack                                                                                                                                                                                                                                                            ||
|TARGET_SERVICE_LABEL| The label that will be used to select one or more services. Must be left empty if TARGET_SERVICE variable is set                                                                                                                                                                                            ||
|NUMBER_OF_PODS| The number of attacker pods that will be deployed                                                                                                                                                                                                                                                           |2|
|IMAGE| The container image that will be used to perform the scenario                                                                                                                                                                                                                                               |quay.io/krkn-chaos/krkn-syn-flood:latest|
|NODE_SELECTORS| The node selectors are used to guide the cluster on where to deploy attacker pods. You can specify one or more labels in the format key=value;key=value2 (even using the same key) to choose one or more node categories. If left empty, the pods will be scheduled on any available node, depending on the cluster's capacity. ||

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:syn-flood
```



### Application outages
This scenario disrupts the traffic to the specified application to be able to understand the impact of the outage on the dependent service/user experience. Refer [docs](https://github.com/krkn-chaos/krkn/blob/master/docs/application_outages.md) for more details.

#### Run

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/krkn-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:application-outages
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:application-outages
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:application-outages

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
DURATION                | Duration in seconds after which the routes will be accessible         | 600                                  |
NAMESPACE               | Namespace to target - all application routes will go inaccessible if pod selector is empty ( Required )|  No default |
POD_SELECTOR            | Pods to target. For example "{app: foo}"                                | No default                           |
BLOCK_TRAFFIC_TYPE      | It can be Ingress or Egress or Ingress, Egress ( needs to be a list ) | [Ingress, Egress]                    |


**NOTE** Defining the `NAMESPACE` parameter is required for running this scenario while the pod_selector is optional. In case of using pod selector to target a particular application, make sure to define it using the following format with a space between key and value: "{key: value}".

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:application-outages
```

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/452403?speed=3&theme=solarized-dark)


### Time Skew Scenarios
This scenario skews the date and time of the nodes and pods matching the label on a Kubernetes/OpenShift cluster. More information can be found [here](https://github.com/krkn-chaos/krkn/blob/master/docs/time_scenarios.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:time-scenarios
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:time-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:time-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```

#### Demo
[Here](https://asciinema.org/a/zMBAdzHE40oPXkFVIz0exEoOX) is a demo of kraken-hub in action

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
OBJECT_TYPE             | Object to target. Supported options: pod, node                        | pod                                  |
LABEL_SELECTOR          | Label of the container(s) or nodes to target                          | k8s-app=etcd                         |
ACTION                  | Action to run. Supported actions: skew_time, skew_date                | skew_date                            |
OBJECT_NAME             | List of the names of pods or nodes you want to skew ( optional parameter )                   | []                                   |
CONTAINER_NAME          | Container in the specified pod to target in case the pod has multiple containers running. Random container is picked if empty   | ""                                   |
NAMESPACE               | Namespace of the pods you want to skew, need to be set only if setting a specific pod name | ""                   |


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios


### Namespace/Service Disruption Scenarios
This scenario deletes main objects within a namespace in your Kubernetes/OpenShift cluster. More information can be found [here](https://github.com/krkn-chaos/krkn/blob/master/docs/service_disruption_scenarios.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:service-disruption-scenarios
# podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:service-disruption-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:service-disruption-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Demo
See [here](https://asciinema.org/a/kKPSI0D7upV9HQWH5jnroTaKb) for a demo of this scenario

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
LABEL_SELECTOR          | Label of the namespace to target. Set this parameter only if NAMESPACE is not set                                       |     ""                     |
NAMESPACE               | Name of the namespace you want to target. Set this parameter only if LABEL_SELECTOR is not set  | "openshift-etcd"                   |
SLEEP                   | Number of seconds to wait before polling to see if namespace exists again         | 15                                    |
DELETE_COUNT            | Number of namespaces to kill in each run, based on matching namespace and label specified | 1 |
RUNS                    | Number of runs to execute the action           | 1                                    |


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:service-disruption-scenarios


### Zone Outage Scenarios
This scenario disrupts a targeted zone in the public cloud by blocking egress and ingress traffic to understand the impact on both Kubernetes/OpenShift platforms control plane as well as applications running on the worker nodes in that zone. More information is documented [here](https://github.com/krkn-chaos/krkn/blob/master/docs/zone_outage.md)

#### Run

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.
 
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:zone-outages
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:zone-outages
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:zone-outages

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
CLOUD_TYPE              | Cloud platform on top of which cluster is running, [supported cloud platforms](https://github.com/krkn-chaos/krkn/blob/master/docs/node_scenarios.md)                     | aws |
DURATION                | Duration in seconds after which the zone will be back online          | 600                                  |
VPC_ID                  | cluster virtual private network to target ( REQUIRED )                             | ""                                   |
SUBNET_ID               | subnet-id to deny both ingress and egress traffic ( REQUIRED ). Format: [subenet1, subnet2]                    | ""       |
DEFAULT_ACL_ID          | (Optional) ID of an existing network ACL to use instead of creating a new one. If provided, this ACL will not be deleted after the scenario | "" |

The following environment variables need to be set for the scenarios that requires intereacting with the cloud platform API to perform the actions:

Amazon Web Services
```
$ export AWS_ACCESS_KEY_ID=<>
$ export AWS_SECRET_ACCESS_KEY=<>
$ export AWS_DEFAULT_REGION=<>
```

Google Cloud Platform
```
TBD
```

Azure
```
TBD
```

OpenStack

```
TBD
```

Baremetal
```
TBD
```

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
```

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/452672?speed=3&theme=solarized-dark)


### Container Scenarios
This scenario disrupts the containers matching the label in the specified namespace on a Kubernetes/OpenShift cluster.

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

ex.) 
`export <parameter_name>=<value>`

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
NAMESPACE               | Targeted namespace in the cluster                                     | openshift-etcd                       |
LABEL_SELECTOR          | Label of the container(s) to target                                   | k8s-app=etcd                         | 
DISRUPTION_COUNT        | Number of container to disrupt                                        | 1                                    |
CONTAINER_NAME          | Name of the container to disrupt                                      | etcd                                 |
ACTION                  | kill signal to run. For example 1 ( hang up ) or 9                    | 1                                    |
EXPECTED_RECOVERY_TIME  | Time to wait before checking if all containers that were affected recover properly | 60                      |

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
```


#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/BXqs9JSGDSEKcydTIJ5LpPZBM?speed=3&theme=solarized-dark)


### KubeVirt VM Outage Scenario
This scenario deletes a Virtual Machine Instance (VMI) matching the namespace and name on a Kubernetes/OpenShift cluster where KubeVirt or OpenShift Containerized Network Virtualization (CNV) is installed. It simulates a VM crash and tests recovery capabilities. For more information refer the following [documentation](https://krkn-chaos.dev/docs/scenarios/kubevirt-vm-outage-scenario/).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:kubevirt-outage
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:kubevirt-outage
OR
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:kubevirt-outage

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.)
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
NAMESPACE               | VMI namespace to target                                               | ""                                   |
VM_NAME                 | VMI name to delete, supports regex                                    | ""                                   |
TIMEOUT                 | Timeout in seconds to wait for VMI to start running again             | 120                                  |
KILL_COUNT              | Number of VMIs to kill serially                                       | 1                                    |

#### Expected Behavior

When executed, the scenario will:
1. Validate that KubeVirt is installed and the target VMI exists
2. Save the initial state of the VMI
3. Delete the VMI
4. Wait for the VMI to become running or hit the timeout
5. Attempt recovery — if the VMI is managed by a `VirtualMachine` resource with `runStrategy: Always`, it will recover automatically; otherwise the plugin manually recreates it using the saved state
6. Validate that the VMI is running again

**NOTE**: If the VM is managed by a `VirtualMachine` resource with `runStrategy: Always`, KubeVirt will automatically recreate the VMI after deletion and the scenario will wait for this automatic recovery to complete.

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:kubevirt-outage
```


### Node Scenarios
This scenario disrupts the node(s) matching the label on a bare metal Kubernetes/OpenShift cluster. Actions/disruptions supported are listed [here](https://github.com/krkn-chaos/krkn/blob/master/docs/node_scenarios.md)

#### Run
Unlike other krkn-hub scenarios, this one requires a specific configuration due to its unique structure. 
You must set up the scenario in a local file following the [scenario syntax](https://github.com/krkn-chaos/krkn/blob/main/scenarios/openshift/baremetal_node_scenarios.yaml), 
and then pass this file's base64-encoded content to the container via the SCENARIO_BASE64 variable.

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host \
    -env-host=true \
    -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
    -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios-bm
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host \
    -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
    -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios-bm
OR 
$ docker run \
     -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
     --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-scenarios-bm

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/ANZY7HhPdWTNaWt4xMFanF6Q5)

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios


### Network Chaos scenario
This scenario introduces network latency, packet loss, bandwidth restriction in the egress traffic of a Node's interface using the tc and Netem. For more information refer the following [documentation](https://github.com/krkn-chaos/krkn/blob/master/docs/network_chaos.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:network-chaos
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:network-chaos

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.)
`export <parameter_name>=<value>`

**NOTE:**
`export TRAFFIC_TYPE=egress` for Egress scenarios and `export TRAFFIC_TYPE=ingress` for Ingress scenarios


See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

##### Egress Scenarios

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
DURATION                | Duration in seconds - during with network chaos will be applied.         | 300                                  |
NODE_NAME               | Node name to inject faults in case of targeting a specific node; Can set multiple node names separated by a comma      | ""                                   |
LABEL_SELECTOR          | When NODE_NAME is not specified, a node with matching label_selector is selected for running.          | node-role.kubernetes.io/master       |
INSTANCE_COUNT          | Targeted instance count matching the label selector                   | 1                                   |
INTERFACES          | List of interface on which to apply the network restriction.                   | []                                    |
EXECUTION          | Execute each of the egress option as a single scenario(parallel) or as separate scenario(serial).                   | parallel                                    |
EGRESS          | Dictonary of values to set  network latency(latency: 50ms), packet loss(loss: 0.02), bandwidth restriction(bandwidth: 100mbit)                  | {bandwidth: 100mbit}                                    |


##### Ingress Scenarios

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
DURATION                | Duration in seconds - during with network chaos will be applied.         | 300                                  |
TARGET_NODE_AND_INTERFACE               |  # Dictionary with key as node name(s) and value as a list of its interfaces to test. For example: {ip-10-0-216-2.us-west-2.compute.internal: [ens5]}      | ""                                   |
LABEL_SELECTOR          | When NODE_NAME is not specified, a node with matching label_selector is selected for running.          | node-role.kubernetes.io/master       |
INSTANCE_COUNT          | Targeted instance count matching the label selector                   | 1                                   |
EXECUTION          |  Used to specify whether you want to apply filters on interfaces one at a time or all at once.                   | parallel|
NETWORK_PARAMS     | latency, loss and bandwidth are the three supported network parameters to alter for the chaos test. For example: {latency: 50ms, loss: '0.02'} | "" |
WAIT_DURATION           | Ensure that it is at least about twice of test_duration               | 300                                   |


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
```


### Service Hijacking scenario
This scenario reroutes traffic intended for a target service to a custom web service that is automatically deployed by Krkn. 
This web service responds with user-defined HTTP statuses, MIME types, and bodies. 
For more details, please refer to the following [documentation](https://github.com/krkn-chaos/krkn/blob/main/docs/service_hijacking_scenarios.md).

#### Run
Unlike other krkn-hub scenarios, this one requires a specific configuration due to its unique structure. 
You must set up the scenario in a local file following the [scenario syntax](https://github.com/krkn-chaos/krkn/blob/main/scenarios/kube/service_hijacking.yaml), 
and then pass this file's base64-encoded content to the container via the SCENARIO_BASE64 variable.

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). 
Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` 
environment variable for the chaos injection container to autoconnect.

```
$ podman run  --name=<container_name> \
              -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
              -v <path_to_kubeconfig>:/home/krkn/.kube/config:Z quay.io/krkn-chaos/krkn-hub:service-hijacking
              
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ export SCENARIO_BASE64="$(base64 -w0 <scenario_file>)"
$ docker run $(./get_docker_params.sh) --name=<container_name> \
                                       --net=host \
                                       -v <path-to-kube-config>:/home/krkn/.kube/config:Z \
                                       -d quay.io/krkn-chaos/krkn-hub:service-hijacking
OR 
$ docker run --name=<container_name> -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
                                     --net=host \
                                     -v <path-to-kube-config>:/home/krkn/.kube/config:Z \
                                     -d quay.io/krkn-chaos/krkn-hub:service-hijacking

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

| Parameter             | Description                                                                                                                                                                                                                               |
|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|  SCENARIO_BASE64 | Base64 encoded service-hijacking scenario file. Note that the __-w0__ option in the command substitution `SCENARIO_BASE64="$(base64 -w0 <scenario_file>)"` is __mandatory__ in order to remove line breaks from the base64 command output |


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run -e SCENARIO_BASE64="$(base64 -w0 <scenario_file>)" \
             --name=<container_name> \
             --net=host \
             --env-host=true \
             -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml \
             -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts \
             -v <path-to-kube-config>:/home/krkn/.kube/config:Z \
             -d quay.io/krkn-chaos/krkn-hub:service-hijacking
```



### Pod Network Filter Scenario
This scenario deploys a privileged workload on one or more nodes and will set iptables rules to block incoming and/or outgoing network traffic on given ports


#### Run

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-filter
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-filter
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-network-filter
$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```


#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`


See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

| Parameter            | Description                                                                                                                      | Default                           
|----------------------|----------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|
| TOTAL_CHAOS_DURATION | set chaos duration (in sec) as desired                                                                                           | 60                                |
| POD_SELECTOR         | defines the pod selector for choosing target pods. If multiple pods match the selector, all of them will be subjected to stress. | "node-role.kubernetes.io/worker=" |
| POD_NAME             | the pod name to target (if POD_SELECTOR not specified)                                                                           |
| INSTANCE_COUNT       | restricts the number of selected pods by the selector                                                                            | "1"                               |                             |
| EXECUTION            | sets the execution mode of the scenario on multiple pods, can be parallel or serial                                              | "parallel"                        |
| INGRESS              | sets the network filter on incoming traffic, can be true or false                                                                | false                             |
| EGRESS               | sets the network filter on outgoing traffic, can be true or false                                                                | true                              |                       
| INTERFACES           | a list of comma separated names of network interfaces (eg. eth0 or eth0,eth1,eth2) to filter for outgoing traffic                | ""                                |
| PORTS                | a list of comma separated port numbers (eg 8080 or 8080,8081,8082) to filter for both outgoing and incoming traffic              | ""                                |
| PROTOCOLS            | a list of comma separated network protocols  (tcp, udp or both of them e.g. tcp,udp)                                             | "tcp"                             |


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-network-traffic
```

### PVC Scenarios
This scenario fills up a given PersistenVolumeClaim by creating a temp file on the PVC from a pod associated with it. The purpose of this scenario is to fill up a volume to understand faults cause by the application using this volume. For more information refer the following [documentation](https://github.com/krkn-chaos/krkn/blob/master/docs/pvc_scenario.md).


#### Run

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pvc-scenarios
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pvc-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pvc-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

example: `export <parameter_name>=<value>`

If both `PVC_NAME` and `POD_NAME` are defined, `POD_NAME` value will be overridden from the `Mounted By:` value on PVC definition.


See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                                     | Default
----------------------- | -----------------------------------------------------------------               | ------------------------------------ |
PVC_NAME                | Targeted PersistentVolumeClaim in the cluster (if null, POD_NAME is required)   |                                      |
POD_NAME                | Targeted pod in the cluster (if null, PVC_NAME is required)                     |                                      |
NAMESPACE               | Targeted namespace in the cluster (required)                                    |                                      |
FILL_PERCENTAGE         | Targeted percentage to be filled up in the PVC                                  | 50                                   |
DURATION                | Duration in seconds with the PVC filled up                                      | 60                                   |
BLOCK_SIZE              | Block size (used by dd if fallocate not available in the container)             | 102400
**NOTE** Set NAMESPACE environment variable to `openshift-.*` to pick and disrupt pods randomly in openshift system namespaces, the DAEMON_MODE can also be enabled to disrupt the pods every x seconds in the background to check the reliability.


### Power Outages
This scenario shuts down Kubernetes/OpenShift cluster for the specified duration to simulate power outages, brings it back online and checks if it's healthy. More information can be found [here](https://github.com/krkn-chaos/krkn/blob/master/docs/cluster_shut_down_scenarios.md)

Right now power outage and cluster shutdown are one in the same. We originally created this scenario to stop all the nodes and then start them back up how a customer would shut their cluster down. 

In a real life chaos scenario though, we figured this scenario was close to if the power went out on the aws side so all of our ec2 nodes would be stopped/powered off.
We tried to look at if aws cli had a way to forcefully poweroff the nodes (not gracefully) and they don't currently support so this scenario is as close as we can get to "pulling the plug"

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:power-outages
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:power-outages
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:power-outages

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Demo

Demo can be found [here](https://asciinema.org/a/r0zLbh70XK7gnc4s5v0ZzSXGo)

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
export <parameter_name>=<value>

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
SHUTDOWN_DURATION       | Duration in seconds to shut down the cluster                          | 1200                                 |
CLOUD_TYPE              | Cloud platform on top of which cluster is running, [supported cloud platforms](https://github.com/krkn-chaos/krkn/blob/master/docs/node_scenarios.md)                     | aws |
TIMEOUT                 | Time in seconds to wait for each node to be stopped or running after the cluster comes back | 600                                |


The following environment variables need to be set for the scenarios that requires intereacting with the cloud platform API to perform the actions:

Amazon Web Services
```
$ export AWS_ACCESS_KEY_ID=<>
$ export AWS_SECRET_ACCESS_KEY=<>
$ export AWS_DEFAULT_REGION=<>
```

Google Cloud Platform
```
TBD
```

Azure
```
TBD
```

OpenStack

```
TBD
```

Baremetal
```
TBD
```

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios


### Node Network Filter Scenario
This scenario deploys a privileged workload on one or more nodes and will set iptables rules to block incoming and/or outgoing network traffic on given ports


#### Run

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-network-filter
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-network-filter
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-network-filter
$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```


#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`


See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

|  Parameter                    | Description                                                           | Default
|-------------------------------| -----------------------------------------------------------------     | ------------------------------------ |
| TOTAL_CHAOS_DURATION          | set chaos duration (in sec) as desired                                | 60                                  |
| NODE_SELECTOR                 | defines the node selector for choosing target nodes. If not specified, one schedulable node in the cluster will be chosen at random. If multiple nodes match the selector, all of them will be subjected to stress.| "node-role.kubernetes.io/worker=" |
| NODE_NAME                     | the node name to target (if label selector not selected|                        
| INSTANCE_COUNT               | restricts the number of selected nodes by the selector                                     | "1" |
| EXECUTION                         | sets the execution mode of the scenario on multiple nodes, can be parallel or serial|"parallel"|
| INGRESS                       | sets the network filter on incoming traffic, can be true or false| false |
| EGRESS                       | sets the network filter on outgoing traffic, can be true or false| true |                       
| INTERFACES                   | a list of comma separated names of network interfaces (eg. eth0 or eth0,eth1,eth2) to filter for outgoing traffic | "" |
| PORTS                        | a list of comma separated port numbers (eg 8080 or 8080,8081,8082) to filter for both outgoing and incoming traffic | "" |
| PROTOCOLS                    | a list of comma separated protocols to filter (tcp, udp or both) |



**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-network-filter
```

### Node Memory hog scenario
This scenario hogs the memory on the specified node on a Kubernetes/OpenShift cluster for a specified duration. For more information refer the following [documentation](https://github.com/krkn-chaos/krkn/blob/main/docs/arcaflow_scenarios/memory_hog.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-memory-hog
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-memory-hog
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-memory-hog

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`


See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

|  Parameter                    | Description                                                           | Default
|-------------------------------| -----------------------------------------------------------------     | ------------------------------------ |
| TOTAL_CHAOS_DURATION          | Set chaos duration (in sec) as desired                                | 60                                  |
| MEMORY_CONSUMPTION_PERCENTAGE | percentage  (expressed with the suffix %) or amount (expressed with the suffix b, k, m or g) of memory to be consumed by the scenario | 90% |
| NUMBER_OF_WORKERS             | Total number of workers (stress-ng threads)   | 1    |
| NAMESPACE                     | Namespace where the scenario container will be deployed | default |
| NODE_SELECTOR                 | defines the node selector for choosing target nodes. If not specified, one schedulable node in the cluster will be chosen at random. If multiple nodes match the selector, all of them will be subjected to stress. If number-of-nodes is specified, that many nodes will be randomly selected from those identified by the selector.                                     | "" |                             |
| NUMBER_OF_NODES               | restricts the number of selected nodes by the selector                                     | "" |                             |
| IMAGE                         | the container image of the stress workload|quay.io/krkn-chaos/krkn-hog||                          


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-memory-hog
```

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/452742?speed=3&theme=solarized-dark)


### Pod Scenarios
This scenario disrupts the pods matching the label in the specified namespace on a Kubernetes/OpenShift cluster.

#### Run

If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-scenarios
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-scenarios
OR 
$ docker run -e <VARIABLE>=<value> --name=<container_name> --net=host -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:pod-scenarios

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```
#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

Parameter               | Description                                                           | Default
----------------------- | -----------------------------------------------------------------     | ------------------------------------ |
NAMESPACE               | Targeted namespace in the cluster ( supports regex )                                     | openshift-.*                         |
POD_LABEL               | Label of the pod(s) to target                                         | ""                                   | 
NAME_PATTERN            | Regex pattern to match the pods in NAMESPACE  when POD_LABEL is not specified | .* |
DISRUPTION_COUNT        | Number of pods to disrupt                                             | 1                                    |
KILL_TIMEOUT            | Timeout to wait for the target pod(s) to be removed in seconds        | 180                                  |
EXPECTED_RECOVERY_TIME           | Fails if the pod disrupted do not recover within the timeout set      | 120                                  |

**NOTE** Set NAMESPACE environment variable to `openshift-.*` to pick and disrupt pods randomly in openshift system namespaces, the DAEMON_MODE can also be enabled to disrupt the pods every x seconds in the background to check the reliability.

**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/home/krkn/kraken/config/metrics-aggregated.yaml` and `/home/krkn/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/home/krkn/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/home/krkn/kraken/config/alerts -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:container-scenarios
```

#### Demo
You can find a link to a demo of the scenario [here](https://asciinema.org/a/452351?speed=3&theme=solarized-dark)


### Node IO hog scenario
This scenario hogs the IO on the specified node on a Kubernetes/OpenShift cluster for a specified duration. For more information refer the following [documentation](https://github.com/krkn-chaos/krkn/blob/main/docs/hog_scenarios.md).

#### Run
If enabling [Cerberus](https://github.com/krkn-chaos/krkn#kraken-scenario-passfail-criteria-and-report) to monitor the cluster and pass/fail the scenario post chaos, refer [docs](https://github.com/redhat-chaos/krkn-hub/tree/main/docs/cerberus.md). Make sure to start it before injecting the chaos and set `CERBERUS_ENABLED` environment variable for the chaos injection container to autoconnect.

```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-kube-config>:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-io-hog
$ podman logs -f <container_name or container_id> # Streams Kraken logs
$ podman inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```

```
$ docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v <path-to-kube-config>:/root/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-io-hog
OR 
$ docker run -e <VARIABLE>=<value> --net=host -v <path-to-kube-config>:/root/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-io-hog

$ docker logs -f <container_name or container_id> # Streams Kraken logs
$ docker inspect <container-name or container-id> --format "{{.State.ExitCode}}" # Outputs exit code which can considered as pass/fail for the scenario
```
**TIP**: Because the container runs with a non-root user, ensure the kube config is globally readable before mounting it in the container. You can achieve this with the following commands:
```kubectl config view --flatten > ~/kubeconfig && chmod 444 ~/kubeconfig && docker run $(./get_docker_params.sh) --name=<container_name> --net=host -v ~kubeconfig:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:<scenario>```

#### Supported parameters

The following environment variables can be set on the host running the container to tweak the scenario/faults being injected:

ex.) 
`export <parameter_name>=<value>`

See list of variables that apply to all scenarios [here](all_scenarios_env.md) that can be used/set in addition to these scenario specific variables

|  Parameter           | Description                                                                                                                                                                                                                                                                                                                           | Default
|----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| ------------------------------------                   |
| TOTAL_CHAOS_DURATION | Set chaos duration (in sec) as desired                                                                                                                                                                                                                                                                                                | 180                                  |
| IO_BLOCK_SIZE        | string size of each write in bytes. Size can be from 1 byte to 4m                                                                                                                                                                                                                                                                     | 1m |
| IO_WORKERS           | Number of stressorts                                                                                                                                                                                                                                                                                                                  | 5 |
| IO_WRITE_BYTES       | string writes N bytes for each hdd process. The size can be expressed as % of free space on the file system or in units of Bytes, KBytes, MBytes and GBytes using the suffix b, k, m or g                                                                                                                                             | 10m |
| NAMESPACE            | Namespace where the scenario container will be deployed                                                                                                                                                                                                                                                                               | default |
| NODE_SELECTOR        | defines the node selector for choosing target nodes. If not specified, one schedulable node in the cluster will be chosen at random. If multiple nodes match the selector, all of them will be subjected to stress. If number-of-nodes is specified, that many nodes will be randomly selected from those identified by the selector. | "" |                             |
| NODE_MOUNT_PATH        | the local path in the node that will be mounted in the pod and that will be filled by the scenario                                                                                                                                                                                                                                    | "" |                             |
| NUMBER_OF_NODES      | restricts the number of selected nodes by the selector                                                                                                                                                                                                                                                                                | "" |                             |
| IMAGE                | the container image of the stress workload                                                                                                                                                                                                                                                                                            |quay.io/krkn-chaos/krkn-hog||


**NOTE** In case of using custom metrics profile or alerts profile when `CAPTURE_METRICS` or `ENABLE_ALERTS` is enabled, mount the metrics profile from the host on which the container is run using podman/docker under `/root/kraken/config/metrics-aggregated.yaml` and `/root/kraken/config/alerts`. For example:
```
$ podman run --name=<container_name> --net=host --env-host=true -v <path-to-custom-metrics-profile>:/root/kraken/config/metrics-aggregated.yaml -v <path-to-custom-alerts-profile>:/root/kraken/config/alerts -v <path-to-kube-config>:/root/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:node-io-hog
```



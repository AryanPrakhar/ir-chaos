#### User query examples
- Crash the KubeVirt virtual machine.
- Delete the VMI to test automatic recreation.
- Simulate a virtual machine failure in OpenShift CNV.
- Forcefully terminate the KubeVirt VM instance.
- Hard stop the virtualized workload.
- Yank the virtual power cord on the KVM guest.
- Destroy the virtual machine instance.
- Simulate a hypervisor fault taking down the VM.
- Test if the VirtualMachine runStrategy actually works.
- Kill the Windows VM running inside OpenShift.
- Pull the plug on the guest OS.

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

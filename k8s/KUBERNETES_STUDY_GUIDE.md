# Kubernetes Mastery Study Guide

A depth-first guide to mastering Kubernetes as an operator and platform engineer. Assumes you already know basic container concepts (`docker run`, images, registries) and have used `kubectl` at least once. Each phase builds on the previous. Deep networking lives in the sibling [Docker & Kubernetes Networking](DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md) guide; production hardening lives in [Kubernetes Security](KUBERNETES_SECURITY_STUDY_GUIDE.md). This guide focuses on the core API, workloads, scheduling, and day-2 operations.

---

## Phase 1: Core Foundations

### 1.1 Cluster Architecture

- **Control plane components**: the brain of the cluster. Run on dedicated nodes (or managed for you in EKS/GKE/AKS).
  - `kube-apiserver` — the only component that talks to `etcd`. All other components watch the API for changes. It's a stateless REST/gRPC frontend, so you scale it horizontally.
  - `etcd` — the source of truth. Strongly-consistent key-value store backed by Raft. Lose etcd, lose the cluster. Snapshot it. Encrypt it at rest.
  - `kube-scheduler` — watches for unscheduled pods, picks a node based on filtering (predicates) and scoring (priorities). Stateless; multiple instances elect a leader.
  - `kube-controller-manager` — runs the built-in controllers (deployment, replicaset, node, endpoints, service-account, etc.). Each is a control loop reconciling desired vs. actual state.
  - `cloud-controller-manager` — cloud-provider-specific glue (load balancers, route tables, node lifecycle).
  - References: [Components](https://kubernetes.io/docs/concepts/overview/components/), [`etcd` overview](https://etcd.io/docs/current/)
- **Node components**: run on every worker.
  - `kubelet` — the node agent. Watches the API for pods assigned to its node, instructs the container runtime to start/stop containers, reports status back. The kubelet is what *actually* runs your workloads.
  - `kube-proxy` — programs iptables / IPVS / nftables rules to implement Service load balancing. Increasingly being replaced by eBPF dataplanes (Cilium).
  - **Container runtime** — Docker is out. Modern clusters use `containerd` or `CRI-O`, both speaking the [CRI](https://kubernetes.io/docs/concepts/architecture/cri/) protocol.
  - References: [kubelet](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/), [kube-proxy modes](https://kubernetes.io/docs/reference/networking/virtual-ips/)
- **Addons** that almost every cluster runs: CoreDNS, metrics-server, a CNI plugin (Calico, Cilium, Flannel), CSI drivers, an Ingress controller.

**Practice**: On a kind or minikube cluster, run `kubectl get pods -n kube-system` and identify each control-plane and node component. Then `kubectl get --raw /readyz?verbose` to see every health check the API server runs.

---

### 1.2 The API Model

Everything in Kubernetes is a resource exposed by the API server. Internalize this and the system stops feeling magical.

- **Group / Version / Kind (GVK)**: every object identifies itself by a tuple. Example: `apps/v1` `Deployment`, `networking.k8s.io/v1` `Ingress`. The empty group (`""`) is the legacy "core" group containing `Pod`, `Service`, `Node`, etc.
- **`spec` vs. `status`**: you declare desired state in `spec`. Controllers write observed state to `status`. Never edit `status` directly.
- **Declarative reconciliation**: you submit desired state; a controller continuously diffs it against actual state and acts. This is the entire programming model.
- **`metadata`**: name, namespace, labels, annotations, owner references, finalizers, `resourceVersion` (used for optimistic concurrency). Labels are for selecting; annotations are for arbitrary metadata that machines or humans read.
- **Discovery**: `kubectl api-resources` lists every kind your cluster knows about. `kubectl explain deploy.spec.template.spec.containers` walks the schema interactively.
- References: [API conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md), [API overview](https://kubernetes.io/docs/concepts/overview/kubernetes-api/)

**Practice**: Pick any object on your cluster and run `kubectl get <kind> <name> -o yaml`. Identify which fields are user-written (`spec`, `metadata`) and which are controller-written (`status`, `metadata.uid`, `metadata.resourceVersion`).

---

### 1.3 Namespaces

- A namespace is a scope for resource *names* and a target for RBAC and resource quotas. It is **not** a security boundary by itself — pods in different namespaces share the same node, kernel, and network unless you add policy.
- Cluster-scoped resources (Nodes, PersistentVolumes, ClusterRoles, CRDs) have no namespace. Namespaced resources (Pods, Services, ConfigMaps, Deployments) do.
- Default namespaces: `default`, `kube-system` (control-plane addons), `kube-public` (world-readable cluster info), `kube-node-lease` (node heartbeats).
- Cross-namespace DNS: `<service>.<namespace>.svc.cluster.local`. Within a namespace you can use just `<service>`.
- References: [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)

---

### 1.4 kubectl Mastery

`kubectl` is the swiss army knife. Treat it like `psql` or `git` — invest in fluency.

- **Contexts & kubeconfig**: a kubeconfig is `(cluster, user, namespace)` tuples grouped into contexts. `kubectl config get-contexts`, `kubectl config use-context`, `kubectl config set-context --current --namespace=foo`. Use [`kubectx`](https://github.com/ahmetb/kubectx) / `kubens` to switch fast.
- **Imperative vs. declarative**:
  - Imperative: `kubectl run`, `kubectl create deploy`, `kubectl expose`, `kubectl scale`. Fast for experiments and debugging.
  - Declarative: `kubectl apply -f`. The right way to manage production. `apply` reconciles your YAML against the cluster using a three-way merge (last-applied annotation, live, desired).
  - Use `--dry-run=client -o yaml` to scaffold YAML from imperative commands.
- **Output formats**: `-o yaml`, `-o json`, `-o wide`, `-o jsonpath='{.items[*].metadata.name}'`, `-o go-template`, `-o custom-columns=NAME:.metadata.name,STATUS:.status.phase`.
- **Selectors**: `-l app=web,env!=prod`, `--field-selector status.phase=Running,spec.nodeName=node1`. Label selectors are how you filter at scale.
- **Debug commands**: `kubectl logs`, `kubectl logs -f --previous` (last crashed container), `kubectl exec -it`, `kubectl port-forward`, `kubectl cp`, `kubectl describe`, `kubectl top pod`, `kubectl events --watch`, `kubectl debug` (ephemeral debug containers).
- **Bulk ops**: `kubectl get pods -A` (all namespaces), `kubectl delete pods --field-selector status.phase=Failed -A`.
- **`kubectl diff`** — show what `apply` *would* change before doing it. Underrated.
- **Plugins via `krew`**: `kubectl krew install ctx ns neat tree access-matrix`. `kubectl neat` strips server-side junk from YAML; `tree` shows owner-reference graphs.
- References: [kubectl cheatsheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/), [JSONPath](https://kubernetes.io/docs/reference/kubectl/jsonpath/)

**Practice**: Build a one-liner that lists every container image running in the cluster, with counts, sorted. Hint: `kubectl get pods -A -o jsonpath=...` piped through `sort | uniq -c | sort -rn`.

---

## Phase 2: Workloads

### 2.1 Pods

The atomic unit of scheduling. Not the atomic unit of *deployment* — you almost never create bare Pods in production.

- **One pod, many containers, one network/IPC namespace**. Containers in a pod share a Linux network namespace (same `localhost`, same IP) and can share volumes. They do *not* share PID or filesystem namespaces by default.
- **`pause` container**: every pod has an invisible infra container that holds the namespaces open. When you `docker ps` on a node and see `pause` containers, that's why.
- **Init containers** run sequentially before app containers. Used for setup work (waiting for a dependency, fetching config, running migrations). Failure of any init container restarts the pod.
- **Sidecar containers** (GA in 1.29+): native sidecar lifecycle via `restartPolicy: Always` on an init container. Starts before app, stops after, and the kubelet treats it correctly during shutdown. Use this instead of the old "just add another container" pattern when ordering matters (e.g., log shipper, service mesh proxy).
- **Probes** — the kubelet uses these to manage container state.
  - `livenessProbe`: kubelet restarts the container if it fails. Use for *deadlock* detection only. Aggressive liveness is a top cause of cascading outages.
  - `readinessProbe`: kubelet removes the pod from Service endpoints if it fails. Use this liberally — it's how rolling deploys stay healthy.
  - `startupProbe`: gives slow-starting apps room before liveness kicks in. Disables liveness until startup succeeds.
  - Mechanisms: `httpGet`, `tcpSocket`, `exec`, `grpc` (1.27+).
- **Pod lifecycle phases**: `Pending` → `Running` → `Succeeded` / `Failed`. `Unknown` means the kubelet hasn't reported recently.
- **`terminationGracePeriodSeconds`** — default 30s. On delete, kubelet sends SIGTERM, waits this long, then SIGKILL. Tune for apps with long in-flight work.
- **`preStop` hook** — runs *before* SIGTERM. Used to drain connections, deregister from external systems, or `sleep` to let load balancers notice. A `sleep 10` `preStop` is a common fix for "requests fail during deploys."
- References: [Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), [Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

---

### 2.2 ReplicaSets and Deployments

- A **ReplicaSet** ensures N pods matching a label selector exist. You almost never write one directly.
- A **Deployment** owns ReplicaSets and orchestrates rolling updates. On every change to `spec.template`, the Deployment controller creates a *new* ReplicaSet and gradually scales it up while scaling the old one down.
- **Rollout strategy**:
  - `RollingUpdate` (default): `maxSurge` and `maxUnavailable` control the pace. Defaults (25%/25%) are fine for most apps; tighten `maxUnavailable: 0` for zero-downtime critical paths.
  - `Recreate`: kill all old, then create new. Use only when two versions cannot coexist (e.g., incompatible schema mid-deploy).
- **`kubectl rollout`**: `status`, `history`, `undo`, `pause`, `resume`, `restart` (rolling restart without changing the spec — useful after a Secret change).
- **`revisionHistoryLimit`** — how many old ReplicaSets to keep for `rollout undo`. Default 10.
- **`progressDeadlineSeconds`** — if a rollout makes no progress for this long, the Deployment is marked failed. Wire this into CD to fail builds.
- **Selector immutability**: `spec.selector` cannot change after creation. If you need to change labels, create a new Deployment.
- References: [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

---

### 2.3 StatefulSets

For workloads that need *stable identity*: databases, message brokers, anything caching state on disk.

- Pods get **predictable names**: `web-0`, `web-1`, `web-2`. Ordinal index matters — `-0` always comes up first, scale-down deletes the highest ordinal first.
- Each pod gets its own **PersistentVolumeClaim** via `volumeClaimTemplates`. PVCs survive pod deletion and are reattached when the pod is rescheduled.
- A **headless Service** (`clusterIP: None`) gives each pod a stable DNS name: `web-0.web.default.svc.cluster.local`. This is the magic that lets `web-1` find `web-0` reliably.
- **Update strategies**: `RollingUpdate` (default, in reverse ordinal order) and `OnDelete` (you trigger updates by deleting pods). `partition` lets you canary by ordinal.
- StatefulSets do **not** delete PVCs by default when you delete the StatefulSet. This is a feature; it's also a foot-gun. `persistentVolumeClaimRetentionPolicy` (1.27+) gives you control.
- References: [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

---

### 2.4 DaemonSets, Jobs, CronJobs

- **DaemonSet**: one pod per node (filtered by selectors/taints). Used for node-level agents: log shippers, monitoring, CNI/CSI plugins, security agents.
  - `updateStrategy: RollingUpdate` with `maxUnavailable` controls how many nodes are disrupted at once.
- **Job**: runs pods to completion. `completions` (how many successful pods needed), `parallelism` (max concurrent), `backoffLimit` (retries before failure), `activeDeadlineSeconds` (timeout).
  - Modes: non-indexed (default), `Indexed` (each pod gets a `JOB_COMPLETION_INDEX` env var — great for parallel data processing).
- **CronJob**: runs a Job on a cron schedule. `concurrencyPolicy: Allow|Forbid|Replace` controls overlapping runs. `startingDeadlineSeconds` bounds how late a missed run can fire. `successfulJobsHistoryLimit` and `failedJobsHistoryLimit` prevent unbounded Job buildup — a classic operational footgun.
- References: [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)

---

## Phase 3: Configuration & State

### 3.1 ConfigMaps and Secrets

- **ConfigMap**: arbitrary key-value config, plaintext. Mount as env vars or files.
- **Secret**: same shape, base64-encoded (NOT encrypted by default — encryption-at-rest must be configured on the API server). Stored in etcd.
- **Consumption patterns**:
  - `envFrom` — inject every key as an env var. Convenient but pollutes the env.
  - `env.valueFrom.configMapKeyRef` / `secretKeyRef` — explicit, one variable at a time. Prefer this.
  - Volume mount — each key becomes a file. The kubelet *updates the files in place* when the ConfigMap changes (within ~60s). Env vars do **not** update; you need a rolling restart.
- **Immutable ConfigMaps/Secrets** (`immutable: true`): prevents accidental update, drastically reduces API server load for large fleets.
- **External secret stores**: most production clusters run [External Secrets Operator](https://external-secrets.io/) or a CSI secret driver (AWS Secrets Manager, Vault, GCP Secret Manager). Keeps real secrets out of etcd entirely.
- References: [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/), [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

### 3.2 Persistent Storage

- **PersistentVolume (PV)**: a piece of storage in the cluster (NFS export, EBS volume, Ceph RBD, etc.). Cluster-scoped.
- **PersistentVolumeClaim (PVC)**: a namespaced request for storage. Binds 1:1 to a PV.
- **StorageClass**: dynamic provisioning. A PVC referencing a StorageClass triggers the CSI driver to create a PV on demand. This is what you'll use 99% of the time — static PVs are mostly legacy.
- **Access modes**: `ReadWriteOnce` (RWO — single node), `ReadOnlyMany` (ROX), `ReadWriteMany` (RWX — single node read-write, multiple nodes elsewhere), `ReadWriteOncePod` (RWOP — single pod, K8s 1.27+). Most block storage is RWO; file storage (NFS, EFS) is RWX.
- **Reclaim policy**: `Delete` (PV deleted when PVC deleted — destructive!) vs. `Retain` (PV kept, manual cleanup). StorageClass defaults to `Delete`; override for anything you care about.
- **Volume expansion**: `allowVolumeExpansion: true` on the StorageClass + edit the PVC's `spec.resources.requests.storage`. Shrinking is not supported.
- **CSI**: the [Container Storage Interface](https://kubernetes-csi.github.io/docs/) — the plugin protocol all modern storage drivers speak. Out-of-tree, so storage updates don't require a Kubernetes upgrade.
- References: [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)

### 3.3 Other Volume Types

- `emptyDir` — scratch space tied to the pod's lifetime. Use `medium: Memory` for a tmpfs ramdisk.
- `hostPath` — mounts a path from the node. Avoid in app workloads (breaks portability, security risk); fine for node-level agents.
- `projected` — combine multiple sources (ConfigMaps, Secrets, downwardAPI, service account tokens) into one mount point. The mechanism behind modern service account token projection.
- `downwardAPI` — exposes pod/container metadata (labels, annotations, resource limits) as files or env vars.

---

## Phase 4: Services & Discovery

This is a light treatment — the deep dive lives in the [networking guide](DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md).

### 4.1 Services

- A **Service** is a stable virtual IP + DNS name that load-balances to a set of pods selected by labels.
- **Types**:
  - `ClusterIP` (default) — only reachable inside the cluster. The right default.
  - `NodePort` — opens a port (30000–32767) on every node. Mostly a building block; rarely the right user-facing choice.
  - `LoadBalancer` — provisions an external L4 load balancer via the cloud-controller-manager. Costs money per service.
  - `ExternalName` — DNS CNAME to an external host. No proxying.
- **Endpoints / EndpointSlices**: the *actual* list of pod IPs behind a Service. The endpoints controller (or EndpointSlice controller, the newer scalable version) reconciles these from the Service's pod selector. `kubectl get endpointslices -l kubernetes.io/service-name=<svc>` to inspect.
- **Headless Services** (`clusterIP: None`) — no virtual IP, DNS returns the pod IPs directly. Use for StatefulSets and any time the client needs to know individual backends.
- **`sessionAffinity: ClientIP`** — sticky sessions based on source IP. Crude; usually you want an L7 ingress with cookie-based affinity instead.

### 4.2 DNS

- **CoreDNS** is the cluster DNS server. Configured via the `coredns` ConfigMap in `kube-system`.
- Service DNS: `<service>.<namespace>.svc.cluster.local`. Same namespace: `<service>` suffices. The `search` path in `/etc/resolv.conf` makes both work.
- Pod DNS: `<pod-ip-with-dashes>.<namespace>.pod.cluster.local`. Rarely useful.
- **`ndots:5`** — by default, `resolv.conf` has `ndots: 5`, which causes any name with fewer than 5 dots to be tried against the search path *first*. This is why external DNS lookups from pods can be slow (5 misses before the real query). Set `dnsConfig` on chatty pods if it matters.

### 4.3 Ingress and Gateway API

- **Ingress** — L7 HTTP routing. Requires an Ingress *controller* (nginx-ingress, Traefik, HAProxy, AWS ALB, GCP GLB) to be running; the Ingress resource itself is just config.
- **`IngressClass`** — tells the cluster *which* controller should service a given Ingress.
- **Gateway API** is the modern successor: better separation between platform and app teams (`GatewayClass` / `Gateway` owned by ops, `HTTPRoute` / `GRPCRoute` / `TLSRoute` owned by app teams), explicit support for L4 + L7, and a clean protocol-aware model. New work should target Gateway API where the controller supports it.
- References: [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Gateway API](https://gateway-api.sigs.k8s.io/)

---

## Phase 5: Scheduling & Resource Management

### 5.1 Requests and Limits

- **`requests`** — what the scheduler uses to find a node. The pod *reserves* this much.
- **`limits`** — what the kubelet enforces at runtime. Exceeding CPU limits throttles; exceeding memory limits gets you OOMKilled.
- **QoS classes**, derived automatically:
  - `Guaranteed` — every container has `requests == limits` for both CPU and memory. Last to be evicted under node pressure.
  - `Burstable` — at least one container has requests but no matching limit, or partial coverage. Middle eviction priority.
  - `BestEffort` — no requests or limits. First to be evicted.
- **CPU limits are controversial**. Throttling can cause latency spikes far worse than the CPU saved. Many shops set requests-only on CPU and rely on the node being correctly sized; always set memory limits.
- **Resource units**: CPU in cores (`500m` = 0.5 core). Memory in bytes (`Mi` = mebibytes, `M` = megabytes — they are *different*; almost always use `Mi`/`Gi`).
- **Ephemeral storage** also has requests/limits. Exceeding the limit evicts the pod. Easy to overlook until a log-spam app brings down a node.
- References: [Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [QoS](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)

### 5.2 Scheduling Constraints

- **`nodeSelector`** — simplest form: pod runs only on nodes with matching labels.
- **Node affinity / anti-affinity** — richer expressions. `requiredDuringSchedulingIgnoredDuringExecution` (hard, only at schedule time) vs. `preferredDuringScheduling...` (soft, weighted).
- **Pod affinity / anti-affinity** — schedule based on what *other pods* are running. Classic use: spread replicas across zones (`topologyKey: topology.kubernetes.io/zone` with anti-affinity).
- **Taints and tolerations** — *taints* repel pods from a node; *tolerations* on a pod let it tolerate matching taints. Effects: `NoSchedule`, `PreferNoSchedule`, `NoExecute`. Used for dedicated nodes (e.g., GPU pools), control-plane isolation, and node draining.
- **Topology spread constraints** — declarative "spread me across these topology domains" with `maxSkew`. Cleaner than pod anti-affinity for most spread cases.
- **PriorityClasses** — when the cluster is full, higher-priority pods can preempt (evict) lower-priority pods. `system-cluster-critical` and `system-node-critical` are reserved for control-plane workloads.
- References: [Assigning pods to nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/), [Taints and tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)

### 5.3 Autoscaling

- **Horizontal Pod Autoscaler (HPA)** — scales replica count based on metrics. CPU and memory out of the box; custom and external metrics via the metrics adapter API. Needs `metrics-server` installed.
- **Vertical Pod Autoscaler (VPA)** — adjusts requests/limits based on observed usage. Three modes: `Off` (recommendations only), `Auto` (recreates pods with new values), `Initial` (only sets at create time). Don't use HPA and VPA on the same resource (they fight) unless you use VPA in `Off` mode for recommendations only.
- **Cluster Autoscaler** — adds/removes nodes from the node group when pods can't be scheduled / nodes are idle. Cloud-provider-specific.
- **Karpenter** (AWS-born, now multi-cloud) — modern replacement for Cluster Autoscaler. Provisions right-sized nodes on demand instead of scaling fixed node groups. Significantly faster and cheaper.
- References: [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/), [Karpenter](https://karpenter.sh/)

---

## Phase 6: Operations & Debugging

### 6.1 Common Failure Modes

You will see these forever. Learn them cold.

- **`Pending`** — the scheduler can't place the pod. `kubectl describe pod` → events. Usually: insufficient resources, no node matches affinity/taints, PVC unbound, image pull secret missing.
- **`ImagePullBackOff` / `ErrImagePull`** — the kubelet can't pull the image. Check `imagePullSecrets`, registry connectivity, image name/tag, and your image actually exists.
- **`CrashLoopBackOff`** — the container starts and exits repeatedly. `kubectl logs --previous` to see the last crashed instance's output. The "backoff" is exponential, capped at 5 minutes.
- **`OOMKilled`** (exit code 137) — container exceeded its memory limit, kernel killed it. `kubectl describe` shows the reason. Either raise the limit or fix the leak.
- **`Evicted`** — the kubelet evicted the pod due to node pressure (memory, disk, PIDs). Check node conditions: `kubectl describe node`.
- **`Terminating` stuck forever** — usually a finalizer holding it open. `kubectl get <obj> -o yaml | grep finalizers`. Investigate *why* before force-removing — finalizers usually mean a controller hasn't finished cleanup.
- **Stuck rollout** — `kubectl rollout status` will tell you what's wrong. Common causes: failing readiness probes, ImagePullBackOff, insufficient cluster capacity (new replicas can't schedule).

### 6.2 The Debug Toolkit

- `kubectl describe <kind> <name>` — *the* first thing to run. The Events section at the bottom is gold.
- `kubectl logs <pod> -c <container> -f --previous` — `-c` for multi-container, `-f` to follow, `--previous` for the last crashed instance.
- `kubectl exec -it <pod> -- sh` — shell into a running container. Doesn't work if your image is `FROM scratch` or distroless.
- `kubectl debug` — modern alternative. `kubectl debug -it <pod> --image=busybox --target=<container>` adds an ephemeral container sharing the target's namespaces. Works on distroless. `kubectl debug node/<node> -it --image=alpine` for a host-namespace shell on a node.
- `kubectl port-forward svc/foo 8080:80` — local tunnel to a service/pod. Indispensable for debugging.
- `kubectl events --watch -A` — live stream of cluster events. Or `kubectl get events --sort-by=.lastTimestamp -A`.
- `kubectl top pod / node` — live resource usage (needs metrics-server).
- `kubectl auth can-i --as=system:serviceaccount:ns:sa create deployments` — RBAC simulator.
- `crictl` on the node — talks directly to the container runtime, bypassing the kubelet. Use when kubelet itself is unhealthy.

### 6.3 Node Operations

- **Drain a node** before maintenance: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`. This cordons the node (no new pods) and evicts existing pods, respecting PodDisruptionBudgets.
- **Cordon / uncordon** — `kubectl cordon` marks unschedulable without evicting; `uncordon` reverses.
- **PodDisruptionBudgets (PDBs)** — declare minimum availability (`minAvailable: 2` or `maxUnavailable: 1`). The eviction API blocks `drain` from violating PDBs. Every production workload should have one.

---

## Phase 7: Extending Kubernetes

### 7.1 Custom Resources & Operators

- **CustomResourceDefinitions (CRDs)** — let you add new API types. The cluster gains `kubectl get <yourkind>` for free.
- **OpenAPI v3 schemas** on CRDs give validation, defaulting, and `kubectl explain` for your types. Always define one.
- **Controllers / Operators** — code that watches CRD instances and reconciles them against the world. The Kubernetes way to automate any stateful application.
- **Frameworks**: [`controller-runtime`](https://book.kubebuilder.io/) (Go, the standard), [`kopf`](https://kopf.readthedocs.io/) (Python), [`metacontroller`](https://metacontroller.github.io/metacontroller/) (declarative hooks). Start with Kubebuilder for Go.
- **Operator pattern**: capture human operator knowledge as a controller. Examples: cert-manager, Prometheus Operator, etcd-operator, Crossplane.
- References: [CRDs](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/), [Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)

### 7.2 Admission Control

- Requests to the API server pass through: authentication → authorization → admission → schema validation → storage.
- **Built-in admission plugins**: `NamespaceLifecycle`, `LimitRanger`, `ResourceQuota`, `PodSecurity`, etc.
- **Validating webhooks** — reject requests that don't meet policy.
- **Mutating webhooks** — modify the request (inject sidecars, defaults, labels). Order matters; mutators run before validators.
- **Policy engines**: [Kyverno](https://kyverno.io/) (CRD-driven, no DSL), [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/) (Rego). Modern clusters use one or the other to enforce org policy.
- References: [Admission controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)

### 7.3 Packaging

- **Helm** — templating + release lifecycle. Charts are tar.gz of YAML templates + `values.yaml`. Production-grade once you understand it; library charts and subcharts can get ugly.
- **Kustomize** — overlay-based, no templating, built into `kubectl` (`kubectl apply -k`). Bases + overlays per environment. Often the right choice for in-house apps.
- **Helm vs. Kustomize**: not mutually exclusive. Common pattern: install vendor stuff via Helm, manage in-house apps via Kustomize. Or render Helm to YAML and post-process with Kustomize.
- References: [Helm](https://helm.sh/docs/), [Kustomize](https://kustomize.io/)

---

## Phase 8: Observability

- **Metrics**:
  - `metrics-server` — basic pod/node CPU and memory for HPA and `kubectl top`. Not for long-term storage.
  - **Prometheus** + `kube-state-metrics` — the standard. `kube-state-metrics` exposes cluster object state (deployment replica counts, pod phases, etc.); node-exporter exposes node-level metrics; Prometheus scrapes both.
  - **OpenTelemetry Collector** — increasingly the right answer for metrics + traces + logs in one pipeline.
- **Logs**: containers write to stdout/stderr; the kubelet writes those to `/var/log/containers/` on the node. A node agent (Fluent Bit, Vector, Promtail) ships them to a store (Loki, Elasticsearch, Cloud logging service). Do **not** rely on `kubectl logs` for anything other than live debugging — kubelet rotation drops history.
- **Traces**: instrument apps with OTel, ship to Tempo/Jaeger/Honeycomb/etc. Service mesh sidecars (Istio, Linkerd) can add traces automatically without code changes.
- **Events**: `kubectl get events` is your built-in event log. They expire (default 1 hour) — for retention, ship them via [`kubernetes-event-exporter`](https://github.com/resmoio/kubernetes-event-exporter) or a logging pipeline.
- References: [Logging architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/), [Prometheus Operator](https://prometheus-operator.dev/)

---

## Phase 9: Production Patterns & Pitfalls

- **Always set resource requests**. Without them the scheduler treats your pod as zero-cost and node packing breaks. BestEffort pods are first to die.
- **Always set readiness probes**. Without them, rolling deploys route traffic to half-started pods.
- **Be conservative with liveness probes**. A flaky liveness probe under load can take your service offline by restarting every pod. Use startup probes for slow boot, readiness for traffic gating, liveness only for true hangs.
- **Pod anti-affinity or topology spread** for any service with ≥2 replicas — otherwise the scheduler may put them all on one node and a node loss takes you down.
- **PodDisruptionBudgets** for every production deployment. Otherwise a node drain can violate your SLO.
- **`terminationGracePeriodSeconds` + `preStop`** for graceful shutdown. Common pattern: `preStop: sleep 10` + app handles SIGTERM by closing the listener and draining in-flight requests.
- **Avoid `latest` tags**. Always pin by digest in production. The kubelet may cache `latest` differently across nodes, causing impossibly weird drift.
- **`imagePullPolicy`**: `Always` for floating tags (slow), `IfNotPresent` for pinned tags (fast). The default is `IfNotPresent` unless the tag is `latest`.
- **Cluster upgrades** — control plane first, then nodes, one node-group at a time. Read the [version skew policy](https://kubernetes.io/releases/version-skew-policy/) — kubelet must be no more than 3 minor versions behind the API server, and you can't skip minor versions.
- **etcd backups** are non-negotiable. `etcdctl snapshot save` daily, off-cluster.
- **Avoid hostNetwork / hostPID / privileged** in app workloads. Use them only for node agents, and gate with admission policy.
- **Don't use `default` namespace**. Per-team or per-app namespaces with RBAC scoped to them are easier to reason about and quota.
- **Quota everything**: ResourceQuotas per namespace, LimitRanges to set per-pod defaults, NetworkPolicies to default-deny.

---

## Phase 10: Ecosystem & Tooling

- **CLI quality of life**: [`k9s`](https://k9scli.io/) (TUI), [`stern`](https://github.com/stern/stern) (multi-pod log tailing), [`kubectx`/`kubens`](https://github.com/ahmetb/kubectx), [`kube-ps1`](https://github.com/jonmosco/kube-ps1) (shell prompt), [`kubectl-tree`](https://github.com/ahmetb/kubectl-tree), [`kubeshark`](https://kubeshark.co/) (cluster-wide traffic capture).
- **GitOps**: [Argo CD](https://argo-cd.readthedocs.io/) and [Flux](https://fluxcd.io/) — declarative cluster state from a Git repo. Pull-based deploys. Replaces "kubectl apply from CI" in serious shops.
- **Service mesh**: [Istio](https://istio.io/), [Linkerd](https://linkerd.io/), [Cilium Service Mesh](https://cilium.io/use-cases/service-mesh/). Worth it for mTLS, fine-grained traffic policy, and L7 observability. Operational cost is real — don't add a mesh until you can articulate the specific problem it solves.
- **Local clusters**: [`kind`](https://kind.sigs.k8s.io/) (Docker-in-Docker, fast), [`minikube`](https://minikube.sigs.k8s.io/), [`k3d`](https://k3d.io/) (k3s in Docker — tiny and fast).
- **Distributions worth knowing**: managed (EKS, GKE, AKS), self-hosted (kubeadm, kops), edge/lightweight ([k3s](https://k3s.io/), MicroK8s), bare-metal ([Talos](https://www.talos.dev/) — immutable, API-driven, no SSH).

---

## Mastery Checklist

You're solid on Kubernetes when you can, without looking anything up:

- Explain what happens between `kubectl apply -f deployment.yaml` and a running pod, by component.
- Write a Deployment, Service, Ingress, ConfigMap, Secret, PVC by hand.
- Debug `Pending`, `CrashLoopBackOff`, `ImagePullBackOff`, `OOMKilled`, and stuck `Terminating` pods.
- Choose between Deployment / StatefulSet / DaemonSet / Job for a given workload.
- Set up RBAC for a service account so it can do exactly what it needs and no more.
- Use taints, tolerations, affinity, and topology spread to control where pods land.
- Configure HPA against a custom metric.
- Write a CRD with an OpenAPI schema and reason about how a controller would reconcile it.
- Recover a cluster from an etcd snapshot.
- Read the Events stream and understand what every line means.

---

## Recommended Reading Path

1. Kubernetes docs — [Concepts](https://kubernetes.io/docs/concepts/) section, end to end. Slow read, take notes.
2. *Kubernetes Up & Running* (Burns, Beda, Hightower, Villalba) — concise, current.
3. *Programming Kubernetes* (Hausenblas, Schimanski) — for writing controllers and operators.
4. The [Kubebuilder Book](https://book.kubebuilder.io/) — practical operator development.
5. KubeCon talks on YouTube — current production patterns from people running clusters at scale.
6. [Kelsey Hightower's "Kubernetes The Hard Way"](https://github.com/kelseyhightower/kubernetes-the-hard-way) — build a cluster from scratch. Nothing teaches the architecture faster.

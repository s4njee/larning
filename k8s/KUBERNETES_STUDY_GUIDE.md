# Kubernetes Mastery Study Guide

A depth-first guide to mastering Kubernetes as an operator and platform engineer. Assumes you already know basic container concepts (`docker run`, images, registries) and have used `kubectl` at least once. Each phase builds on the previous. Deep networking lives in the sibling [Docker & Kubernetes Networking](DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md) guide; production hardening lives in [Kubernetes Security](KUBERNETES_SECURITY_STUDY_GUIDE.md). This guide focuses on the core API, workloads, scheduling, and day-2 operations.

The goal is practical fluency: you should be able to read a manifest, predict which controller owns it, explain how traffic reaches it, debug it when it fails, and make conservative production choices without needing a platform team to rescue every deploy.

---

## Table of Contents

1. [Phase 1: Core Foundations](#phase-1-core-foundations)
2. [Phase 2: Workloads](#phase-2-workloads)
3. [Phase 3: Configuration & State](#phase-3-configuration--state)
4. [Phase 4: Services & Discovery](#phase-4-services--discovery)
5. [Phase 5: Scheduling & Resource Management](#phase-5-scheduling--resource-management)
6. [Phase 6: Operations & Debugging](#phase-6-operations--debugging)
7. [Phase 7: API Access, Policy & Packaging](#phase-7-api-access-policy--packaging)
8. [Phase 8: Observability](#phase-8-observability)
9. [Phase 9: Production Patterns & Pitfalls](#phase-9-production-patterns--pitfalls)
10. [Phase 10: Ecosystem & Tooling](#phase-10-ecosystem--tooling)
11. [Hands-On Labs](#hands-on-labs)
12. [Mastery Checklist](#mastery-checklist)
13. [Recommended Reading Path](#recommended-reading-path)

---

## Phase 1: Core Foundations

Kubernetes is easiest to learn when you stop thinking of it as "a place containers run" and start thinking of it as **an API plus a fleet of controllers**. You write desired state to the API. Controllers watch that state and keep trying to make the real world match it.

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

### 1.3 Ownership, Labels, and Selectors

Most Kubernetes behavior is driven by *relationships between objects*, not by hidden state. Learn the relationship fields early.

- **Labels** are queryable identity. They are how Services find Pods, ReplicaSets find Pods, and humans filter objects. Use a consistent label set:
  - `app.kubernetes.io/name`: app name, e.g. `payments-api`
  - `app.kubernetes.io/component`: role, e.g. `api`, `worker`, `db`
  - `app.kubernetes.io/instance`: install/release name, e.g. `payments-prod`
  - `app.kubernetes.io/version`: app version, e.g. `1.7.3`
- **Selectors** are contracts. A Deployment's selector tells it which Pods it owns. A Service's selector tells it which Pods receive traffic. Be careful: many selectors are immutable after creation because changing them can orphan or steal objects.
- **Annotations** are non-query metadata. Controllers use them for options, checksums, external IDs, or tool-specific data. Humans use them for descriptions and runbook links.
- **Owner references** connect parent and child objects. A Deployment owns ReplicaSets; ReplicaSets own Pods. Garbage collection follows this tree. `kubectl tree deploy/foo` from `krew` makes this visible.
- **Finalizers** are cleanup hooks. If an object is stuck in `Terminating`, a finalizer is often waiting for a controller to clean up external resources before deletion completes.

```bash
# see the ownership chain from a pod back to its deployment
kubectl get pod <pod> -o jsonpath='{.metadata.ownerReferences}'

# list pods selected by a service
kubectl get svc web -o jsonpath='{.spec.selector}'
kubectl get pods -l app=web
```

**Practice**: Create a Deployment and a Service with the same `app` label. Change a Pod label manually and watch it disappear from the Service endpoints. Then delete the Pod and watch the ReplicaSet recreate one with the correct labels.

---

### 1.4 Namespaces

- A namespace is a scope for resource *names* and a target for RBAC and resource quotas. It is **not** a security boundary by itself — pods in different namespaces share the same node, kernel, and network unless you add policy.
- Cluster-scoped resources (Nodes, PersistentVolumes, ClusterRoles, CRDs) have no namespace. Namespaced resources (Pods, Services, ConfigMaps, Deployments) do.
- Default namespaces: `default`, `kube-system` (control-plane addons), `kube-public` (world-readable cluster info), `kube-node-lease` (node heartbeats).
- Cross-namespace DNS: `<service>.<namespace>.svc.cluster.local`. Within a namespace you can use just `<service>`.
- References: [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)

---

### 1.5 kubectl Mastery

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
- **Server-side apply**: `kubectl apply --server-side --field-manager=<name>` lets the API server track field ownership. This matters when multiple tools manage the same object.
- **Explain everything**: `kubectl explain` is your built-in schema browser. `kubectl explain deployment.spec.strategy.rollingUpdate` is faster than searching docs mid-incident.
- **Plugins via `krew`**: `kubectl krew install ctx ns neat tree access-matrix`. `kubectl neat` strips server-side junk from YAML; `tree` shows owner-reference graphs.
- References: [kubectl cheatsheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/), [JSONPath](https://kubernetes.io/docs/reference/kubectl/jsonpath/)

**Practice**: Build a one-liner that lists every container image running in the cluster, with counts, sorted. Hint: `kubectl get pods -A -o jsonpath=...` piped through `sort | uniq -c | sort -rn`.

### 1.6 Local Practice Environments

You need a disposable cluster you can break on purpose.

- **kind**: Kubernetes-in-Docker. Fast, scriptable, excellent for controller tests and CI. Best default for study.
- **minikube**: more featureful local cluster with drivers for Docker, HyperKit, VirtualBox, etc. Great for trying addons.
- **k3d**: runs k3s inside Docker. Tiny, fast, friendly for local multi-node experiments.
- **Killercoda / Play with Kubernetes**: browser labs when you do not want to install anything.

Good practice loop:

```bash
kind create cluster --name k8s-study
kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -A
kind delete cluster --name k8s-study
```

---

## Phase 2: Workloads

Workloads are the Kubernetes objects that create and manage Pods. The first decision is almost always "which controller owns this Pod?"

| Need | Use | Why |
|---|---|---|
| Stateless web/API/worker service | Deployment | Rolling updates, rollbacks, replica management |
| Stable identity and per-replica storage | StatefulSet | Predictable names, ordered rollout, PVC templates |
| One node-level agent per node | DaemonSet | Scheduler maintains coverage across eligible nodes |
| Batch task that must finish | Job | Completion tracking, retries, parallelism |
| Scheduled batch task | CronJob | Cron semantics plus Job history and concurrency policy |
| Single throwaway debug container | Pod | Useful for tests; rarely a production object |

### 2.1 Pods

The atomic unit of scheduling. Not the atomic unit of *deployment* — you almost never create bare Pods in production.

- **One pod, many containers, one network/IPC namespace**. Containers in a pod share a Linux network namespace (same `localhost`, same IP) and can share volumes. They do *not* share PID or filesystem namespaces by default.
- **`pause` container**: every pod has an invisible infra container that holds the namespaces open. When you `docker ps` on a node and see `pause` containers, that's why.
- **Init containers** run sequentially before app containers. Used for setup work (waiting for a dependency, fetching config, running migrations). Failure of any init container restarts the pod.
- **Sidecar containers**: native sidecar lifecycle uses `restartPolicy: Always` on an init container. The feature is stable in Kubernetes v1.33 and has been active by default since v1.29. Use this when startup/shutdown ordering matters (e.g., log shipper, service mesh proxy).
- **Probes** — the kubelet uses these to manage container state.
  - `livenessProbe`: kubelet restarts the container if it fails. Use for *deadlock* detection only. Aggressive liveness is a top cause of cascading outages.
  - `readinessProbe`: kubelet removes the pod from Service endpoints if it fails. Use this liberally — it's how rolling deploys stay healthy.
  - `startupProbe`: gives slow-starting apps room before liveness kicks in. Disables liveness until startup succeeds.
  - Mechanisms: `httpGet`, `tcpSocket`, `exec`, `grpc` (1.27+).
- **Pod lifecycle phases**: `Pending` → `Running` → `Succeeded` / `Failed`. `Unknown` means the kubelet hasn't reported recently.
- **`terminationGracePeriodSeconds`** — default 30s. On delete, kubelet sends SIGTERM, waits this long, then SIGKILL. Tune for apps with long in-flight work.
- **`preStop` hook** — runs *before* SIGTERM. Used to drain connections, deregister from external systems, or `sleep` to let load balancers notice. A `sleep 10` `preStop` is a common fix for "requests fail during deploys."
- References: [Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), [Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [Sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)

---

### 2.2 Pod Template Anatomy

Deployments, StatefulSets, DaemonSets, Jobs, and CronJobs all contain a **Pod template** at `spec.template`. If a field is under `spec.template`, changing it usually creates replacement Pods. If a field is outside the template, it usually changes controller behavior without replacing current Pods.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app.kubernetes.io/name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: web
  template:
    metadata:
      labels:
        app.kubernetes.io/name: web
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: web
          image: ghcr.io/example/web:1.2.3
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              memory: 256Mi
          startupProbe:
            httpGet:
              path: /healthz
              port: 8080
            failureThreshold: 30
            periodSeconds: 2
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8080
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 30
```

What to notice:

- `metadata.labels` on the Deployment and `spec.template.metadata.labels` on Pods are different fields. Services select the Pod labels.
- `spec.selector.matchLabels` must match the template labels and is effectively permanent.
- `resources.requests` are for scheduling; `resources.limits` are for runtime enforcement.
- Probes hit container ports, not Service ports.
- Changing `image`, `resources`, probes, labels, or env under `spec.template` triggers a rollout.

---

### 2.3 ReplicaSets and Deployments

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

Deployment commands you should be able to use without thinking:

```bash
kubectl rollout status deploy/web
kubectl rollout history deploy/web
kubectl set image deploy/web web=ghcr.io/example/web:1.2.4
kubectl rollout undo deploy/web
kubectl scale deploy/web --replicas=5
kubectl rollout restart deploy/web
```

**Rollout checklist**:

- Set `readinessProbe` before relying on zero-downtime deploys.
- Keep at least 2 replicas for services that receive traffic.
- Use `maxUnavailable: 0` for strict availability; combine with enough capacity for `maxSurge`.
- Make database migrations backward-compatible before deploying app code that depends on them.
- Watch both `kubectl rollout status` and `kubectl get pods -w`; a rollout can be "progressing" while individual Pods are crash-looping.

---

### 2.4 StatefulSets

For workloads that need *stable identity*: databases, message brokers, anything caching state on disk.

- Pods get **predictable names**: `web-0`, `web-1`, `web-2`. Ordinal index matters — `-0` always comes up first, scale-down deletes the highest ordinal first.
- Each pod gets its own **PersistentVolumeClaim** via `volumeClaimTemplates`. PVCs survive pod deletion and are reattached when the pod is rescheduled.
- A **headless Service** (`clusterIP: None`) gives each pod a stable DNS name: `web-0.web.default.svc.cluster.local`. This is the magic that lets `web-1` find `web-0` reliably.
- **Update strategies**: `RollingUpdate` (default, in reverse ordinal order) and `OnDelete` (you trigger updates by deleting pods). `partition` lets you canary by ordinal.
- StatefulSets do **not** delete PVCs by default when you delete the StatefulSet. This is a feature; it's also a foot-gun. `persistentVolumeClaimRetentionPolicy` (1.27+) gives you control.
- References: [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

Use StatefulSets carefully:

- Kubernetes gives you identity and storage attachment; it does **not** magically make a database highly available.
- Prefer a mature operator for complex databases (Postgres, MySQL, Kafka, Elasticsearch) unless your needs are simple and you understand failover.
- Budget time to test restore, replica replacement, zone loss, and volume resize. Stateful workloads punish "we will figure that out later."

---

### 2.5 DaemonSets, Jobs, CronJobs

- **DaemonSet**: one pod per node (filtered by selectors/taints). Used for node-level agents: log shippers, monitoring, CNI/CSI plugins, security agents.
  - `updateStrategy: RollingUpdate` with `maxUnavailable` controls how many nodes are disrupted at once.
- **Job**: runs pods to completion. `completions` (how many successful pods needed), `parallelism` (max concurrent), `backoffLimit` (retries before failure), `activeDeadlineSeconds` (timeout).
  - Modes: non-indexed (default), `Indexed` (each pod gets a `JOB_COMPLETION_INDEX` env var — great for parallel data processing).
- **CronJob**: runs a Job on a cron schedule. `concurrencyPolicy: Allow|Forbid|Replace` controls overlapping runs. `startingDeadlineSeconds` bounds how late a missed run can fire. `successfulJobsHistoryLimit` and `failedJobsHistoryLimit` prevent unbounded Job buildup — a classic operational footgun.
- References: [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)

CronJob example worth memorizing:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-report
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 900
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: report
              image: ghcr.io/example/report:1.0.0
```

Use `concurrencyPolicy: Forbid` for jobs that should not overlap, and `Replace` only when killing the previous run is explicitly safe.

---

## Phase 3: Configuration & State

Kubernetes separates application code, configuration, secrets, and storage. That separation is powerful, but it also creates deployment edge cases: environment variables do not update live, volume-mounted config does, and persistent disks outlive Pods.

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

ConfigMap + Secret usage pattern:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
data:
  LOG_LEVEL: info
  FEATURE_FLAGS: "checkout-v2,retry-worker"
---
apiVersion: v1
kind: Secret
metadata:
  name: web-secrets
type: Opaque
stringData:
  DATABASE_URL: postgres://user:pass@postgres.default.svc.cluster.local:5432/app
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  template:
    spec:
      containers:
        - name: web
          image: ghcr.io/example/web:1.2.3
          env:
            - name: LOG_LEVEL
              valueFrom:
                configMapKeyRef:
                  name: web-config
                  key: LOG_LEVEL
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: web-secrets
                  key: DATABASE_URL
```

Operational implications:

- If config is consumed as env vars, changing the ConfigMap or Secret does not change running containers. Trigger a rollout (`kubectl rollout restart deploy/web`) or use a tool that hashes config into the Pod template.
- If config is mounted as files, kubelet refreshes the mounted data eventually, but your app must reload it. Many apps still need a restart.
- Do not store large files in ConfigMaps or Secrets. Use object storage, container images, or volumes.
- Do not put real credentials in Git just because the object is called `Secret`. Use sealed secrets, external secret operators, or a secrets manager workflow.

### 3.1.1 The Config Change Rollout Pattern

The common production trick is to put a checksum annotation on the Pod template. Any change to config changes the template, which triggers a Deployment rollout:

```yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: "sha256-of-rendered-config"
```

Helm charts often compute this with a template function; Kustomize users often generate ConfigMaps with content-hash suffixes. The point is the same: make the Pod template change when the config it depends on changes.

### 3.2 Persistent Storage

- **PersistentVolume (PV)**: a piece of storage in the cluster (NFS export, EBS volume, Ceph RBD, etc.). Cluster-scoped.
- **PersistentVolumeClaim (PVC)**: a namespaced request for storage. Binds 1:1 to a PV.
- **StorageClass**: dynamic provisioning. A PVC referencing a StorageClass triggers the CSI driver to create a PV on demand. This is what you'll use 99% of the time — static PVs are mostly legacy.
- **Access modes**: `ReadWriteOnce` (RWO — mounted read-write by one node), `ReadOnlyMany` (ROX — mounted read-only by many nodes), `ReadWriteMany` (RWX — mounted read-write by many nodes), `ReadWriteOncePod` (RWOP — mounted read-write by one Pod; stable in v1.29 for CSI volumes). Most block storage is RWO; file storage (NFS, EFS) is RWX.
- **Reclaim policy**: `Delete` (PV deleted when PVC deleted — destructive!) vs. `Retain` (PV kept, manual cleanup). StorageClass defaults to `Delete`; override for anything you care about.
- **Volume expansion**: `allowVolumeExpansion: true` on the StorageClass + edit the PVC's `spec.resources.requests.storage`. Shrinking is not supported.
- **CSI**: the [Container Storage Interface](https://kubernetes-csi.github.io/docs/) — the plugin protocol all modern storage drivers speak. Out-of-tree, so storage updates don't require a Kubernetes upgrade.
- References: [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)

PVC example:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 20Gi
```

Attach it to a Pod:

```yaml
spec:
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: app-data
  containers:
    - name: app
      image: ghcr.io/example/app:1.0.0
      volumeMounts:
        - name: data
          mountPath: /var/lib/app
```

Storage questions to ask before production:

- Is the volume zonal or regional? A zonal disk can pin the Pod to one zone.
- What happens if the node dies while the volume is attached?
- How are snapshots taken, retained, and restored?
- Does the app tolerate being restarted on a different node with the same disk?
- Is the reclaim policy safe for the environment?

### 3.3 Other Volume Types

- `emptyDir` — scratch space tied to the pod's lifetime. Use `medium: Memory` for a tmpfs ramdisk.
- `hostPath` — mounts a path from the node. Avoid in app workloads (breaks portability, security risk); fine for node-level agents.
- `projected` — combine multiple sources (ConfigMaps, Secrets, downwardAPI, service account tokens) into one mount point. The mechanism behind modern service account token projection.
- `downwardAPI` — exposes pod/container metadata (labels, annotations, resource limits) as files or env vars.

### 3.4 Backups and Data Lifecycle

Kubernetes can attach storage, but it does not automatically give you an application-consistent backup strategy.

- **Stateless workloads**: back up source code, manifests, config, and external databases. Pods are disposable.
- **Stateful workloads**: back up the data store using its own native mechanism first (Postgres base backups + WAL, MySQL binlogs, etc.). CSI snapshots are useful, but app-level consistency still matters.
- **Cluster state**: for self-managed clusters, back up etcd. For managed clusters, understand the provider's control-plane backup and disaster-recovery model.
- **Manifests**: GitOps repositories are not full backups, but they make cluster rebuilds possible because desired state is recoverable.
- **Restore testing**: a backup that has never been restored is a hopeful artifact, not a recovery plan.

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

Service manifest:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: web
  ports:
    - name: http
      port: 80        # Service port
      targetPort: 8080 # container port or named port
```

Traffic path for a normal in-cluster request:

```text
client Pod
  -> DNS lookup for web.default.svc.cluster.local
  -> Service virtual IP
  -> kube-proxy / eBPF load-balancing rule
  -> one ready Pod endpoint
  -> containerPort 8080
```

Debug order:

```bash
kubectl get svc web -o wide
kubectl get endpointslices -l kubernetes.io/service-name=web
kubectl get pods -l app.kubernetes.io/name=web -o wide
kubectl describe svc web
```

If the Service has no endpoints, the selector probably does not match any ready Pods, or readiness probes are failing.

### 4.2 DNS

- **CoreDNS** is the cluster DNS server. Configured via the `coredns` ConfigMap in `kube-system`.
- Service DNS: `<service>.<namespace>.svc.cluster.local`. Same namespace: `<service>` suffices. The `search` path in `/etc/resolv.conf` makes both work.
- Pod DNS: `<pod-ip-with-dashes>.<namespace>.pod.cluster.local`. Rarely useful.
- **`ndots:5`** — by default, `resolv.conf` has `ndots: 5`, which causes any name with fewer than 5 dots to be tried against the search path *first*. This is why external DNS lookups from pods can be slow (5 misses before the real query). Set `dnsConfig` on chatty pods if it matters.

DNS debugging:

```bash
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- nslookup web.default.svc.cluster.local
kubectl get configmap coredns -n kube-system -o yaml
kubectl logs -n kube-system deploy/coredns
```

### 4.3 Ingress and Gateway API

- **Ingress** — L7 HTTP routing. Requires an Ingress *controller* (nginx-ingress, Traefik, HAProxy, AWS ALB, GCP GLB) to be running; the Ingress resource itself is just config.
- **`IngressClass`** — tells the cluster *which* controller should service a given Ingress.
- **Gateway API** is the modern successor: better separation between platform and app teams (`GatewayClass` / `Gateway` owned by ops, `HTTPRoute` / `GRPCRoute` / `TLSRoute` owned by app teams), explicit support for L4 + L7, and a clean protocol-aware model. New work should target Gateway API where the controller supports it.
- References: [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Gateway API](https://gateway-api.sigs.k8s.io/)

Ingress example:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
spec:
  ingressClassName: nginx
  rules:
    - host: web.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
```

Know the boundary:

- A Service is L4 load balancing to Pods.
- Ingress is L7 HTTP routing to Services.
- Gateway API models shared infrastructure more explicitly than Ingress.
- TLS certificates usually come from cert-manager, a cloud load balancer integration, or a platform team's certificate workflow.
- External DNS records are usually managed by ExternalDNS, Terraform, or cloud-native DNS automation.

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

Resource example:

```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
    ephemeral-storage: 1Gi
  limits:
    memory: 512Mi
    ephemeral-storage: 2Gi
```

How to choose starting values:

- Start with measured usage from a real environment, not guesses from local dev.
- Set memory requests close to steady-state usage and memory limits above expected peaks.
- Be careful with CPU limits for latency-sensitive services; CPU requests are usually more important for scheduling.
- Revisit requests after production traffic. Bad requests create bad scheduling decisions forever.

### 5.2 Scheduling Constraints

- **`nodeSelector`** — simplest form: pod runs only on nodes with matching labels.
- **Node affinity / anti-affinity** — richer expressions. `requiredDuringSchedulingIgnoredDuringExecution` (hard, only at schedule time) vs. `preferredDuringScheduling...` (soft, weighted).
- **Pod affinity / anti-affinity** — schedule based on what *other pods* are running. Classic use: spread replicas across zones (`topologyKey: topology.kubernetes.io/zone` with anti-affinity).
- **Taints and tolerations** — *taints* repel pods from a node; *tolerations* on a pod let it tolerate matching taints. Effects: `NoSchedule`, `PreferNoSchedule`, `NoExecute`. Used for dedicated nodes (e.g., GPU pools), control-plane isolation, and node draining.
- **Topology spread constraints** — declarative "spread me across these topology domains" with `maxSkew`. Cleaner than pod anti-affinity for most spread cases.
- **PriorityClasses** — when the cluster is full, higher-priority pods can preempt (evict) lower-priority pods. `system-cluster-critical` and `system-node-critical` are reserved for control-plane workloads.
- References: [Assigning pods to nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/), [Taints and tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)

Topology spread example:

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: web
```

This says: keep matching Pods spread evenly across zones, with no zone having more than one extra Pod compared to another. For most stateless services, this is clearer than pod anti-affinity.

Taint/toleration pattern:

```bash
kubectl taint nodes node-1 workload=gpu:NoSchedule
```

```yaml
tolerations:
  - key: workload
    operator: Equal
    value: gpu
    effect: NoSchedule
nodeSelector:
  workload: gpu
```

The taint keeps random Pods away; the selector intentionally targets the node pool. Use both for dedicated pools.

### 5.3 Autoscaling

- **Horizontal Pod Autoscaler (HPA)** — scales replica count based on metrics. CPU and memory out of the box; custom and external metrics via the metrics adapter API. Needs `metrics-server` installed.
- **Vertical Pod Autoscaler (VPA)** — adjusts requests/limits based on observed usage. Three modes: `Off` (recommendations only), `Auto` (recreates pods with new values), `Initial` (only sets at create time). Don't use HPA and VPA on the same resource (they fight) unless you use VPA in `Off` mode for recommendations only.
- **Cluster Autoscaler** — adds/removes nodes from the node group when pods can't be scheduled / nodes are idle. Cloud-provider-specific.
- **Karpenter** (AWS-born, now multi-cloud) — modern replacement for Cluster Autoscaler. Provisions right-sized nodes on demand instead of scaling fixed node groups. Significantly faster and cheaper.
- References: [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/), [Karpenter](https://karpenter.sh/)

HPA example:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

HPA pitfalls:

- CPU utilization is relative to CPU **requests**. If requests are wrong, scaling is wrong.
- HPA reacts after metrics arrive; it is not instant. Keep enough baseline replicas for sudden bursts.
- Scale-down should be conservative for services with connection churn or cold caches.
- Custom metrics are powerful, but the metrics pipeline becomes part of your availability story.

### 5.4 Namespace Resource Governance

Resource governance keeps one team, app, or runaway job from consuming the whole cluster.

- **ResourceQuota** caps aggregate namespace usage: total CPU, memory, PVC count, storage, object counts.
- **LimitRange** sets defaults and per-object min/max rules when teams forget requests/limits.
- **PriorityClass** tells the scheduler which Pods matter more under pressure.
- **PodDisruptionBudget** protects availability during voluntary disruptions like node drains.

Example quota:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.memory: 80Gi
    persistentvolumeclaims: "20"
```

Example LimitRange:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
spec:
  limits:
    - type: Container
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      default:
        memory: 256Mi
```

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

First diagnostic habit: read Events before guessing.

```bash
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp -n <namespace>
kubectl get events --field-selector involvedObject.name=<pod> -n <namespace>
```

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

Debugging flow:

```text
1. What object is unhealthy?        kubectl get deploy,rs,pod,svc,ingress
2. What does Kubernetes say?        kubectl describe ...
3. What did the container say?      kubectl logs ... --previous
4. Can it be scheduled?             events, node conditions, PVC status
5. Can it receive traffic?          readiness, Service selector, EndpointSlices
6. Is it allowed to act?            service account, RBAC, admission errors
7. Is the node healthy?             kubectl describe node, kubelet logs, crictl
```

### 6.3 Node Operations

- **Drain a node** before maintenance: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`. This cordons the node (no new pods) and evicts existing pods, respecting PodDisruptionBudgets.
- **Cordon / uncordon** — `kubectl cordon` marks unschedulable without evicting; `uncordon` reverses.
- **PodDisruptionBudgets (PDBs)** — declare minimum availability (`minAvailable: 2` or `maxUnavailable: 1`). The eviction API blocks `drain` from violating PDBs. Every production workload should have one.

PDB example:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: web
```

Drain checklist:

- Verify the node is not the only place a critical singleton can run.
- Check PDBs before the maintenance window: `kubectl get pdb -A`.
- Drain one node at a time unless you have modeled zone and capacity impact.
- Remember that DaemonSet Pods are ignored by default; node agents must tolerate maintenance.

### 6.4 Incident Walkthroughs

**A Pod is stuck Pending**

```bash
kubectl describe pod <pod>
kubectl get pvc -n <namespace>
kubectl describe node <candidate-node>
kubectl get nodes --show-labels
```

Common interpretations:

- `0/6 nodes are available: insufficient cpu` means requests cannot fit. Lower requests, scale nodes, or free capacity.
- `had untolerated taint` means the Pod needs a matching toleration or should not target that node pool.
- `pod has unbound immediate PersistentVolumeClaims` means storage provisioning or binding is blocking scheduling.
- `node(s) didn't match Pod's node affinity/selector` means labels and selectors disagree.

**A Deployment rollout is stuck**

```bash
kubectl rollout status deploy/web
kubectl get rs -l app.kubernetes.io/name=web
kubectl get pods -l app.kubernetes.io/name=web
kubectl describe pod <new-pod>
kubectl logs <new-pod> --previous
```

Likely causes:

- New Pods fail readiness, so old Pods cannot be scaled down.
- New image cannot be pulled.
- New Pods cannot schedule because `maxSurge` needs extra capacity.
- App starts but exits because config or secrets changed incorrectly.

**A Service returns connection failures**

```bash
kubectl get svc web -o yaml
kubectl get endpointslices -l kubernetes.io/service-name=web
kubectl get pods -l app.kubernetes.io/name=web
kubectl port-forward svc/web 8080:80
```

Likely causes:

- Service selector does not match Pod labels.
- Pods are not ready, so they are intentionally removed from endpoints.
- `targetPort` does not match the container port or named port.
- NetworkPolicy, mesh policy, or cloud firewall is blocking traffic.

---

## Phase 7: API Access, Policy & Packaging

Kubernetes is an API, so "who can call the API, with which verbs, against which resources" is part of basic operational literacy. The security guide goes deep; this phase covers the working model you need for day-to-day use.

### 7.1 Service Accounts and RBAC Basics

- **Users** are usually external identities from OIDC, certificates, cloud IAM, or an auth proxy. Kubernetes does not have a built-in `User` object.
- **ServiceAccounts** are Kubernetes identities for workloads. Pods use them to call the API.
- **Roles** grant verbs on resources inside one namespace.
- **ClusterRoles** grant cluster-scoped permissions or reusable namespaced permission sets.
- **RoleBindings** attach a Role or ClusterRole to users, groups, or service accounts inside a namespace.
- **ClusterRoleBindings** attach a ClusterRole cluster-wide. Treat them carefully.
- **Verbs** are API operations: `get`, `list`, `watch`, `create`, `update`, `patch`, `delete`.

Minimal service-account permission:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: deployment-reader
  namespace: apps
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: read-deployments
  namespace: apps
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deployment-reader
  namespace: apps
subjects:
  - kind: ServiceAccount
    name: deployment-reader
    namespace: apps
roleRef:
  kind: Role
  name: read-deployments
  apiGroup: rbac.authorization.k8s.io
```

RBAC debugging:

```bash
kubectl auth can-i list deployments -n apps --as=system:serviceaccount:apps:deployment-reader
kubectl auth can-i '*' '*' --all-namespaces
kubectl get role,rolebinding -n apps
kubectl get clusterrolebinding
```

Rule of thumb: grant the smallest namespace-scoped Role that works. Reach for ClusterRoleBinding only when the actor truly needs cluster-wide authority.

### 7.2 Custom Resources & Operators

- **CustomResourceDefinitions (CRDs)** — let you add new API types. The cluster gains `kubectl get <yourkind>` for free.
- **OpenAPI v3 schemas** on CRDs give validation, defaulting, and `kubectl explain` for your types. Always define one.
- **Controllers / Operators** — code that watches CRD instances and reconciles them against the world. The Kubernetes way to automate any stateful application.
- **Frameworks**: [`controller-runtime`](https://book.kubebuilder.io/) (Go, the standard), [`kopf`](https://kopf.readthedocs.io/) (Python), [`metacontroller`](https://metacontroller.github.io/metacontroller/) (declarative hooks). Start with Kubebuilder for Go.
- **Operator pattern**: capture human operator knowledge as a controller. Examples: cert-manager, Prometheus Operator, etcd-operator, Crossplane.
- References: [CRDs](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/), [Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)

What to remember as a beginner: a CRD gives you storage and validation; a controller gives the CRD behavior. Installing a CRD without its controller often leaves inert custom objects sitting in etcd.

### 7.3 Admission Control

- Requests to the API server pass through: authentication → authorization → admission → schema validation → storage.
- **Built-in admission plugins**: `NamespaceLifecycle`, `LimitRanger`, `ResourceQuota`, `PodSecurity`, etc.
- **Validating webhooks** — reject requests that don't meet policy.
- **Mutating webhooks** — modify the request (inject sidecars, defaults, labels). Order matters; mutators run before validators.
- **Policy engines**: [Kyverno](https://kyverno.io/) (CRD-driven, no DSL), [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/) (Rego). Modern clusters use one or the other to enforce org policy.
- References: [Admission controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)

Admission failures usually show up at `kubectl apply` time:

```text
Error from server (Forbidden): admission webhook "..." denied the request
```

Read these messages closely. They often tell you the exact missing label, disallowed security setting, or policy violation.

### 7.4 Packaging

- **Helm** — templating + release lifecycle. Charts are tar.gz of YAML templates + `values.yaml`. Production-grade once you understand it; library charts and subcharts can get ugly.
- **Kustomize** — overlay-based, no templating, built into `kubectl` (`kubectl apply -k`). Bases + overlays per environment. Often the right choice for in-house apps.
- **Helm vs. Kustomize**: not mutually exclusive. Common pattern: install vendor stuff via Helm, manage in-house apps via Kustomize. Or render Helm to YAML and post-process with Kustomize.
- References: [Helm](https://helm.sh/docs/), [Kustomize](https://kustomize.io/)

Packaging decision:

- Use **plain YAML** for learning and very small systems.
- Use **Kustomize** when you have one app with environment overlays and want minimal magic.
- Use **Helm** when you need reusable packaging, values, hooks, dependencies, or a vendor-supported install path.
- Use **GitOps** to continuously reconcile the rendered result into clusters.

Always inspect rendered YAML:

```bash
helm template web ./chart -f values-prod.yaml
kubectl kustomize overlays/prod
kubectl diff -f rendered.yaml
```

---

## Phase 8: Observability

Kubernetes gives you a lot of status, but it does not give you durable observability by default. `kubectl` is for live debugging; production needs metrics, logs, traces, and retained events.

### 8.1 Metrics

- **Metrics**:
  - `metrics-server` — basic pod/node CPU and memory for HPA and `kubectl top`. Not for long-term storage.
  - **Prometheus** + `kube-state-metrics` — the standard. `kube-state-metrics` exposes cluster object state (deployment replica counts, pod phases, etc.); node-exporter exposes node-level metrics; Prometheus scrapes both.
  - **OpenTelemetry Collector** — increasingly the right answer for metrics + traces + logs in one pipeline.
- References: [Logging architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/), [Prometheus Operator](https://prometheus-operator.dev/)

Minimum cluster metrics to know:

- Node CPU, memory, disk, and network saturation.
- Pod restarts, OOM kills, evictions, and pending Pods.
- Deployment desired/available replicas.
- API server request rate, error rate, latency, and inflight requests.
- etcd latency and database size for self-managed clusters.
- HPA desired vs. current replicas and metric availability.

Useful live commands:

```bash
kubectl top nodes
kubectl top pods -A --containers
kubectl get deploy -A
kubectl get hpa -A
```

### 8.2 Logs

Containers write to stdout/stderr; the kubelet writes those streams to files on the node. A node agent (Fluent Bit, Vector, Promtail, cloud logging agent) ships them to a log store. Do **not** rely on `kubectl logs` for anything other than live debugging — kubelet rotation drops history.

Production logging basics:

- Emit structured JSON logs from applications.
- Include request IDs, trace IDs, user/account IDs where appropriate, and error codes.
- Avoid high-cardinality or sensitive fields by default.
- Make log retention explicit; otherwise cost and compliance surprises arrive together.
- Test multiline stack traces in your log pipeline.

### 8.3 Traces and Service-Level Signals

Traces answer "where did this request spend time?" Instrument apps with OpenTelemetry and ship to Tempo, Jaeger, Honeycomb, Datadog, or another backend. Service mesh sidecars can provide some traffic-level spans automatically, but application instrumentation still gives the best business context.

For a service, dashboard the four golden signals:

- **Latency**: p50, p90, p99 by route or operation.
- **Traffic**: request rate, queue depth, worker throughput.
- **Errors**: 5xx rate, failed jobs, retry exhaustion.
- **Saturation**: CPU, memory, connection pools, thread pools, queue lag.

### 8.4 Events

`kubectl get events` is your built-in event log. Events explain scheduling failures, image pulls, probe failures, evictions, and volume attach problems. They expire quickly, so production clusters should export them with something like [`kubernetes-event-exporter`](https://github.com/resmoio/kubernetes-event-exporter) or a logging pipeline.

```bash
kubectl events -A --watch
kubectl get events -A --sort-by=.lastTimestamp
```

Events are not application logs. They are cluster control-plane breadcrumbs.

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

### 9.1 The Production Deployment Minimum

For a normal stateless HTTP service, a production-ready baseline usually includes:

- Deployment with at least 2 replicas.
- Service with a stable selector.
- Ingress or HTTPRoute if it receives external traffic.
- Readiness probe, startup probe if boot is slow, conservative liveness probe only if useful.
- CPU and memory requests; memory limit; ephemeral-storage limit if logs/temp files can grow.
- Topology spread across zones or nodes.
- PodDisruptionBudget.
- ConfigMap/Secret references with a rollout strategy for config changes.
- ServiceAccount with only required permissions.
- Logs shipped off-node and metrics scraped.
- Image pinned by immutable tag or digest.

### 9.2 Safe Rollout Mindset

Kubernetes gives you mechanics, not release safety. You still need compatibility discipline:

- **Backward-compatible database changes first**: add columns/tables before code depends on them; remove later.
- **Two-version compatibility**: during a rolling update, old and new Pods run together.
- **Graceful shutdown**: handle SIGTERM, stop accepting new work, finish in-flight work, then exit.
- **Idempotent startup**: multiple replicas may start together; migrations and boot tasks must tolerate retries.
- **Fast rollback**: know whether `kubectl rollout undo` is actually safe after schema/config changes.

### 9.3 Common Manifest Smells

- No `resources.requests`.
- `replicas: 1` for a user-facing service.
- A Service selector that is broader than the Deployment's labels.
- `latest` image tags or mutable tags in production.
- Secrets committed as plain YAML.
- Liveness and readiness probes hitting the same expensive dependency.
- `hostPath`, `hostNetwork`, `privileged`, or broad ClusterRoleBinding in app namespaces.
- StatefulSet used as a database strategy without tested backups and failover.
- CronJobs with no history limits or concurrency policy.
- Ingress without explicit `ingressClassName`.

---

## Phase 10: Ecosystem & Tooling

- **CLI quality of life**: [`k9s`](https://k9scli.io/) (TUI), [`stern`](https://github.com/stern/stern) (multi-pod log tailing), [`kubectx`/`kubens`](https://github.com/ahmetb/kubectx), [`kube-ps1`](https://github.com/jonmosco/kube-ps1) (shell prompt), [`kubectl-tree`](https://github.com/ahmetb/kubectl-tree), [`kubeshark`](https://kubeshark.co/) (cluster-wide traffic capture).
- **GitOps**: [Argo CD](https://argo-cd.readthedocs.io/) and [Flux](https://fluxcd.io/) — declarative cluster state from a Git repo. Pull-based deploys. Replaces "kubectl apply from CI" in serious shops.
- **Service mesh**: [Istio](https://istio.io/), [Linkerd](https://linkerd.io/), [Cilium Service Mesh](https://cilium.io/use-cases/service-mesh/). Worth it for mTLS, fine-grained traffic policy, and L7 observability. Operational cost is real — don't add a mesh until you can articulate the specific problem it solves.
- **Local clusters**: [`kind`](https://kind.sigs.k8s.io/) (Docker-in-Docker, fast), [`minikube`](https://minikube.sigs.k8s.io/), [`k3d`](https://k3d.io/) (k3s in Docker — tiny and fast).
- **Distributions worth knowing**: managed (EKS, GKE, AKS), self-hosted (kubeadm, kops), edge/lightweight ([k3s](https://k3s.io/), MicroK8s), bare-metal ([Talos](https://www.talos.dev/) — immutable, API-driven, no SSH).

Tool categories worth recognizing:

| Category | Common tools | What they solve |
|---|---|---|
| Package/install | Helm, Kustomize | Render and organize manifests |
| GitOps | Argo CD, Flux | Continuously reconcile desired state from Git |
| Certificates | cert-manager | Automate TLS certificate issuance/renewal |
| DNS automation | ExternalDNS | Create DNS records from Ingress/Gateway/Service objects |
| Secrets | External Secrets Operator, Sealed Secrets, Vault CSI | Keep real secrets out of plain manifests |
| Policy | Kyverno, OPA Gatekeeper, ValidatingAdmissionPolicy | Enforce cluster rules |
| Autoscaling | HPA, VPA, KEDA, Cluster Autoscaler, Karpenter | Scale Pods and nodes |
| Observability | Prometheus Operator, OpenTelemetry Collector, Loki, Tempo | Metrics, logs, traces |
| Progressive delivery | Argo Rollouts, Flagger | Canary/blue-green releases |
| Backup | Velero, CSI snapshots, database-native tooling | Restore cluster objects and persistent data |

Adoption rule: add ecosystem tools to solve a specific operational problem, not because the CNCF landscape poster made eye contact.

---

## Hands-On Labs

These are intentionally small. Repeat them until the commands feel boring.

### Lab 1: Deploy and Expose a Stateless App

1. Create a namespace.
2. Write a Deployment with 3 replicas, requests/limits, readiness/startup probes, and labels.
3. Write a ClusterIP Service that selects it.
4. Port-forward the Service and make a request.
5. Change the image tag and watch the rollout.
6. Roll back.

Commands to use:

```bash
kubectl create namespace apps
kubectl apply -f deployment.yaml -n apps
kubectl apply -f service.yaml -n apps
kubectl rollout status deploy/web -n apps
kubectl port-forward svc/web 8080:80 -n apps
kubectl rollout undo deploy/web -n apps
```

### Lab 2: Break Scheduling on Purpose

1. Add a fake `nodeSelector` that matches no nodes.
2. Apply the Deployment and watch Pods stay `Pending`.
3. Use `kubectl describe pod` to read the scheduler message.
4. Fix the selector.
5. Add topology spread and verify Pods land across available topology domains if your cluster has labels.

### Lab 3: Debug a Bad Service Selector

1. Deploy an app with label `app=web`.
2. Create a Service with selector `app=api`.
3. Confirm the Service has no endpoints.
4. Fix the selector and watch EndpointSlices populate.

```bash
kubectl get endpointslices -l kubernetes.io/service-name=web
```

### Lab 4: Config Change Behavior

1. Create a ConfigMap and consume it as an environment variable.
2. Change the ConfigMap.
3. Confirm the running Pod does not see the new env value.
4. Restart the rollout.
5. Mount the same ConfigMap as a file and observe how updates appear differently.

### Lab 5: RBAC From Scratch

1. Create a ServiceAccount.
2. Bind it to a Role that can only `get`, `list`, and `watch` Pods.
3. Use `kubectl auth can-i` to verify allowed and denied actions.
4. Try to create a Deployment as that ServiceAccount and confirm it is denied.

### Lab 6: Drain Safety

1. Create a Deployment with 3 replicas and a PDB requiring `minAvailable: 2`.
2. Cordon and drain one node in a multi-node local cluster.
3. Watch evictions and rescheduling.
4. Try a stricter PDB and observe how it blocks disruption.

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

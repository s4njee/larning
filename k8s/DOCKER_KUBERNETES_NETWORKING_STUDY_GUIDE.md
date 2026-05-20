# Docker and Kubernetes Networking Study Guide

A practical, job-focused guide to Docker and Kubernetes networking. The goal is not to memorize every packet path or kernel flag. The goal is to understand the patterns you will actually use on a laptop, in Docker Compose, and in production Kubernetes clusters, then recognize the Kubernetes equivalent when a team moves from "containers on one host" to "workloads across a cluster."

The most important mindset shift in this guide is this: a common Docker networking pattern often maps to multiple Kubernetes objects, not a single one. A published Docker port might become a `Service`, an `Ingress`, a `Gateway`, or a temporary `kubectl port-forward` depending on the job that pattern is doing.

---

## Table of Contents

1. [Phase 1: Core Mental Models](#phase-1-core-mental-models)
2. [Phase 2: Common Docker Patterns and Kubernetes Equivalents](#phase-2-common-docker-patterns-and-kubernetes-equivalents)
3. [Phase 3: Troubleshooting and Practical Labs](#phase-3-troubleshooting-and-practical-labs)
4. [Phase 4: Advanced Kubernetes Networking Patterns](#phase-4-advanced-kubernetes-networking-patterns)

---

## Phase 1: Core Mental Models

### 1.1 What "Container Networking" Actually Means

Official docs: [Docker Engine networking](https://docs.docker.com/engine/network/), [Docker bridge driver](https://docs.docker.com/engine/network/drivers/bridge/), [Kubernetes Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/), [Kubernetes Pods](https://kubernetes.io/docs/concepts/workloads/pods/)

- **Network namespace**: A container usually gets its own isolated view of interfaces, routes, and ports.
  - That is why a process inside a container can listen on port `80` without colliding with another container also listening on `80`.
- **Virtual Ethernet pair (`veth`)**: One end lives in the container namespace, the other connects to a bridge or host-side network.
  - This is the common Linux plumbing that lets container traffic leave the namespace and reach the rest of the system.
- **Bridge**: A virtual switch on the host that connects container interfaces together.
  - In Docker, the bridge model is the default starting point for most local development.
- **NAT / port publishing**: Traffic from a host port is translated and forwarded into a container port.
  - This is the networking behind `docker run -p 8080:80 ...`.
- **DNS-based service discovery**: Instead of hardcoding IPs, containers and Pods usually resolve names to find each other.
  - In real teams, stable names matter much more than memorizing dynamic IPs.
- **Overlay or cluster networking**: Multiple hosts need a shared routing model so workloads can talk across nodes.
  - Docker Swarm overlay networks and Kubernetes pod networking solve this at a higher level than a single Linux bridge.

**Practical picture**

```text
Docker published port:
browser -> host:8080 -> Docker NAT -> container:80

Kubernetes cluster path:
client -> LoadBalancer / Ingress / Gateway -> Service -> Pod IP -> containerPort
```

### 1.2 Docker Networking in Real Life

Official docs: [Docker Engine networking](https://docs.docker.com/engine/network/), [Port publishing and mapping](https://docs.docker.com/engine/network/port-publishing/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Host driver](https://docs.docker.com/engine/network/drivers/host/), [Macvlan driver](https://docs.docker.com/engine/network/drivers/macvlan/), [IPvlan driver](https://docs.docker.com/engine/network/drivers/ipvlan/)

- **Default bridge network**: Good for quick tests, but not ideal for multi-container apps.
  - Containers on the default bridge can reach outbound networks, but service discovery and isolation are better with a user-defined bridge.
- **User-defined bridge network**: The most common Docker networking pattern for local multi-container apps.
  - Containers on the same user-defined network can resolve each other by container or service name.
- **Published ports**: Used when traffic must enter from the host machine or outside world.
  - Example: expose `localhost:3000` to reach a React app running on port `3000` inside a container.
- **Multiple networks per container**: One container can join more than one network.
  - This is a very common pattern for reverse proxies: they join a public network and a private app network.
- **Host networking**: The container uses the host's network stack directly.
  - This is useful for node-level agents, packet inspection, or workloads that need raw host networking behavior, but it reduces isolation.
- **Macvlan / IPvlan**: Advanced Docker options for making containers appear more directly on the physical network.
  - These are real tools, but they are not the first choice for ordinary web apps.

**What Docker Compose usually gives you**

- One default user-defined bridge network unless you define custom networks.
- DNS by service name, such as `db`, `redis`, or `api`.
- Easy expression of "app can see db, but only app is published to the host."

### 1.3 Kubernetes Networking in Real Life

Official docs: [Pods](https://kubernetes.io/docs/concepts/workloads/pods/), [Services](https://kubernetes.io/docs/concepts/services-networking/service/), [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

- **Every Pod gets an IP**: Kubernetes expects Pods to talk to each other without port publishing between them.
  - This is a major difference from the "publish every useful thing to the host" mental model many people bring from Docker.
- **All containers in one Pod share a network namespace**: They share `localhost`, ports, and the Pod IP.
  - If two containers truly need to communicate over `localhost`, they belong in the same Pod.
- **Services provide stable virtual endpoints**: Pods come and go; the `Service` name stays stable.
  - This is the standard way other workloads find `api`, `redis`, or `postgres`.
- **Ingress and Gateway are cluster entry patterns**: They handle HTTP, TLS, hostname routing, and external exposure.
  - Think of them as the Kubernetes answer to "my Nginx or Traefik container is my front door," except standardized at cluster level.
- **NetworkPolicy controls allowed traffic**: It is the main Kubernetes tool for saying which Pods may talk to which other Pods or CIDRs.
  - This only works if the cluster network plugin enforces NetworkPolicy.
- **The cluster network is bigger than one host**: Kubernetes networking spans nodes.
  - Your app should not care whether Pod A and Pod B are on the same machine.

### 1.4 Quick Mapping: Docker Pattern to Kubernetes Equivalent

Official docs: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [`kubectl port-forward`](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Gateway API in Kubernetes docs](https://kubernetes.io/docs/concepts/services-networking/gateway/)

| Common Docker pattern | What it means | Typical Kubernetes equivalent |
|---|---|---|
| `docker run -p 8080:80 app` | Publish one container port | `kubectl port-forward` for local access, or `Service` + `Ingress` / `Gateway` / `LoadBalancer` for real exposure |
| User-defined bridge network | Private service-to-service communication on one host | Pod-to-Pod networking + `Service` DNS inside a namespace |
| Docker Compose app stack | Several services sharing a network and names | Multiple `Deployment` / `StatefulSet` objects plus `Service` objects |
| Reverse proxy container | Entry point routing traffic to app containers | `Ingress` or `Gateway` + backend `Service` objects |
| `--network container:...` or shared stack pattern | Two containers share one network namespace | Multi-container Pod |
| Container attached to two networks | One workload talks to public and private tiers | `Service` boundaries + `NetworkPolicy`; for true extra interfaces, Multus |
| `--network host` | Use host network directly | `hostNetwork: true` |
| Macvlan / IPvlan | Underlay network integration | Advanced CNI patterns such as Multus + macvlan / ipvlan / SR-IOV |

**Rule of thumb**

- In Docker, networking is usually about **containers on one host**.
- In Kubernetes, networking is usually about **Pods, Services, and policies across a cluster**.

---

## Phase 2: Common Docker Patterns and Kubernetes Equivalents

### 2.1 Pattern: Publish One App Port

Official docs: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), [`kubectl port-forward`](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)

This is the most common Docker networking pattern: run one app container and make it reachable from your laptop or another machine.

**Real-world example**

You are running an internal status dashboard locally while developing:

```bash
docker run --rm -p 8080:80 nginx
```

You open `http://localhost:8080`.

**What this really means**

- Host traffic is entering on `8080`
- Docker forwards it to container port `80`
- The container is still isolated; only the published port is exposed

**Kubernetes equivalent**

There are three realistic equivalents, depending on intent:

1. **Local developer access**: `kubectl port-forward`
2. **Internal cluster access**: `Service` of type `ClusterIP`
3. **Real external access**: `Service` plus `Ingress`, `Gateway`, or `LoadBalancer`

**Local-dev equivalent**

```bash
kubectl port-forward deployment/web 8080:80
```

That is conceptually closer to `docker run -p` than creating a public cloud load balancer just to test something.

**Production-style equivalent**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: nginx:1.27
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
```

If you need hostname routing such as `status.internal.example.com`, add an Ingress or Gateway in front of the `Service`.

**Practical rule**

- If you are thinking "I just need to hit it from my machine," use `port-forward`.
- If you are thinking "other workloads in the cluster need a stable name," use `Service`.
- If you are thinking "users or systems outside the cluster need access," use `Ingress`, `Gateway`, or `LoadBalancer`.

### 2.2 Pattern: App and Database on a Private Network

Official docs: [Docker bridge driver](https://docs.docker.com/engine/network/drivers/bridge/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

This is the classic web-app pattern in Docker: the app can reach the database, but the database is not publicly exposed.

**Real-world example**

A small SaaS API runs in one container and PostgreSQL runs in another. Developers only expose the API port to the host.

```bash
docker network create app-net

docker run -d \
  --name postgres \
  --network app-net \
  -e POSTGRES_PASSWORD=secret \
  postgres:16

docker run -d \
  --name api \
  --network app-net \
  -p 8000:8000 \
  -e DATABASE_URL=postgres://postgres:secret@postgres:5432/app \
  my-api:latest
```

The important detail is not Docker itself. The important detail is the pattern:

- `api` can resolve `postgres`
- `postgres` is private to the network
- only the app entry point is exposed

**Kubernetes equivalent**

- App workload: usually a `Deployment`
- Database workload: often a managed database outside the cluster, or a `StatefulSet` if self-hosted
- Stable DNS name: a `Service`
- Optional network restriction: a `NetworkPolicy`

**Example manifests**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: my-api:latest
          env:
            - name: DATABASE_HOST
              value: postgres
            - name: DATABASE_PORT
              value: "5432"
          ports:
            - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
    - port: 8000
      targetPort: 8000
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          ports:
            - containerPort: 5432
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

**Where teams get tripped up**

- They think "I need to expose Postgres like I published it in Docker."
  - Usually you do not. A `ClusterIP` `Service` is enough for in-cluster consumers.
- They treat a Pod IP as stable.
  - It is not. Use the `Service` name like `postgres`.
- They put app and database in one Pod because they lived in one Compose file.
  - In Kubernetes, scaling boundary and failure boundary matter more than file grouping.

**Real-world note**

For production teams, "Kubernetes equivalent" does not always mean "run Postgres in the cluster." Many teams use managed Postgres, but the application still follows the same networking idea: it connects to a stable DNS name and the database is not generally exposed to the public internet.

### 2.3 Pattern: Reverse Proxy in Front of Multiple Apps

Official docs: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Kubernetes Gateway](https://kubernetes.io/docs/concepts/services-networking/gateway/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)

This is extremely common in Docker Compose: one Nginx or Traefik container routes traffic to multiple backend containers.

**Real-world example**

You have:

- `frontend` at `app.example.com`
- `api` at `api.example.com`
- one reverse proxy container exposed on ports `80` and `443`

**Docker shape**

```yaml
services:
  proxy:
    image: nginx:1.27
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - frontend
      - api
  frontend:
    image: my-frontend:latest
  api:
    image: my-api:latest
```

The reverse proxy joins the app network and routes by hostname.

**Kubernetes equivalent**

The common answer is:

- `Deployment` for `frontend`
- `Deployment` for `api`
- `Service` for each backend
- `Ingress` or `Gateway` for hostname-based routing

**Ingress example**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
spec:
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8000
```

**Why this mapping matters**

- In Docker, the reverse proxy container is just another container.
- In Kubernetes, the cluster often has a shared ingress controller run by the platform team.
- App teams usually define routes, not raw listener processes.

**Practical rule**

- If the proxy is there mainly for HTTP/TLS entry, think `Ingress` or `Gateway`.
- If the proxy is tightly coupled to exactly one app and needs `localhost` access, a sidecar Pod pattern may be more accurate.

### 2.4 Pattern: API, Worker, Redis, and Database

Official docs: [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)

This is the "real app" Docker pattern that shows up constantly:

- API serves HTTP
- Worker processes jobs
- Redis holds queue or cache state
- Postgres stores durable data

**Real-world example**

An e-commerce system creates image thumbnails asynchronously:

- `api` receives image upload
- `api` pushes a job to Redis
- `worker` processes the image
- `postgres` stores metadata

**Docker Compose thinking**

```yaml
services:
  api:
    image: my-api:latest
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - postgres
  worker:
    image: my-worker:latest
    depends_on:
      - redis
      - postgres
  redis:
    image: redis:7
  postgres:
    image: postgres:16
```

**Kubernetes equivalent**

- `api` becomes a `Deployment`
- `worker` becomes a separate `Deployment`
- `redis` gets a `Service`; the backing workload may be a `Deployment` or `StatefulSet`
- `postgres` usually gets a `Service`; the backing workload may be managed externally or self-hosted via `StatefulSet`

**Why separate Deployments matter**

- API and worker scale independently
- Worker restarts should not bounce the API
- Health checks are different
- Resource requests are different

**Example mental mapping**

| Docker service | Kubernetes shape | Why |
|---|---|---|
| `api` | `Deployment` + `Service` | HTTP-serving stateless app |
| `worker` | `Deployment` | Background processing, no public service needed |
| `redis` | `Deployment` or `StatefulSet` + `Service` | Stable in-cluster name |
| `postgres` | Managed DB or `StatefulSet` + `Service` | Stateful dependency |

**Where Docker and Kubernetes differ sharply**

- Docker Compose `depends_on` is not the same as Kubernetes readiness.
  - In Kubernetes, use `readinessProbe`, startup behavior, retries, and resilient application logic.
- Compose groups services in one file.
  - Kubernetes groups by runtime relationships: scaling, availability, routing, and policy.

### 2.5 Pattern: Tightly Coupled Helper Container

Official docs: [Docker Engine networking](https://docs.docker.com/engine/network/), [Kubernetes Pods](https://kubernetes.io/docs/concepts/workloads/pods/), [Sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)

Some workloads need a helper process that should live right next to the main app.

**Real-world examples**

- App + Cloud SQL/Auth proxy
- App + Envoy proxy
- App + log shipper tailing a shared volume
- App + VPN client or tunnel process

**Docker pattern**

In plain Docker this often appears as:

- `--network container:<name>`
- `network_mode: "service:app"` in Compose
- or a looser two-container arrangement where one helper is dedicated to one app

The goal is usually:

- share `localhost`
- share the same lifecycle as much as possible
- avoid exposing helper ports broadly

**Kubernetes equivalent**

This is the classic **multi-container Pod** pattern.

**Example**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-with-proxy
spec:
  containers:
    - name: api
      image: my-api:latest
      env:
        - name: DATABASE_HOST
          value: 127.0.0.1
        - name: DATABASE_PORT
          value: "5432"
    - name: db-proxy
      image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:latest
      args:
        - "--port=5432"
        - "project:region:instance"
```

The `api` container reaches the proxy at `127.0.0.1:5432` because both containers share the Pod network namespace.

**Practical rule**

- Same Pod if the containers must share `localhost`, startup ordering, or a very tight lifecycle.
- Separate Deployments if they scale independently or should survive each other.

### 2.6 Pattern: Use the Host Network Directly

Official docs: [Docker host network driver](https://docs.docker.com/engine/network/drivers/host/), [Kubernetes Pods](https://kubernetes.io/docs/concepts/workloads/pods/)

This is common when a container needs to see the node's real network behavior.

**Real-world examples**

- Node-level monitoring agent
- DNS cache
- Packet capture tool
- BGP speaker
- Ingress controller that binds directly to host ports

**Docker pattern**

```bash
docker run --rm --network host nicolaka/netshoot ss -lntp
```

**Kubernetes equivalent**

Use `hostNetwork: true`, usually with a `DaemonSet` if the workload should run on every node.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-agent
spec:
  selector:
    matchLabels:
      app: node-agent
  template:
    metadata:
      labels:
        app: node-agent
    spec:
      hostNetwork: true
      containers:
        - name: agent
          image: my-agent:latest
```

**Tradeoffs**

- Lower isolation
- Port collisions with node services are now your problem
- Debugging can be more confusing because you are no longer living behind normal Pod networking boundaries

**Practical rule**

Reach for host networking only when the workload genuinely needs node-local visibility or binding behavior. Do not use it just because it feels familiar from Docker.

### 2.7 Pattern: Public and Private Tiers

Official docs: [Docker bridge driver](https://docs.docker.com/engine/network/drivers/bridge/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

A very common Docker Compose pattern is splitting networks into public and private zones.

**Real-world example**

- `proxy` is on `frontend` and `backend`
- `api` is on `backend`
- `db` is only on `backend`

**Docker Compose shape**

```yaml
services:
  proxy:
    image: traefik:v3
    networks: [frontend, backend]
  api:
    image: my-api:latest
    networks: [backend]
  db:
    image: postgres:16
    networks: [backend]

networks:
  frontend: {}
  backend: {}
```

**Kubernetes equivalent**

There is no exact one-to-one equivalent where ordinary Pods just "join two cluster networks" by default.

The usual Kubernetes answer is:

- `Ingress` or `Gateway` for public entry
- `Service` objects for backend reachability
- `NetworkPolicy` for restricting what can talk to what
- often separate namespaces for environment or tenancy boundaries

**Example policy idea**

- Allow ingress to `api` only from the ingress controller namespace
- Allow ingress to `db` only from Pods labeled `app=api`
- Deny everything else by default

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-only-from-api
spec:
  podSelector:
    matchLabels:
      app: db
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
      ports:
        - protocol: TCP
          port: 5432
```

**Important lesson**

Docker network membership is often used as a rough access-control tool.

Kubernetes usually separates that concern into:

- routing (`Service`, `Ingress`, `Gateway`)
- identity/selection (labels and namespaces)
- enforcement (`NetworkPolicy`)

That separation is more powerful, but it is also a bigger mental model.

### 2.8 Pattern Summary: What to Reach for First

Official docs: [Docker Engine networking](https://docs.docker.com/engine/network/), [Kubernetes Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/)

| If you are doing this in Docker... | First Kubernetes thing to think about |
|---|---|
| Publish a local app port | `kubectl port-forward` or `Service` |
| Put app and db on one private network | `Service` names plus `NetworkPolicy` |
| Front multiple apps with Nginx/Traefik | `Ingress` or `Gateway` |
| Run worker + API + cache + db | Separate `Deployment` / `StatefulSet` objects |
| Share `localhost` between helpers | Multi-container Pod |
| Run a node-level networking agent | `DaemonSet` + `hostNetwork: true` |
| Split public/private tiers | `Ingress` / `Gateway` + `Service` + `NetworkPolicy` |

---

## Phase 3: Troubleshooting and Practical Labs

### 3.1 Docker Networking Checks You Will Use Constantly

Official docs: [`docker network ls`](https://docs.docker.com/reference/cli/docker/network/ls/), [`docker network inspect`](https://docs.docker.com/reference/cli/docker/network/inspect/), [`docker exec`](https://docs.docker.com/reference/cli/docker/container/exec/), [`docker port`](https://docs.docker.com/reference/cli/docker/container/port/), [`docker logs`](https://docs.docker.com/reference/cli/docker/container/logs/)

- **List networks**

```bash
docker network ls
```

- **Inspect one network**

```bash
docker network inspect app-net
```

This tells you:

- which containers are attached
- their IPs on that network
- whether you accidentally attached a service to the wrong network

- **Check listening ports inside a container**

```bash
docker exec -it api ss -lntp
```

- **Test DNS from inside a container**

```bash
docker exec -it api getent hosts postgres
docker exec -it api nc -vz postgres 5432
```

- **Check whether the problem is publishing or the app itself**

```bash
curl localhost:8000
docker exec -it api curl localhost:8000
```

If it works inside the container but not via the host port, your problem is outside the application process.

### 3.2 Kubernetes Networking Checks You Will Use Constantly

Official docs: [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/), [Get a shell to a running container](https://kubernetes.io/docs/tasks/debug/debug-application/get-shell-running-container/), [`kubectl exec`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_exec/), [`kubectl logs`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), [`kubectl port-forward`](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_port-forward/)

- **See where Pods actually landed**

```bash
kubectl get pods -o wide
```

- **Inspect Services**

```bash
kubectl get svc
kubectl describe svc api
```

- **See the real backends**

```bash
kubectl get endpointslices
kubectl get endpointslices -l kubernetes.io/service-name=api -o yaml
```

This is one of the fastest ways to answer "does this Service actually point to healthy Pods?"

- **Test DNS from inside the cluster**

```bash
kubectl run dns-test --rm -it --image=busybox:1.36 -- nslookup api
kubectl run dns-test --rm -it --image=busybox:1.36 -- nslookup postgres.default.svc.cluster.local
```

- **Test connectivity from inside the cluster**

```bash
kubectl exec -it deploy/api -- nc -vz postgres 5432
kubectl exec -it deploy/api -- wget -qO- http://frontend
```

- **Port-forward for quick isolation**

```bash
kubectl port-forward svc/api 8000:8000
```

If `port-forward` works but your Ingress path does not, the app and `Service` are probably fine and the problem is higher up the chain.

- **Check NetworkPolicy**

```bash
kubectl get networkpolicy
kubectl describe networkpolicy db-only-from-api
```

- **Check ingress controller logs**

```bash
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
```

### 3.3 Practical Incident Walkthroughs

Official docs: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), [Docker bridge driver](https://docs.docker.com/engine/network/drivers/bridge/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/), [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

#### Incident 1: API Cannot Reach the Database

**Docker version**

Symptoms:

- app logs say `connection refused` or `name not found`
- API starts, but all requests fail on DB access

Fast checks:

1. Is the DB container running?
2. Are app and DB on the same network?
3. Does the app resolve the DB hostname?
4. Is Postgres actually listening on `5432` inside the DB container?

**Kubernetes version**

Fast checks:

1. Are the DB Pods healthy?
2. Does the DB `Service` exist?
3. Does the `Service` have EndpointSlices?
4. Does the API Pod resolve `postgres`?
5. Is a `NetworkPolicy` blocking traffic?

Common root causes:

- wrong label selector on the `Service`
- Pod not ready, so no endpoint is added
- app using Pod IP instead of `Service` name
- DB exposed on the wrong port

#### Incident 2: Web App Works in Pod, But Not From Browser

**Docker version**

- App listens only on `127.0.0.1` inside the container instead of `0.0.0.0`
- Wrong published port mapping
- Reverse proxy points to the wrong upstream container name

**Kubernetes version**

- Pod is healthy, but the `Service` points at the wrong `targetPort`
- Ingress points to the wrong `Service` port
- TLS or hostname rule is wrong
- Readiness probe is failing, so the Pod never becomes a backend

**Fast isolation approach**

1. `kubectl port-forward` directly to the Pod or `Service`
2. If that works, inspect `Service`
3. If `Service` works, inspect `Ingress` or `Gateway`

#### Incident 3: DNS Name Does Not Resolve

**Docker version**

- Containers are on different networks
- You are using the default bridge instead of a user-defined one
- You are trying to resolve a name that exists only in Compose service discovery, not in plain Docker run

**Kubernetes version**

- Wrong namespace
- Wrong short name assumption
- CoreDNS issue
- Headless vs normal `Service` misunderstanding

**Practical reminder**

- `postgres` resolves only inside the same namespace by default
- `postgres.data` or `postgres.data.svc.cluster.local` is safer when crossing namespaces

### 3.4 Practice Labs

Official docs: [Docker Engine networking](https://docs.docker.com/engine/network/), [Compose networks](https://docs.docker.com/reference/compose-file/networks/), [Kubernetes Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)

#### Lab 1: Migrate a Small Compose Stack Mentally

Start with this Compose idea:

- `proxy`
- `api`
- `worker`
- `redis`
- `postgres`

Write down the Kubernetes translation:

- Which become `Deployment`?
- Which become `StatefulSet`?
- Which need `Service`?
- Which need external exposure?
- Which should talk over `localhost`, if any?

If you can answer that cleanly, your networking mental model is improving.

#### Lab 2: Draw the Request Path

For each scenario, draw the packet path:

1. Browser -> Docker app published with `-p 8080:80`
2. Internet -> Kubernetes Ingress -> `Service` -> Pod
3. Worker Pod -> Redis `Service`
4. API Pod -> managed Postgres outside the cluster

This sounds simple, but teams debug much faster when they can sketch the actual path.

#### Lab 3: Break and Fix Service Discovery

In Docker:

- Put `api` and `db` on different networks
- watch hostname resolution fail
- attach them to the same network and verify it works

In Kubernetes:

- create a `Service` with the wrong selector
- observe that the `Service` has no endpoints
- fix labels and confirm traffic starts working

---

## Phase 4: Advanced Kubernetes Networking Patterns

### 4.1 Headless Services and StatefulSets

Official docs: [Headless Services](https://kubernetes.io/docs/concepts/services-networking/service/#headless-services), [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

Use this when clients need to reach specific replicas rather than "any healthy backend."

**Real-world examples**

- Kafka brokers
- Redis Sentinel clusters
- Cassandra
- ZooKeeper
- Any system where ordinal identity matters

**Why a normal Service is not enough**

A normal `Service` load balances across backends. That is great for stateless HTTP apps, but it is wrong for systems where clients need stable identities like:

- `broker-0`
- `broker-1`
- `broker-2`

**Pattern**

- `StatefulSet` gives stable Pod identity
- headless `Service` (`clusterIP: None`) gives DNS records that point directly to Pods

```yaml
apiVersion: v1
kind: Service
metadata:
  name: broker
spec:
  clusterIP: None
  selector:
    app: broker
  ports:
    - port: 9092
      targetPort: 9092
```

Clients can then resolve names like:

- `broker-0.broker.default.svc.cluster.local`
- `broker-1.broker.default.svc.cluster.local`

**When to use it**

Use it when application-level clustering expects stable peer names. Do not use it just because it sounds advanced.

### 4.2 Gateway API for Shared Traffic Management

Official docs: [Gateway API in Kubernetes docs](https://kubernetes.io/docs/concepts/services-networking/gateway/), [Gateway API project docs](https://gateway-api.sigs.k8s.io/)

Ingress is still common, but Gateway API is the more expressive pattern for many modern Kubernetes platforms.

**Real-world example**

A platform team owns the shared edge infrastructure. App teams should be allowed to define routes without owning the entire load balancer configuration.

**Why Gateway API helps**

- clearer separation of duties
- richer routing features
- better expression of traffic policy than "annotations on Ingress"

**Pattern**

- Platform team creates a `Gateway`
- App team attaches `HTTPRoute` objects to it

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-gateway
spec:
  gatewayClassName: example
  listeners:
    - name: http
      protocol: HTTP
      port: 80
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  parentRefs:
    - name: shared-gateway
  hostnames:
    - "api.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: api
          port: 8000
```

**When it shines**

- many teams share one cluster edge
- you need weighted routing, header matching, or cleaner ownership boundaries
- you want traffic policy to be a first-class API instead of controller-specific annotations

### 4.3 Service Mesh for East-West Traffic

Official docs: [Kubernetes Gateway](https://kubernetes.io/docs/concepts/services-networking/gateway/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/), [Sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)

Service mesh is an advanced pattern for managing service-to-service traffic inside the cluster.

**Real-world examples**

- enforce mutual TLS between internal services
- canary 10% of checkout traffic to a new version
- add retries and timeouts between `frontend` and `payments`
- gather detailed traffic telemetry without rebuilding every service

**Typical shape**

- sidecar proxies or node proxies handle traffic
- policies control mTLS, routing, retries, and telemetry
- the application still talks to a normal `Service` name, but the data plane is richer

**When teams adopt it**

- compliance requires encrypted east-west traffic
- platform team needs consistent traffic policy across many apps
- progressive delivery is central to release strategy

**Tradeoff**

Service mesh adds real operational weight:

- more moving parts
- more certificates and control-plane concerns
- more failure modes

Use it when you have mesh-sized problems, not just because it sounds enterprise.

### 4.4 Default-Deny, Egress Control, and Zero-Trust Networking

Official docs: [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/), [Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/)

Many teams start with open east-west traffic and then later realize the cluster is too flat.

**Real-world example**

A PCI-sensitive payments namespace should:

- accept inbound traffic only from the API namespace
- reach only a database, a metrics sink, and an approved payment provider
- block all other lateral movement

**Pattern**

1. Start with default-deny ingress and egress policies
2. Allow only required Pod-to-Pod traffic
3. Control outbound internet access through NAT, firewall rules, or an egress gateway pattern

**What this looks like operationally**

- namespace labels matter
- Pod labels matter
- DNS traffic must be explicitly considered
- third-party API dependencies must be mapped, not guessed

**Why this is advanced**

Because the hard part is not writing YAML. The hard part is understanding every path your application actually needs:

- DNS
- metrics
- tracing
- identity providers
- package mirrors
- cloud metadata services

This pattern is where "we thought networking was simple" often stops.

### 4.5 Topology-Aware Routing and Local Traffic Policies

Official docs: [Topology Aware Routing](https://kubernetes.io/docs/concepts/services-networking/topology-aware-routing/), [Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/#traffic-policies)

In multi-zone clusters, not every backend choice is equally good.

**Real-world example**

You run a latency-sensitive API across three availability zones. You want requests from a Pod in zone A to prefer backends in zone A when possible, reducing cross-zone traffic cost and latency.

**Relevant Kubernetes patterns**

- **Topology-aware routing**: Prefer same-zone backends when the endpoint distribution supports it
- **`internalTrafficPolicy: Local`**: Keep in-cluster traffic node-local when possible
- **`externalTrafficPolicy: Local`**: Preserve source IP and keep external traffic on nodes with local backends

**Why this matters**

- lower latency
- reduced cross-zone bandwidth cost
- better client IP preservation in some ingress/load balancer cases

**Tradeoffs**

- locality can create uneven load if endpoints are not well distributed
- autoscaling and zone skew can make behavior surprising
- "local only" can look like "zero endpoints" from the wrong node

Use these patterns when traffic locality is operationally important, not as a default tweak everywhere.

### 4.6 Multiple Network Interfaces per Pod

Official docs: [Network Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/), [Pods](https://kubernetes.io/docs/concepts/workloads/pods/)

Standard Kubernetes networking assumes one main Pod network interface. Some workloads need more.

**Real-world examples**

- telecom/NFV workloads
- high-performance packet processing
- storage appliances
- workloads that must join a legacy VLAN directly

**Pattern**

Use a meta-plugin approach such as **Multus** so a Pod can have:

- normal cluster interface for Kubernetes traffic
- extra interface for a storage network, telco network, or underlay VLAN

This is the advanced Kubernetes equivalent of the kind of problem people reach for macvlan, ipvlan, or SR-IOV to solve in lower-level container environments.

**Why teams use it**

- strict network separation
- high-performance or low-jitter traffic requirements
- integration with environments that are not designed around plain cluster overlay networking

**Tradeoff**

This moves you much closer to infrastructure engineering than ordinary app deployment. Debugging, IP management, and operational risk all go up.

### 4.7 Multi-Cluster Service Networking

Official docs: [ServiceExport](https://multicluster.sigs.k8s.io/api-types/service-export/), [ServiceImport](https://multicluster.sigs.k8s.io/api-types/service-import/), [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)

At some scale, one cluster is not enough.

**Real-world examples**

- active-active regional services
- disaster recovery across clusters
- one cluster per business unit, but shared service discovery requirements
- edge clusters that must consume central services

**Patterns you will see**

- service mesh multi-cluster
- Multi-Cluster Services APIs
- global DNS over multiple regional ingress endpoints
- east-west gateways between clusters

**Why this is advanced**

You now have to reason about:

- identity across clusters
- failure domains across regions
- overlapping CIDRs
- cross-cluster discovery
- policy consistency

This is where Kubernetes networking becomes distributed-systems networking, not just cluster plumbing.

### 4.8 Choosing the Right Advanced Pattern

Official docs: [Kubernetes Services and Networking concepts](https://kubernetes.io/docs/concepts/services-networking/), [Gateway API in Kubernetes docs](https://kubernetes.io/docs/concepts/services-networking/gateway/), [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

| Problem | Advanced pattern |
|---|---|
| Stable peer identity for clustered databases or brokers | Headless `Service` + `StatefulSet` |
| Shared edge with clearer app/platform ownership | Gateway API |
| mTLS, canary, retries, and rich east-west control | Service mesh |
| Strict least-privilege traffic model | Default-deny `NetworkPolicy` + egress control |
| Reduce cross-zone traffic and preserve locality | Topology-aware routing and traffic policies |
| Pod needs more than one real network interface | Multus / advanced CNI integration |
| Services span regions or clusters | Multi-cluster networking patterns |

**Final takeaway**

The most common Docker networking patterns are about:

- publishing ports
- giving containers names on one host
- fronting apps with a reverse proxy
- isolating databases and private dependencies

The Kubernetes equivalents are usually about:

- Pods as the execution unit
- Services as the stable network identity
- Ingress or Gateway as the front door
- NetworkPolicy as the enforcement layer

Once those basics feel natural, advanced Kubernetes networking stops looking magical and starts looking like a set of deliberate tools for identity, routing, locality, and policy at cluster scale.

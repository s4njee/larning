# Docker Deep Dive

A practical guide to Docker focused on what each component does, when to use it, and how it works under the hood. Assumes basic familiarity (you've run `docker run` and written a Dockerfile). Skips the "what is a container" preamble and goes straight to the machinery.

For Docker/Kubernetes networking specifically, see [Docker & Kubernetes Networking](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md).

Primary references: [Docker Documentation](https://docs.docker.com/), [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/), [OCI Image Spec](https://github.com/opencontainers/image-spec), [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec)

---

## Table of Contents

1. [What Containers Actually Are](#1-what-containers-actually-are)
2. [Images & Layers](#2-images--layers)
3. [Dockerfile in Depth](#3-dockerfile-in-depth)
4. [Multi-Stage Builds](#4-multi-stage-builds)
5. [BuildKit](#5-buildkit)
6. [Volumes, Bind Mounts & tmpfs](#6-volumes-bind-mounts--tmpfs)
7. [Networking](#7-networking)
8. [Docker Compose](#8-docker-compose)
9. [Health Checks & Restart Policies](#9-health-checks--restart-policies)
10. [Resource Limits](#10-resource-limits)
11. [Security](#11-security)
12. [The Runtime Stack: containerd, runc & OCI](#12-the-runtime-stack-containerd-runc--oci)
13. [Registries & Image Distribution](#13-registries--image-distribution)
14. [Logging, Debugging & Observability](#14-logging-debugging--observability)
15. [Production Patterns](#15-production-patterns)
16. [Common Mistakes](#16-common-mistakes)

---

## 1. What Containers Actually Are

Reference: [cgroups(7)](https://man7.org/linux/man-pages/man7/cgroups.7.html), [namespaces(7)](https://man7.org/linux/man-pages/man7/namespaces.7.html), [Understanding the Docker Internals](https://docs.docker.com/get-started/docker-overview/#the-underlying-technology)

A container is not a VM. It's a regular Linux process (or group of processes) with three isolation mechanisms applied to it:

### Namespaces — What the Process Can See

Each namespace type isolates a specific resource so the container sees its own private version:

| Namespace | Isolates | Practical effect |
|---|---|---|
| `pid` | Process IDs | Container's PID 1 is its entrypoint; it can't see host processes |
| `net` | Network stack | Container gets its own interfaces, routing table, iptables, ports |
| `mnt` | Mount points | Container sees its own filesystem (the image + volumes) |
| `uts` | Hostname | Container has its own hostname |
| `ipc` | IPC (shared memory, semaphores) | Containers can't read each other's shared memory |
| `user` | User/group IDs | UID 0 inside can map to UID 100000 on the host (rootless) |
| `cgroup` | Cgroup view | Container sees only its own resource limits |

```bash
# see the namespaces of a running container
ls -la /proc/$(docker inspect --format '{{.State.Pid}}' mycontainer)/ns/
```

### Cgroups — What the Process Can Use

Control groups limit and account for CPU, memory, I/O, and PIDs:

```bash
# Docker creates a cgroup per container — you can inspect it:
cat /sys/fs/cgroup/docker/<container-id>/memory.max
cat /sys/fs/cgroup/docker/<container-id>/cpu.max
```

When a container hits its memory limit, the kernel OOM-kills it. When it hits its CPU limit, it gets throttled. This is how `docker run --memory 512m --cpus 1.5` works under the hood.

### Union Filesystem — How Images Become Filesystems

The image provides read-only layers. The container gets a thin writable layer on top. Writes use copy-on-write — the first write to a file copies it from the read-only layer into the writable layer.

```
┌──────────────────────┐
│   Container Layer    │  ← writable, ephemeral
├──────────────────────┤
│   Image Layer 3      │  ← read-only (e.g., COPY app .)
├──────────────────────┤
│   Image Layer 2      │  ← read-only (e.g., RUN npm install)
├──────────────────────┤
│   Image Layer 1      │  ← read-only (e.g., FROM node:22)
└──────────────────────┘
```

The default storage driver on modern Docker is `overlay2`. Each layer is a directory, and OverlayFS merges them into a single unified view.

### Why This Matters Practically

- **Containers share the host kernel.** A kernel vulnerability affects all containers. This is the fundamental security difference from VMs.
- **Startup is fast** because there's no OS to boot — you're just creating namespaces and cgroups around a process.
- **Density is high** because containers don't duplicate the kernel or a full OS.
- **Isolation is weaker than VMs** — the shared kernel is a larger attack surface.

```quiz
Q: What are the three isolation mechanisms that turn a regular Linux process into a container?
- [x] Namespaces (what it can see — PID, net, mnt, etc.), cgroups (what it can use — CPU/memory/IO limits), and a union filesystem (read-only image layers + a writable copy-on-write layer)
- [ ] A hypervisor, a guest kernel, and virtual hardware
- [ ] chroot, sudo, and seccomp
- [ ] A VM, a network bridge, and a volume
> A container is not a VM — it shares the host kernel, which is the fundamental security difference. --memory and --cpus map to cgroup limits; a memory-limit breach OOM-kills, a CPU-limit breach throttles.

Q: What does the user namespace let you do that the others don't, security-wise?
- [x] Map UID 0 inside the container to an unprivileged UID on the host (rootless) — so root in the container isn't root on the host; without it, container root IS host root and an escape gives host root
- [ ] Isolate the network stack
- [ ] Limit memory usage
- [ ] Hide host processes
> "Containers share the host kernel" means a kernel vuln or misconfig handing kernel privilege is a host compromise — the larger attack surface versus VMs. User namespaces (rootless Docker) shrink the blast radius of an escape.
```

---

## 2. Images & Layers

Reference: [Docker Image Specification](https://docs.docker.com/reference/build-checks/), [OCI Image Spec](https://github.com/opencontainers/image-spec/blob/main/spec.md)

### What an Image Actually Is

An image is an ordered stack of filesystem layers plus metadata (environment variables, entrypoint, exposed ports, labels), where each layer is a tar archive of *filesystem changes* — the files added, modified, or deleted relative to the layer beneath it. But the fact that turns this from a storage detail into the thing that explains Docker's whole performance and economics story is *how those layers combine into the single filesystem a container sees*: a **union filesystem** (overlayfs on modern Linux). Overlayfs stacks the read-only layers and presents them as one merged directory tree — when the container reads `/usr/bin/python`, the kernel searches the layers top-down and returns the first copy it finds, so the layers *appear* as one filesystem without ever being flattened or copied together.

Two mechanisms fall out of this and explain most of Docker's behavior. First, **copy-on-write**: all the image layers are read-only and *shared*, and when a running container writes to a file, overlayfs copies just that file up into a thin writable layer unique to the container, leaving the shared layers untouched. This is why a container starts in milliseconds despite a "gigabyte image" — nothing is copied at startup; the container gets an empty writable layer over the shared read-only stack, and copying happens lazily, per-file, only on write. Second, **sharing across images and containers**: because layers are content-addressed and read-only, ten containers from the same image share *one* on-disk copy of its layers, and two different images built on `python:3.12-slim` share that base layer's bytes once — which is why pulling your second Python image is fast (the base is already local) and why a host running fifty containers doesn't need fifty copies of their common layers. So "an image is a stack of layers" is not bookkeeping trivia; the union-mount-plus-copy-on-write mechanism is *why* containers are cheap to start, cheap to store, and cheap to run many of — the entire value proposition, sitting in this one design.

```bash
# inspect the layers in an image
docker image inspect python:3.12-slim --format '{{json .RootFS.Layers}}' | jq .

# see history — which Dockerfile instruction created each layer
docker history python:3.12-slim
```

### Layer Caching

Each Dockerfile instruction that modifies the filesystem creates a new layer. Docker caches layers and reuses them if the instruction and all parent layers haven't changed.

The cache check depends on the instruction type:
- **`COPY` / `ADD`**: checksums of the files being copied. Changed file → cache miss.
- **`RUN`**: the exact command string. Same string with same parent layer → cache hit, even if the command would produce different output today (`apt update` returns different packages next month, but Docker doesn't know that).

This is why instruction order in a Dockerfile matters enormously — see [Section 3](#3-dockerfile-in-depth).

### Image Tags and Digests

```bash
# tags are mutable pointers — python:3.12 points to different images over time
docker pull python:3.12

# digests are immutable content hashes
docker pull python@sha256:abc123...

# always pin digests in production for reproducible builds
```

### Image Sizes

```bash
# see actual sizes (shared layers are counted once)
docker system df
docker image ls

# see layer-by-layer breakdown
docker history --no-trunc myimage
```

Every layer adds to the image size, even if a later layer deletes files:

```dockerfile
# bad — file.tar.gz still exists in Layer 1, deleted in Layer 2
RUN curl -o file.tar.gz https://example.com/file.tar.gz
RUN tar xzf file.tar.gz && rm file.tar.gz

# good — download, extract, and clean up in one layer
RUN curl -o file.tar.gz https://example.com/file.tar.gz \
    && tar xzf file.tar.gz \
    && rm file.tar.gz
```

```quiz
Q: Why does a container with a "gigabyte image" start in milliseconds?
- [x] Nothing is copied at startup — overlayfs gives the container an empty writable layer over the shared read-only image stack, and copy-on-write copies individual files lazily, only on write
- [ ] The image is decompressed into RAM first
- [ ] Docker pre-boots a minimal OS
- [ ] The kernel caches the whole image
> Copy-on-write plus union mounts is the whole value proposition: cheap to start, cheap to store (ten containers share one on-disk copy of the layers), cheap to run many. Two images on python:3.12-slim share that base layer's bytes once.

Q: Splitting a download and its cleanup across two RUN instructions bloats the image. Why?
- [x] Each instruction creates a layer, and a layer is the *changes* relative to the one below — the file added in layer 1 still occupies space even though layer 2 deletes it; combine download+extract+rm in one RUN
- [ ] Two RUNs run twice as slowly
- [ ] The cache invalidates both layers
- [ ] rm doesn't work across layers
> Layers are additive tar diffs; a later deletion can't shrink an earlier layer. The same reasoning drives ordering for cache efficiency — minimize layers that carry transient files.

Q: Why pin image *digests* rather than *tags* in production?
- [x] Tags are mutable pointers (python:3.12 points to different images over time); a digest (python@sha256:...) is an immutable content hash, giving reproducible builds
- [ ] Digests pull faster
- [ ] Tags can't be used in Dockerfiles
- [ ] Digests are smaller
> A rebuild months later against the same tag can silently get a different base image. Digests freeze exactly which bytes you depend on — the reproducibility guarantee tags can't give.

Q: A RUN apt-get install line stays cached even though apt would fetch newer packages today. Why?
- [x] Docker's cache key for RUN is the exact command *string* plus parent layers — same string, same parent = cache hit, regardless of what the command would produce now
- [ ] Docker re-runs apt and compares output
- [ ] The cache checks package checksums
- [ ] RUN instructions are never cached
> COPY/ADD cache on file checksums (changed file → miss); RUN caches on the command text. This is why instruction *order* matters enormously and why you sometimes need --no-cache or a cache-busting arg for "always fresh" steps.
```

---

## 3. Dockerfile in Depth

Reference: [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)

### Instruction Reference

| Instruction | What it does | Creates a layer? |
|---|---|---|
| `FROM` | Sets the base image | Yes (pulls base layers) |
| `RUN` | Executes a command during build | Yes |
| `COPY` | Copies files from build context | Yes |
| `ADD` | Like COPY but also extracts tars and fetches URLs | Yes |
| `ENV` | Sets environment variables | No (metadata only) |
| `ARG` | Build-time variable (not in final image) | No |
| `WORKDIR` | Sets working directory | No (creates dir if needed) |
| `EXPOSE` | Documents which ports the app uses | No (documentation only) |
| `VOLUME` | Creates a mount point | No (metadata) |
| `ENTRYPOINT` | The executable to run | No (metadata) |
| `CMD` | Default arguments to ENTRYPOINT | No (metadata) |
| `USER` | Sets the user for subsequent instructions | No |
| `LABEL` | Adds metadata key-value pairs | No |
| `HEALTHCHECK` | Container health check command | No |
| `SHELL` | Override default shell for `RUN` | No |
| `STOPSIGNAL` | Signal sent to stop the container | No |

### `ENTRYPOINT` vs `CMD`

These two interact in a specific way that causes constant confusion:

```dockerfile
# ENTRYPOINT = the executable
# CMD = default arguments to the executable
ENTRYPOINT ["python"]
CMD ["app.py"]
# runs: python app.py
# docker run myimage test.py → runs: python test.py (CMD overridden)
```

| | `docker run myimage` | `docker run myimage other-arg` |
|---|---|---|
| Only CMD | runs CMD | runs `other-arg` |
| Only ENTRYPOINT | runs ENTRYPOINT | runs `ENTRYPOINT other-arg` |
| Both | runs `ENTRYPOINT CMD` | runs `ENTRYPOINT other-arg` |

**Shell form vs exec form:**

```dockerfile
# exec form (preferred) — runs directly, PID 1, receives signals
ENTRYPOINT ["python", "app.py"]

# shell form — runs via /bin/sh -c, shell is PID 1, app doesn't get signals
ENTRYPOINT python app.py
```

Always use exec form for ENTRYPOINT so your application is PID 1 and receives `SIGTERM` for graceful shutdown.

### Instruction Ordering for Cache Efficiency

Put instructions that change rarely at the top, and instructions that change frequently at the bottom:

```dockerfile
FROM node:22-slim

WORKDIR /app

# 1. system dependencies — changes rarely
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. dependency manifest — changes when you add/remove packages
COPY package.json package-lock.json ./

# 3. install dependencies — cached until package.json changes
RUN npm ci

# 4. application code — changes every commit
COPY . .

RUN npm run build

USER node
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

If you put `COPY . .` before `npm ci`, every code change invalidates the dependency cache and forces a full reinstall.

### `.dockerignore`

Prevents files from being sent to the build context. Essential for speed and security:

```
# .dockerignore
.git
node_modules
dist
.env
*.md
Dockerfile
.dockerignore
__pycache__
.pytest_cache
.venv
```

Without this, `docker build` ships your entire directory (including `node_modules`, `.git`, etc.) to the daemon, which is slow and can leak secrets.

### `ARG` vs `ENV`

```dockerfile
# ARG — available only during build, not in the final image
ARG NODE_VERSION=22
FROM node:${NODE_VERSION}-slim

ARG BUILD_ENV=production
RUN echo "Building for $BUILD_ENV"

# ENV — available during build AND at runtime
ENV NODE_ENV=production
```

```bash
# override ARG at build time
docker build --build-arg BUILD_ENV=staging .
```

**Security note**: `ARG` values are visible in `docker history`. Don't pass secrets through `ARG` — use BuildKit secrets instead (see [Section 5](#5-buildkit)).

### `COPY --chown` and `COPY --chmod`

```dockerfile
# set ownership at copy time (avoids an extra RUN chown layer)
COPY --chown=node:node . .

# set permissions at copy time (BuildKit only)
COPY --chmod=755 entrypoint.sh /usr/local/bin/
```

---

## 4. Multi-Stage Builds

Reference: [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)

Multi-stage builds use multiple `FROM` instructions. Only the final stage ends up in the image. Previous stages exist only to produce artifacts.

### The Pattern: Build in One Stage, Run in Another

```dockerfile
# --- Stage 1: Build ---
FROM node:22 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Stage 2: Production ---
FROM node:22-slim

WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

USER node
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

**Result**: the final image contains only the runtime (`node:22-slim`), the compiled output, and production dependencies. No TypeScript compiler, no dev dependencies, no source code. Images shrink from hundreds of MB to tens.

```quiz
Q: In a multi-stage build, what ends up in the final image?
- [x] Only the last stage — previous stages exist purely to produce artifacts that you COPY --from into the final one, so build toolchains, dev dependencies, and source never ship
- [ ] All stages, concatenated
- [ ] The largest stage
- [ ] The first stage plus the last
> This is why a Go service can build in golang:1.23 and ship FROM scratch (~10-20MB, just the static binary and TLS certs). The build-vs-run split shrinks images from hundreds of MB to tens and removes the compiler from your attack surface.

Q: Why does the Node multi-stage example COPY package.json and run npm ci *before* COPY . .?
- [x] Layer-cache efficiency — dependencies change rarely, so caching the npm install layer means a source-only change reuses it; copying everything first would bust the dependency cache on every code edit
- [ ] npm requires it
- [ ] It reduces the number of stages
- [ ] Source files must come last alphabetically
> Order instructions from least-to-most frequently changing. The dependency-manifest-then-install-then-source pattern is the single most impactful Dockerfile caching trick, applicable in every ecosystem (Cargo, pip, go mod).
```

### Go — The Extreme Case

Go compiles to a static binary. The final image can be `scratch` (literally empty):

```dockerfile
FROM golang:1.23 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /server ./cmd/server

FROM scratch
COPY --from=builder /server /server
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8080
ENTRYPOINT ["/server"]
```

Final image: ~10-20MB. No shell, no package manager, no OS — just the binary and TLS certs.

### Rust

```dockerfile
FROM rust:1.80 AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
# cache dependency compilation
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/myapp /usr/local/bin/
USER nobody
CMD ["myapp"]
```

### Python

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt -o requirements.txt --without-hashes
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
USER nobody
CMD ["python", "-m", "myapp"]
```

### Copying from External Images

You can copy from any image, not just previous stages:

```dockerfile
# grab a binary from another image
COPY --from=busybox:latest /bin/wget /usr/local/bin/wget

# grab a config from a custom image you maintain
COPY --from=mycompany/configs:latest /etc/nginx/nginx.conf /etc/nginx/
```

### Targeting Specific Stages

```bash
# build only the builder stage (useful for CI/testing)
docker build --target builder -t myapp:test .

# run tests in the builder stage:
docker build --target builder -t myapp:test . && docker run myapp:test npm test
```

---

## 5. BuildKit

Reference: [BuildKit](https://docs.docker.com/build/buildkit/), [Dockerfile frontend syntax](https://docs.docker.com/build/buildkit/dockerfile-frontend/)

BuildKit is Docker's modern build engine (default since Docker Desktop 23.0 and Docker Engine 23.0). It replaces the legacy builder with parallel execution, better caching, and new Dockerfile features.

```bash
# ensure BuildKit is active (set in Docker daemon config or per-build)
DOCKER_BUILDKIT=1 docker build .

# or use the dedicated CLI
docker buildx build .
```

### What BuildKit Improves Over the Legacy Builder

| Feature | Legacy builder | BuildKit |
|---|---|---|
| Build stages | Sequential | Parallel (independent stages build concurrently) |
| Layer caching | Local only | Local, inline, registry, S3, GitHub Actions |
| Secrets | Must use ARG (visible in history) | `--mount=type=secret` (never in image) |
| SSH forwarding | Impossible | `--mount=type=ssh` |
| Build output | Image only | Image, local directory, tar archive |
| Progress output | Verbose | Compact, parallelized |

### Secret Mounting

Pass secrets without baking them into image layers:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install --no-cache-dir -r requirements.txt
```

```bash
docker build --secret id=pip_conf,src=$HOME/.pip/pip.conf .
```

The secret is available during the `RUN` instruction but never written to any image layer.

### SSH Forwarding

Forward the host's SSH agent for private repo access during build:

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22
RUN --mount=type=ssh git clone git@github.com:private/repo.git
```

```bash
docker build --ssh default .
```

### Cache Mounts

Persist caches across builds without including them in the image:

```dockerfile
# syntax=docker/dockerfile:1

# Go module cache
RUN --mount=type=cache,target=/go/pkg/mod \
    go build -o /server ./cmd/server

# Apt cache
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y curl

# pip cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# npm cache
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

Cache mounts dramatically speed up rebuilds. The cache directory persists between builds but isn't included in the image layer.

### External Build Cache

Push cache to a registry so CI pipelines don't start cold:

```bash
# push cache alongside the image
docker buildx build \
  --cache-to type=registry,ref=myregistry/myapp:buildcache \
  --cache-from type=registry,ref=myregistry/myapp:buildcache \
  -t myapp:latest .
```

### Multi-Platform Builds

Build images for different architectures from a single machine:

```bash
# create a builder with multi-platform support
docker buildx create --name multiarch --use

# build for multiple architectures and push
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myregistry/myapp:latest \
  --push .
```

This uses QEMU emulation (slow but works) or cross-compilation (fast, requires Dockerfile changes). For the Pi Zero 2 W specifically, you'd target `linux/arm64`.

---

## 6. Volumes, Bind Mounts & tmpfs

Reference: [Manage data in Docker](https://docs.docker.com/engine/storage/)

Containers are ephemeral — when a container is removed, its writable layer is gone. Docker provides three mechanisms for persistent or shared data:

### Comparison

| | Volumes | Bind mounts | tmpfs |
|---|---|---|---|
| Where data lives | Docker-managed area (`/var/lib/docker/volumes/`) | Anywhere on host | RAM only |
| Survives container removal | Yes | Yes (it's host files) | No |
| Shareable between containers | Yes | Yes | No |
| Performance | Near-native (same filesystem) | Native (direct host access) | Very fast (no disk I/O) |
| Managed by Docker CLI | Yes (`docker volume` commands) | No | No |
| Use case | Database data, persistent state | Dev: live code reload. Source code, config | Sensitive temp data (secrets, session files) |

### Volumes

```bash
# create a named volume
docker volume create pgdata

# use it
docker run -d \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16

# inspect
docker volume inspect pgdata

# list all volumes
docker volume ls

# remove unused volumes
docker volume prune
```

Volumes are the right choice for anything that needs to persist: database files, upload directories, application state.

### Bind Mounts

```bash
# mount current directory into the container
docker run -d \
  -v $(pwd):/app \
  -w /app \
  node:22 npm run dev
```

Bind mounts map a host path directly into the container. The container sees real-time changes to the host filesystem. This makes them essential for development workflows where you want hot-reload.

**Gotcha on macOS/Windows**: bind mounts go through a virtualization layer (Docker Desktop runs Linux in a VM). File-watching-heavy workloads (like webpack with thousands of files) can be slow. Solutions:
- Use volumes for `node_modules` (avoid syncing thousands of files)
- Use Docker's synchronized file shares (Docker Desktop 4.27+)
- Use `:delegated` or `:cached` flags (legacy, less impactful now)

```yaml
# compose pattern: bind mount for source, volume for node_modules
services:
  app:
    volumes:
      - .:/app
      - node_modules:/app/node_modules  # volume, not synced from host

volumes:
  node_modules:
```

### tmpfs Mounts

```bash
docker run -d \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  myapp
```

Data in tmpfs is stored in memory and never written to disk. Use for:
- Temporary files that shouldn't survive a restart
- Sensitive data you don't want on the container filesystem
- Performance-sensitive temp storage

### Read-Only Containers

Run a container with a read-only root filesystem and only allow writes to specific locations:

```bash
docker run -d \
  --read-only \
  --tmpfs /tmp \
  --tmpfs /var/run \
  -v mydata:/data \
  myapp
```

This is a strong security posture — even if an attacker gets code execution, they can't write to the filesystem except designated areas.

---

## 7. Networking

Reference: [Docker Networking Overview](https://docs.docker.com/engine/network/), also see [Docker & Kubernetes Networking](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md) for full depth

This section covers the practical essentials. The dedicated networking guide in this repo covers the underlying theory.

### Network Drivers

| Driver | Use case | How it works |
|---|---|---|
| `bridge` (default) | Single-host container-to-container | Creates a Linux bridge; containers get private IPs; NAT for outbound |
| `host` | Maximum network performance | Container shares the host's network namespace directly — no isolation |
| `none` | Complete network isolation | Container has only a loopback interface |
| `overlay` | Multi-host (Swarm/cluster) | VXLAN tunnel between Docker hosts |
| `macvlan` | Container needs a "real" IP on the LAN | Container gets its own MAC address on the physical network |

### User-Defined Bridge Networks

Always create your own bridge networks instead of using the default `bridge`:

```bash
docker network create mynet

docker run -d --name api --network mynet myapi
docker run -d --name db  --network mynet postgres:16
```

Why user-defined bridges are better than the default:
- **Automatic DNS**: containers resolve each other by name (`db`, `api`). The default bridge requires `--link` (deprecated) or IP addresses.
- **Isolation**: containers on different networks can't communicate.
- **Hot-connect**: you can attach/detach running containers from networks.

### Port Publishing

```bash
# publish container port 3000 to host port 8080
docker run -p 8080:3000 myapp

# publish to a specific interface
docker run -p 127.0.0.1:8080:3000 myapp

# publish to a random host port
docker run -p 3000 myapp
docker port <container>  # see which port was assigned
```

### DNS Resolution in Compose

In a Compose network, services resolve by service name:

```yaml
services:
  api:
    build: .
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/mydb  # "db" resolves to the db container
  db:
    image: postgres:16
```

Docker's embedded DNS server handles this. It returns the container's IP on the shared network.

---

## 8. Docker Compose

Reference: [Docker Compose](https://docs.docker.com/compose/), [Compose Specification](https://docs.docker.com/reference/compose-file/)

Compose defines multi-container applications in a YAML file. It handles networking, volumes, dependencies, and environment configuration.

### Core Structure

```yaml
# compose.yaml (or docker-compose.yml — both work, compose.yaml is canonical)

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: development       # build a specific stage
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://user:pass@db:5432/mydb
    volumes:
      - .:/app
      - node_modules:/app/node_modules
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
  node_modules:
```

### Essential Commands

```bash
# start all services (build if needed)
docker compose up -d

# rebuild images before starting
docker compose up -d --build

# stop and remove containers (volumes preserved)
docker compose down

# stop, remove containers AND volumes (destructive)
docker compose down -v

# view logs
docker compose logs -f api
docker compose logs --tail 50 db

# run a one-off command
docker compose exec api sh
docker compose run --rm api npm test

# scale a service
docker compose up -d --scale worker=3

# see running services
docker compose ps
```

### Environment Variables

Priority order (highest to lowest):
1. `docker compose run -e VAR=value`
2. Shell environment (`export VAR=value` before `docker compose up`)
3. `.env` file in the project root
4. `env_file` directive in compose.yaml
5. `environment` directive in compose.yaml
6. Default in the Dockerfile (`ENV`)

```yaml
services:
  api:
    env_file:
      - .env              # shared defaults
      - .env.local         # local overrides (gitignored)
    environment:
      NODE_ENV: production # explicit — highest priority in compose
```

### Profiles

Run different subsets of services for different workflows:

```yaml
services:
  api:
    build: .
    # no profile — always starts

  db:
    image: postgres:16
    # no profile — always starts

  debug-tools:
    image: busybox
    profiles: [debug]       # only starts with --profile debug

  monitoring:
    image: grafana/grafana
    profiles: [monitoring]  # only starts with --profile monitoring
```

```bash
docker compose up -d                        # api + db only
docker compose --profile debug up -d        # api + db + debug-tools
docker compose --profile monitoring up -d   # api + db + monitoring
```

### Compose Watch (File Sync + Hot Reload)

```yaml
services:
  api:
    build: .
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: package.json
```

```bash
docker compose watch
```

`sync` pushes file changes into the container without rebuilding. `rebuild` triggers a full rebuild when the specified file changes. This replaces bind mounts for development in many cases and avoids the macOS/Windows performance issues.

### Override Files

```bash
# compose.yaml          — base configuration
# compose.override.yaml — dev defaults (auto-loaded)
# compose.prod.yaml     — production overrides

# dev (automatic override):
docker compose up -d

# production:
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

---

## 9. Health Checks & Restart Policies

Reference: [HEALTHCHECK](https://docs.docker.com/reference/dockerfile/#healthcheck), [Restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/)

### Health Checks

A health check tells Docker how to determine if a container is working, not just running:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
```

| Parameter | What it means | Default |
|---|---|---|
| `--interval` | Time between checks | 30s |
| `--timeout` | Max time for a single check | 30s |
| `--start-period` | Grace period after start (failures don't count) | 0s |
| `--retries` | Consecutive failures before `unhealthy` | 3 |
| `--start-interval` | Interval during start period (more frequent checks) | 5s |

Container states: `starting` → `healthy` / `unhealthy`. Docker doesn't automatically restart unhealthy containers, but Compose `depends_on` and orchestrators (Swarm, Kubernetes) use health status.

```bash
# check health status
docker inspect --format '{{.State.Health.Status}}' mycontainer

# see recent health check results
docker inspect --format '{{json .State.Health}}' mycontainer | jq .
```

**Practical health checks by service type:**

```dockerfile
# HTTP service
HEALTHCHECK CMD curl -f http://localhost:3000/health || exit 1

# PostgreSQL
HEALTHCHECK CMD pg_isready -U postgres || exit 1

# Redis
HEALTHCHECK CMD redis-cli ping || exit 1

# worker/queue consumer (write a heartbeat file)
HEALTHCHECK CMD test $(find /tmp/heartbeat -mmin -1 | wc -l) -gt 0 || exit 1
```

### Restart Policies

```bash
docker run -d --restart unless-stopped myapp
```

| Policy | Behavior |
|---|---|
| `no` | Don't restart (default) |
| `on-failure[:max-retries]` | Restart only on non-zero exit code |
| `always` | Restart regardless of exit code, including on daemon startup |
| `unless-stopped` | Like `always`, but don't restart if the container was manually stopped |

`unless-stopped` is the right default for most production services — it survives host reboots but respects manual `docker stop`.

```quiz
Q: What does a HEALTHCHECK tell Docker that the container being "running" doesn't?
- [x] Whether the container is actually *working* (e.g. answering /health), not just that its process exists — states go starting → healthy/unhealthy, and start-period gives a grace window where failures don't count
- [ ] How much memory it's using
- [ ] Whether to restart it automatically
- [ ] Its exit code
> A process can be up but deadlocked or not-yet-ready. Docker doesn't auto-restart unhealthy containers, but Compose depends_on and orchestrators consume the status. start-period is the equivalent of Kubernetes' startupProbe for slow boots.

Q: Why is `unless-stopped` the right restart-policy default for production services?
- [x] It restarts the container on failure and survives host reboots, but respects a manual `docker stop` (unlike `always`, which would restart even something you deliberately stopped)
- [ ] It restarts only on a zero exit code
- [ ] It never restarts, which is safest
- [ ] It's the only policy that works with health checks
> `no` (default) won't survive a crash; `on-failure` won't survive a reboot; `always` ignores your manual stop. `unless-stopped` is the pragmatic middle — resilient but not insubordinate.
```

---

## 10. Resource Limits

Reference: [Runtime options with memory, CPUs](https://docs.docker.com/engine/containers/resource_constraints/)

### Memory

```bash
# hard limit — container is OOM-killed if it exceeds this
docker run -d --memory 512m myapp

# soft limit (reservation) — used for scheduling, not enforcement
docker run -d --memory 512m --memory-reservation 256m myapp

# disable swap (prevent the container from using swap space)
docker run -d --memory 512m --memory-swap 512m myapp
# --memory-swap = --memory means no swap allowed
# --memory-swap = -1 means unlimited swap
```

When a container exceeds its memory limit:
1. The kernel OOM-killer terminates the process
2. Docker records the exit code as 137 (128 + SIGKILL=9)
3. The restart policy determines what happens next

### CPU

```bash
# limit to 1.5 CPUs worth of processing time
docker run -d --cpus 1.5 myapp

# pin to specific CPU cores
docker run -d --cpuset-cpus "0,2" myapp

# relative weight (only matters when CPUs are contended)
docker run -d --cpu-shares 512 myapp   # default is 1024
```

`--cpus` is a hard limit. `--cpu-shares` is a relative weight that only applies when containers compete for CPU — if nothing else is running, a container with low shares still gets full CPU.

### PIDs Limit

Prevent fork bombs:

```bash
docker run -d --pids-limit 100 myapp
```

### Compose Resource Limits

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 256M
```

### Monitoring Resource Usage

```bash
# live resource stats
docker stats

# single snapshot
docker stats --no-stream

# specific container
docker stats mycontainer
```

`docker stats` shows CPU %, memory usage/limit, network I/O, and block I/O per container.

---

## 11. Security

Reference: [Docker Security](https://docs.docker.com/engine/security/), [Docker Bench for Security](https://github.com/docker/docker-bench-security)

### Run as Non-Root

The number one Docker security improvement. By default, processes in a container run as root:

```dockerfile
# create a non-root user and switch to it
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# for distroless or Alpine:
USER nobody
# or
USER 65534
```

If the app is compromised, the attacker has root inside the container. With user namespaces disabled (the default), that maps to root on the host — container escape gives host root.

### Drop Capabilities

Linux capabilities break root's powers into ~40 fine-grained permissions. Docker drops many by default but keeps some. Drop everything and add back only what's needed:

```bash
docker run -d \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  myapp
```

Common capabilities:

| Capability | Allows | Most apps need it? |
|---|---|---|
| `NET_BIND_SERVICE` | Bind ports < 1024 | Only if binding to 80/443 |
| `CHOWN` | Change file ownership | Rarely |
| `SETUID` / `SETGID` | Change user/group | Rarely |
| `SYS_PTRACE` | Debug processes | Only for debugging |
| `NET_RAW` | Raw sockets (ping) | Rarely |

### Read-Only Root Filesystem

```bash
docker run -d \
  --read-only \
  --tmpfs /tmp \
  --tmpfs /var/run \
  myapp
```

### No New Privileges

Prevent the container process from gaining additional privileges via setuid binaries or capabilities:

```bash
docker run -d --security-opt no-new-privileges myapp
```

### Seccomp Profiles

Docker applies a default seccomp profile that blocks ~44 dangerous syscalls (like `reboot`, `mount`, `kexec_load`). You can make it stricter:

```bash
# use a custom profile
docker run -d --security-opt seccomp=myprofile.json myapp

# see the default profile
docker info --format '{{.SecurityOptions}}'
```

### Image Scanning

Scan images for known vulnerabilities before deployment:

```bash
# Docker Scout (built into Docker Desktop)
docker scout cves myimage:latest
docker scout recommendations myimage:latest

# Trivy (open source, widely used in CI)
trivy image myimage:latest

# Grype
grype myimage:latest
```

### Rootless Docker

Run the entire Docker daemon as a non-root user:

```bash
# install rootless Docker
dockerd-rootless-setuptool.sh install

# uses user namespaces — root in container maps to your UID on host
```

Reference: [Rootless mode](https://docs.docker.com/engine/security/rootless/)

### Security Checklist

1. Use a minimal base image (`slim`, `alpine`, distroless)
2. Run as non-root (`USER`)
3. Drop all capabilities, add back selectively
4. Read-only root filesystem
5. No new privileges
6. Pin image digests, not tags
7. Scan images in CI
8. Don't store secrets in images (use BuildKit secrets, runtime secrets management)
9. Use `.dockerignore` to exclude sensitive files from build context
10. Keep Docker and base images updated

```quiz
Q: Why is "run as non-root" the number-one Docker security improvement?
- [x] By default container processes run as root, and with user namespaces disabled (the default) that maps to root on the host — so an app compromise plus a container escape gives host root; a USER directive makes the escape land as an unprivileged user
- [ ] Root processes are slower
- [ ] Non-root containers start faster
- [ ] It's required by the OCI spec
> The USER directive is the cheapest, highest-impact hardening. It pairs with --cap-drop ALL (add back only what's needed), --read-only root filesystem, --security-opt no-new-privileges, and the default seccomp profile.

Q: What does --cap-drop ALL --cap-add NET_BIND_SERVICE accomplish?
- [x] Strips all ~40 Linux capabilities (the fine-grained slices of root's power) and adds back only the one needed to bind ports below 1024 — most apps need none, so dropping all and adding selectively is least privilege
- [ ] It disables networking entirely
- [ ] It grants the container full root
- [ ] It's only for privileged containers
> Docker keeps a permissive default capability set; almost every app needs fewer. Better still, bind a high port and need zero capabilities. The same drop-all-add-back discipline appears in Kubernetes securityContext.

Q: Why pair --read-only with --tmpfs /tmp?
- [x] A read-only root filesystem defeats write-a-payload/drop-a-tool attacks by making the image immutable at runtime — but most apps need *some* writable scratch space, so you mount tmpfs (RAM-backed, ephemeral) explicitly for /tmp and similar
- [ ] tmpfs makes the container faster
- [ ] Read-only mode requires tmpfs to boot
- [ ] It encrypts /tmp
> Read-only root is high-leverage hardening that needs the few writable paths declared explicitly. tmpfs keeps that scratch space in memory and out of the persistent layer — the standard pairing.
```

---

## 12. The Runtime Stack: containerd, runc & OCI

Reference: [Docker architecture](https://docs.docker.com/get-started/docker-overview/#docker-architecture), [containerd](https://containerd.io/), [runc](https://github.com/opencontainers/runc)

### The Architecture

When you run `docker run`, several components are involved:

```
docker CLI
    │
    ▼
Docker daemon (dockerd)     ← API server, build engine, orchestration
    │
    ▼
containerd                  ← container lifecycle (create, start, stop, delete)
    │
    ▼
containerd-shim             ← per-container process that parents the container
    │
    ▼
runc                        ← sets up namespaces/cgroups, execs the container process, then exits
    │
    ▼
your container process      ← PID 1 inside the container
```

### Why the Layers Exist

- **Docker daemon**: the user-facing API, builds images, manages networks/volumes, provides the CLI interface.
- **containerd**: the industry-standard container runtime. Kubernetes uses it directly (without Docker). Manages image pulls, container lifecycle, storage.
- **runc**: the low-level runtime that actually creates the container (sets up namespaces, cgroups, pivot_root). Runs briefly, sets up the isolation, starts the process, then exits.
- **containerd-shim**: stays alive for the lifetime of the container. Keeps stdout/stderr open, reports exit status, allows the container to survive a containerd restart.

### OCI Standards

The Open Container Initiative defines two specs:

| Spec | Defines | Why it matters |
|---|---|---|
| [Image Spec](https://github.com/opencontainers/image-spec) | Image format, manifest, layers, config | Images built by Docker work in Podman, Kubernetes, etc. |
| [Runtime Spec](https://github.com/opencontainers/runtime-spec) | How to run a container (config.json → namespaces/cgroups) | runc, crun, youki all implement this — containers are portable |

### Alternative Runtimes

| Runtime | Language | Differentiator |
|---|---|---|
| `runc` | Go | Reference implementation, default everywhere |
| `crun` | C | Faster startup, lower memory, used by Podman by default |
| `youki` | Rust | Rust implementation of the OCI runtime spec |
| `gVisor (runsc)` | Go | Application kernel — intercepts syscalls for stronger isolation |
| `Kata Containers` | Go | Runs containers in lightweight VMs for VM-level isolation |

```bash
# use an alternative runtime
docker run --runtime=runsc myapp    # gVisor
docker run --runtime=kata myapp    # Kata Containers
```

### Podman — Docker Without a Daemon

Podman is a drop-in Docker CLI replacement that doesn't require a daemon:

```bash
# same CLI, no daemon
podman run -d -p 8080:80 nginx
podman build -t myimage .
podman compose up -d
```

Key differences: daemonless (each container is a child process of the podman command), rootless by default, uses crun instead of runc, no Docker socket to protect.

---

## 13. Registries & Image Distribution

Reference: [Docker Registry](https://docs.docker.com/registry/), [Docker Hub](https://hub.docker.com/)

### Image Naming

```
registry.example.com/organization/repository:tag
│                     │              │          │
│                     │              │          └─ version identifier (default: latest)
│                     │              └─ image name
│                     └─ namespace / org
└─ registry hostname (default: docker.io)
```

```bash
# these are equivalent:
docker pull nginx
docker pull docker.io/library/nginx:latest

# pull from a private registry:
docker pull ghcr.io/myorg/myapp:v1.2.3
docker pull 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:latest
```

### Common Registries

| Registry | URL | Notes |
|---|---|---|
| Docker Hub | `docker.io` | Default, rate-limited for anonymous pulls (100/6h) |
| GitHub Container Registry | `ghcr.io` | Free for public images, integrates with GitHub Actions |
| AWS ECR | `<account>.dkr.ecr.<region>.amazonaws.com` | Per-account, IAM-integrated |
| Google Artifact Registry | `<region>-docker.pkg.dev` | Replaced GCR |
| Azure Container Registry | `<name>.azurecr.io` | AAD-integrated |
| Self-hosted | Any | Run the [registry](https://hub.docker.com/_/registry) image |

### Pushing Images

```bash
# tag for a registry
docker tag myapp:latest ghcr.io/myorg/myapp:v1.0.0
docker tag myapp:latest ghcr.io/myorg/myapp:latest

# authenticate
docker login ghcr.io

# push
docker push ghcr.io/myorg/myapp:v1.0.0
docker push ghcr.io/myorg/myapp:latest
```

### Image Manifests and Multi-Arch

A tag can point to a **manifest list** — a list of image manifests for different platforms:

```bash
# inspect what platforms an image supports
docker manifest inspect python:3.12-slim

# create a multi-arch manifest
docker manifest create myapp:latest \
  myapp:latest-amd64 \
  myapp:latest-arm64
docker manifest push myapp:latest
```

When you `docker pull` on an ARM machine, Docker automatically selects the `linux/arm64` variant from the manifest list.

### Self-Hosted Registry

```bash
# simplest possible private registry
docker run -d -p 5000:5000 --name registry registry:2

docker tag myapp:latest localhost:5000/myapp:latest
docker push localhost:5000/myapp:latest
docker pull localhost:5000/myapp:latest
```

For production, add TLS, authentication, and storage backend configuration. See the [registry deployment guide](https://docs.docker.com/registry/deploying/).

---

## 14. Logging, Debugging & Observability

Reference: [View container logs](https://docs.docker.com/engine/logging/), [Docker logging drivers](https://docs.docker.com/engine/logging/configure/)

### Logs

Docker captures stdout and stderr from the container process:

```bash
# follow logs
docker logs -f mycontainer

# last 100 lines
docker logs --tail 100 mycontainer

# logs with timestamps
docker logs -t mycontainer

# logs since a time
docker logs --since 2024-01-01T00:00:00 mycontainer
docker logs --since 30m mycontainer
```

### Logging Drivers

Docker can send logs to different backends:

| Driver | Destination | `docker logs` works? |
|---|---|---|
| `json-file` (default) | JSON files on disk | Yes |
| `local` | Optimized local format | Yes |
| `syslog` | Syslog daemon | No |
| `journald` | systemd journal | Yes |
| `fluentd` | Fluentd collector | No |
| `awslogs` | CloudWatch Logs | No |
| `gcplogs` | Google Cloud Logging | No |

```bash
docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  myapp
```

**Always set `max-size` and `max-file`** on the json-file driver. Without limits, a noisy container can fill up the disk. Set this in the daemon config (`/etc/docker/daemon.json`) as a default:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}
```

### Debugging Running Containers

```bash
# interactive shell
docker exec -it mycontainer sh
docker exec -it mycontainer bash

# run a specific command
docker exec mycontainer cat /etc/os-release
docker exec mycontainer env
docker exec mycontainer ps aux

# inspect container metadata
docker inspect mycontainer
docker inspect --format '{{.State.Status}}' mycontainer
docker inspect --format '{{.NetworkSettings.IPAddress}}' mycontainer

# see processes
docker top mycontainer

# filesystem changes since the image
docker diff mycontainer
# A = added, C = changed, D = deleted
```

### Debugging Images (No Running Container)

```bash
# start a throwaway container from the image
docker run --rm -it myimage sh

# override the entrypoint
docker run --rm -it --entrypoint sh myimage

# inspect the image without running it
docker image inspect myimage
docker history myimage
```

### Debugging Build Failures

```bash
# with BuildKit, use --progress=plain for full output
docker build --progress=plain .

# target a specific stage
docker build --target builder .

# run the failing stage interactively
docker build --target builder -t debug .
docker run --rm -it debug sh
```

### Copying Files In and Out

```bash
# copy from container to host
docker cp mycontainer:/app/logs/error.log ./error.log

# copy from host to container
docker cp ./config.json mycontainer:/app/config.json
```

### Events

Watch Docker events in real time:

```bash
docker events
docker events --filter container=mycontainer
docker events --filter event=die
```

---

## 15. Production Patterns

### Signal Handling and Graceful Shutdown

PID 1 inside a container receives `SIGTERM` on `docker stop`. The process has 10 seconds (configurable with `--stop-timeout`) to shut down before `SIGKILL`.

**Problem**: if you use shell form in ENTRYPOINT/CMD, `/bin/sh` is PID 1 and your app doesn't get the signal:

```dockerfile
# bad — shell is PID 1, app won't receive SIGTERM
CMD node server.js

# good — node is PID 1, receives SIGTERM directly
CMD ["node", "server.js"]
```

**Problem**: some applications don't handle SIGTERM. Use `tini` or `--init` as a lightweight init process:

```bash
docker run --init myapp
```

Or in the Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends tini
ENTRYPOINT ["tini", "--"]
CMD ["node", "server.js"]
```

`tini` forwards signals to the child process and reaps zombie processes (PID 1 is responsible for reaping zombies — most applications don't do this).

### Minimal Base Images

| Image | Size | Shell? | Package manager? | When to use |
|---|---|---|---|---|
| `ubuntu:24.04` | ~78MB | Yes | apt | Need full OS compatibility |
| `debian:bookworm-slim` | ~75MB | Yes | apt | Need apt but want smaller |
| `alpine:3.20` | ~7MB | Yes (ash) | apk | Minimal, but musl libc can cause compatibility issues |
| `distroless` | ~2-20MB | No | No | Maximum security — no shell to exploit |
| `scratch` | 0MB | No | No | Static binaries (Go, Rust) |

```dockerfile
# distroless for Node.js
FROM node:22 AS builder
WORKDIR /app
COPY . .
RUN npm ci && npm run build

FROM gcr.io/distroless/nodejs22-debian12
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["dist/index.js"]
```

### One Process Per Container

Each container should run one process (one concern). Don't run nginx + your app + a log forwarder in one container.

Benefits:
- Independent scaling (scale workers without scaling the web server)
- Independent health checks (a crashed worker doesn't make the web server look unhealthy)
- Independent logging (each container's stdout is one log stream)
- Independent resource limits
- Simpler restart (restart just the thing that crashed)

### Labels for Metadata

```dockerfile
LABEL org.opencontainers.image.source="https://github.com/myorg/myapp"
LABEL org.opencontainers.image.version="1.2.3"
LABEL org.opencontainers.image.description="My application"
LABEL org.opencontainers.image.created="2025-01-15T10:30:00Z"
```

OCI-standard labels let tools (registries, scanners, orchestrators) understand your images.

### Deterministic Builds

```dockerfile
# pin the base image by digest
FROM node:22-slim@sha256:abc123...

# pin package versions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl=7.88.1-10+deb12u5

# use lock files for application dependencies
COPY package-lock.json ./
RUN npm ci  # ci uses the lockfile exactly, unlike npm install
```

### Docker in CI/CD

```yaml
# GitHub Actions example
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ghcr.io/myorg/myapp:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

The `type=gha` cache backend stores BuildKit cache in GitHub Actions' cache, so subsequent CI builds are fast.

---

## 16. Common Mistakes

### 1. Using `latest` in Production

```bash
# which version is this? depends on when you pulled
docker pull myapp:latest
```

`latest` is a mutable tag. Two machines that pull `latest` at different times get different images. Always use specific version tags or digests in production.

### 2. Running as Root

The default. Fix it:

```dockerfile
USER nobody
```

See [Section 11](#11-security) for the full security rationale.

### 3. Not Setting Memory Limits

Without limits, a memory leak in one container can OOM-kill the host and take down everything. Always set `--memory`.

### 4. Fat Images

```dockerfile
# bad — 900MB image with build tools, source code, test fixtures
FROM node:22
COPY . .
RUN npm install
CMD ["node", "index.js"]

# good — ~150MB image with only what's needed to run
FROM node:22 AS builder
COPY . .
RUN npm ci && npm run build

FROM node:22-slim
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["node", "dist/index.js"]
```

### 5. Secrets in Images

```dockerfile
# bad — token is permanently in a layer, visible in docker history
ARG NPM_TOKEN
RUN echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > .npmrc
RUN npm ci
RUN rm .npmrc  # still in the previous layer!

# good — secret is never in any layer
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
```

### 6. Ignoring .dockerignore

Without `.dockerignore`, `docker build` sends everything to the daemon — including `.git` (could be hundreds of MB), `node_modules`, `.env` files with credentials, and large test fixtures.

### 7. Misunderstanding Layer Caching Order

```dockerfile
# bad — every code change re-runs npm install
COPY . .
RUN npm ci

# good — npm install only re-runs when package.json changes
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
```

### 8. Not Setting Log Rotation

Default `json-file` driver has no size limit. A noisy container logging 1GB/hour will fill your disk.

### 9. Using `docker compose up` Without `--build`

If you change your Dockerfile but don't pass `--build`, Compose reuses the old image. Confusing when your changes "don't take effect."

### 10. Conflating Stop and Kill

```bash
docker stop mycontainer   # SIGTERM → 10s grace → SIGKILL
docker kill mycontainer   # SIGKILL immediately — no graceful shutdown
```

Use `stop` unless you specifically need to force-kill a hung container.

---

## Quick Reference: Docker Commands

### Lifecycle

```bash
docker run -d --name app -p 8080:3000 myimage     # create + start
docker start app                                    # start a stopped container
docker stop app                                     # graceful stop (SIGTERM)
docker restart app                                  # stop + start
docker rm app                                       # remove stopped container
docker rm -f app                                    # force-remove running container
```

### Images

```bash
docker build -t myapp:v1 .                         # build
docker tag myapp:v1 registry.example.com/myapp:v1   # tag
docker push registry.example.com/myapp:v1           # push
docker pull nginx:latest                             # pull
docker image ls                                      # list
docker image rm myapp:v1                             # remove
docker image prune                                   # remove dangling images
docker system prune -a                               # remove everything unused
```

### Inspection

```bash
docker ps                              # running containers
docker ps -a                           # all containers
docker logs -f app                     # follow logs
docker exec -it app sh                 # shell into container
docker inspect app                     # full container metadata
docker stats                           # live resource usage
docker top app                         # processes in container
docker diff app                        # filesystem changes
docker port app                        # port mappings
```

### Cleanup

```bash
docker system df                       # disk usage
docker system prune                    # remove stopped containers, unused networks, dangling images
docker system prune -a --volumes       # aggressive: everything unused including volumes
docker volume prune                    # remove unused volumes
docker image prune -a                  # remove all unused images
docker builder prune                   # remove BuildKit cache
```

---

## Where to Go Next

- **Read the [Dockerfile reference](https://docs.docker.com/reference/dockerfile/) and the [build best-practices page](https://docs.docker.com/build/building/best-practices/)** end to end — short, official, and the source of every layer-caching and multi-stage idiom in this guide.
- **Go beneath the abstraction with the [Linux Fundamentals guide](LINUX_FUNDAMENTALS_STUDY_GUIDE.md)** (Part 8: namespaces + cgroups) — a container is a process, and proving it to yourself (`cat /proc/self/cgroup` inside one, `unshare` your own by hand) permanently demystifies Docker.
- **Read the [OCI image](https://github.com/opencontainers/image-spec/blob/main/spec.md) and [runtime](https://github.com/opencontainers/runtime-spec/blob/main/spec.md) specs' overview sections** — knowing that "Docker image" is just a tarball-of-layers + JSON manifest explains registries, `docker save`, and why alternative runtimes interoperate.
- **Optimize one real image.** Take your largest production Dockerfile and drive it down: multi-stage build, cache mounts, `.dockerignore`, distroless or slim base, then verify with [`dive`](https://github.com/wagoodman/dive). One deliberate optimization pass teaches the whole build model.
- **Adjacent guides in this repo:** [Kubernetes](k8s/KUBERNETES_STUDY_GUIDE.md) (where containers run at scale), [Docker & Kubernetes Networking](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md), [Kubernetes Security](k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md) (image signing/scanning), and [GitHub Actions](GITHUB_ACTIONS_STUDY_GUIDE.md) (building images in CI).

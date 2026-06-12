# Ansible Mastery Study Guide

A depth-first guide to Ansible for engineers who need to configure real machines, not toy ones. Assumes you can SSH into a Linux box, understand basic YAML, and have used at least one configuration-management or provisioning tool before — even if that tool was "a folder of bash scripts." Each phase builds on the previous. Phases 1–11 are the fundamentals; phases 12–14 are the applied recipes (a real role, a real deploy, an end-to-end production playbook) that turn the fundamentals into something you can ship.

> *Ansible's superpower is that it makes the boring half of operations boring. Terraform creates the machine; cloud-init might bootstrap it; Ansible is what keeps it the shape you want — every week, on a thousand boxes, without drift.*

---

## Phase 1: Foundations

### 1.1 What Ansible Actually Is

Ansible is a **push-based, agentless configuration management** tool. You run a command on your laptop (the *control node*); Ansible opens SSH connections to a set of remote machines (the *managed nodes*); on each one, it copies small Python programs (*modules*) into a temp directory, executes them, collects the results, and removes them. There is no daemon. There is no agent. There is no persistent connection. Every run is a fresh SSH session.

This is the single most important thing to internalize: an Ansible run is, mechanically, **SSH + scp + invoke-python**. Once you see it that way, most of Ansible's quirks (latency, the need for Python on the target, the way connection plugins work, why `mitogen` exists) become obvious instead of magical.

Originally created by Michael DeHaan in 2012, Red Hat acquired Ansible in 2015, and it now ships in two main flavors:

- **`ansible-core`** — the open-source engine. Ships the language, the runtime, the `ansible.builtin` module set, and the CLI. About 70 modules.
- **Ansible collections** (post-2.10) — everything else (clouds, networks, Windows, databases, third-party SaaS) lives in *collections* hosted on Ansible Galaxy or a private Automation Hub. You install what you need.

Above that, Red Hat sells **Ansible Automation Platform (AAP)** — RBAC, audit, scheduled jobs, surveys, and a web UI. The open-source equivalent is **AWX**, and the lighter-weight community alternative is **Semaphore**.

References: [Ansible documentation home](https://docs.ansible.com/), [Why Ansible](https://www.ansible.com/overview/it-automation), [ansible-core release notes](https://docs.ansible.com/ansible/latest/roadmap/index.html).

### 1.2 Push vs. Pull, Agent vs. Agentless

The classic config-management split:

| Tool       | Architecture | Transport       | Language     | Default mode |
|------------|--------------|-----------------|--------------|--------------|
| Ansible    | Push         | SSH / WinRM     | YAML + Jinja2 | Imperative-feeling, declarative-by-convention |
| Puppet     | Pull         | HTTPS to puppetserver | Puppet DSL (Ruby-ish) | Strongly declarative |
| Chef       | Pull         | HTTPS to Chef server  | Ruby DSL    | Imperative-procedural |
| Salt       | Push *or* pull | ZeroMQ (default) | YAML + Jinja2 | Declarative |
| cfengine   | Pull         | Custom          | Custom DSL  | Strongly declarative |

**Push** means the control node decides when and where work runs; you trigger it. **Pull** means each managed node periodically asks the server "what should I look like?" and converges itself. Push is simpler to reason about and operate; pull is better for huge fleets and disconnected hosts (intermittent VPNs, edge devices, secure enclaves).

**Agentless** means nothing extra has to be installed on the target — just SSH and Python. You can drop Ansible into an environment with no advance work; you can also use it against ephemeral nodes (CI runners, containers, fresh cloud VMs) without a registration step. The cost is that every run pays the full SSH-handshake-plus-Python-startup tax per host.

In 2026, Salt and Puppet still beat Ansible on raw scale (5,000+ managed nodes), but Ansible's mental-model simplicity and agentless model win for the vast majority of teams — and AWX/AAP closes much of the operational gap when you do need fleet-wide control.

### 1.3 The Idempotency Promise

Every well-written Ansible task is *idempotent*: running it once vs. running it ten times produces the same end state. Modules report `changed: true` only when they actually changed something. This is what makes Ansible safe to run repeatedly, and what makes "do nothing if already correct" cheap.

Idempotency is a property of *modules*, not of YAML. The `file` module is idempotent (creates the file if missing, no-ops if present). The `shell` module is **not** idempotent — it just runs your command. The "imperative-via-declarative-modules" framing is the right one: you write declarative YAML, but the *modules themselves* know how to converge. When you reach for `shell` or `command`, you're stepping outside the idempotency contract and you're responsible for adding `creates:`, `removes:`, `changed_when:`, or `failed_when:` to put it back.

References: [Ansible best practices: idempotency](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html), [`creates`/`removes` parameters](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/command_module.html).

### 1.4 Declarative-Via-Imperative-Modules

A play *looks* imperative — tasks run top-to-bottom in order. But each task delegates to a module that knows how to make a *declaration* true. You don't write "create the file if it doesn't exist, else update it"; you write `state: present` and the module figures out what to do.

This is the same trick Puppet and Chef play; the only difference is that in Ansible, the *ordering* between tasks is yours to control directly. Puppet's compiled catalog declares "these things must be true" and the agent works out the order from dependencies. Ansible says "run these things in this order; each one converges." The Ansible model is more legible to humans, less elegant to graph theorists.

### 1.5 Where Ansible Fits in 2026

Ansible is **not the right tool to create cloud infrastructure**. Terraform (or Pulumi, or the cloud-native templates — CloudFormation, Bicep, Deployment Manager) is built for that — see [TERRAFORM_STUDY_GUIDE.md](TERRAFORM_STUDY_GUIDE.md). Use Terraform to make the VM, the VPC, the load balancer; use Ansible to *configure* the OS, the package manager, the service files, the application deployment.

Ansible's sweet spots in 2026:

- **OS configuration and hardening** — users, groups, sudoers, sysctl, SSH config, CIS benchmarks.
- **App deployment to long-lived VMs** — pulling code, restarting services, rolling updates. Outside Kubernetes, this is still where most companies live.
- **One-shot orchestration** — "patch all production boxes," "rotate certs across the fleet," "run this command on the 12 boxes tagged `role=db`."
- **Network and appliance configuration** — Cisco, Arista, Juniper, F5, Palo Alto. The network collections are first-class.
- **Bootstrapping** — turning a fresh Ubuntu 24.04 box into something useful, often invoked from cloud-init or right after a Terraform apply.

What Ansible is **bad** at in 2026:

- **Building immutable images** — Packer is purpose-built for this. You can use Ansible *as a Packer provisioner*, which is excellent, but Ansible itself doesn't bake AMIs.
- **Continuous fleet drift detection** — works, but Puppet/Salt are stronger because they run on a timer by design.
- **Massive scale** (10k+ nodes) — possible, with tuning, AWX, and `mitogen`, but you'll spend real engineering effort. At that scale a pull-based tool is usually less painful.
- **K8s-native workloads** — use Helm, Kustomize, or operators. Ansible has Kubernetes modules, but they're for managing K8s *clusters*, not for managing apps inside them.

References: [Ansible vs. Puppet](https://www.ansible.com/blog/topic/ansible-vs-other-tools), [Packer Ansible provisioner](https://developer.hashicorp.com/packer/integrations/hashicorp/ansible).

### 1.6 Installation and the Control Node

Install `ansible-core` from your distribution, or — better — from `pipx` so you get a clean isolated environment:

```bash
pipx install --include-deps ansible
ansible --version
ansible-galaxy collection list
```

The control node needs Python 3.10+, SSH, and outbound network access to the managed nodes. Managed nodes need Python 3 (any modern Linux ships with it), SSH (or WinRM on Windows), and a user that can become root if you'll be doing privileged work.

The classic working layout for a team:

```
inventory/
  production/
    hosts.yml
    group_vars/
      all.yml
      webservers.yml
    host_vars/
      web01.example.com.yml
  staging/
    hosts.yml
roles/
  common/
  nginx/
  postgres/
collections/
  requirements.yml
playbooks/
  site.yml
  deploy.yml
ansible.cfg
```

The `ansible.cfg` file is read in this precedence order: `ANSIBLE_CONFIG` env var, `./ansible.cfg`, `~/.ansible.cfg`, `/etc/ansible/ansible.cfg`. Keep a project-local `ansible.cfg` so the team's settings travel with the repo.

A reasonable starting `ansible.cfg`:

```ini
[defaults]
inventory = ./inventory/production/hosts.yml
roles_path = ./roles
collections_path = ./collections
host_key_checking = False
forks = 25
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 7200
retry_files_enabled = False
stdout_callback = yaml
callbacks_enabled = profile_tasks,timer

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o UserKnownHostsFile=/dev/null
```

`pipelining = True` is the single most impactful performance setting — it cuts the number of SSH operations per task roughly in half. The catch: it requires `requiretty` to be disabled in sudoers (it usually already is on modern distros).

References: [Installing Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html), [ansible.cfg reference](https://docs.ansible.com/ansible/latest/reference_appendices/config.html).

```quiz
Q: Why is the `file` module idempotent but the `shell` module is not?
- [ ] `shell` runs as root by default, so it always changes state
- [x] `file` checks current state and converges; `shell` just runs your command blindly
- [ ] `shell` is written in Bash and Bash cannot be idempotent
- [ ] `file` caches its result and `shell` disables caching
> Idempotency is a property of the module, not of YAML. `file` inspects the target and no-ops when it's already in the declared `state`, reporting `changed: false`. `shell` has no idea what "already done" means — it just executes — so you own restoring the contract with `creates:`, `removes:`, `changed_when:`, or `failed_when:`.

Q: In 2026 you need to create a VPC and load balancer and then configure the OS on the resulting VMs. What's the idiomatic split?
- [ ] Ansible for both — it has cloud modules
- [ ] Terraform for both — it can run shell on hosts
- [x] Terraform to create the infrastructure, Ansible to configure the OS
- [ ] cloud-init for both, with no Terraform or Ansible
> Ansible's cloud modules exist, but provisioning cloud infrastructure is Terraform's job — it tracks state, plans diffs, and manages dependencies between resources. Ansible's sweet spot is configuring the OS, packages, service files, and app deployment *after* the box exists. Using each for the other's job means fighting the tool.

Q: A task uses `shell: /opt/app/bin/import-data` and reports `changed: true` on every run, breaking your "no changes = converged" check. What's the right fix?
- [ ] Wrap it in a `block`/`rescue`
- [ ] Switch the strategy to `free`
- [x] Add `creates:` or a `changed_when:` so it reports change accurately
- [ ] Set `gather_facts: false` on the play
> The problem is that `shell` always reports a change because it has no notion of prior state. `creates: /path/to/marker` makes it skip (and report no change) when the work is already done, and `changed_when:` lets you derive "did anything actually change" from the command's output or return code. That's how you put a raw command back inside the idempotency contract.
```

---

## Phase 2: Inventories

### 2.1 The Inventory's Job

An inventory is a list of hosts Ansible can target, organized into *groups*, with *variables* attached at the host level, the group level, or both. Everything Ansible does is scoped to an inventory: when you write `hosts: webservers` in a play, "webservers" is a group defined by the inventory.

The inventory is also where dynamic environments enter the picture. In 2026 most inventories are *plugins* that talk to a cloud API and produce the host list at runtime; static files are mostly for small fixed fleets, lab environments, and CI.

### 2.2 Static Inventories — INI vs. YAML

The two formats are equivalent in expressive power. INI is the historical default; YAML is the modern choice when you want nested structure or variable types other than string.

INI:

```ini
[webservers]
web01.example.com
web02.example.com
web[03:06].example.com

[dbservers]
db01.example.com ansible_host=10.0.1.10

[production:children]
webservers
dbservers

[production:vars]
ansible_user=deploy
```

YAML:

```yaml
all:
  children:
    webservers:
      hosts:
        web01.example.com:
        web02.example.com:
    dbservers:
      hosts:
        db01.example.com:
          ansible_host: 10.0.1.10
    production:
      children:
        webservers:
        dbservers:
      vars:
        ansible_user: deploy
```

A few things to internalize:

- **All hosts implicitly belong to the `all` group.** `hosts: all` targets everything.
- **There's also an implicit `ungrouped` group** for hosts not in any explicit group.
- **Host names are arbitrary labels.** `ansible_host` overrides the actual SSH target. A common pattern: name hosts by role (`web01`, `db01`) and set `ansible_host` to the actual DNS or IP.
- **Ranges expand**: `web[01:06]` becomes `web01` through `web06`.

References: [Build your inventory](https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html).

### 2.3 Dynamic Inventory Plugins

Anything beyond a tiny fleet should use a dynamic inventory. Plugins are YAML files (suffix `.aws_ec2.yml`, `.gcp_compute.yml`, etc.) that Ansible recognizes by their `plugin:` key.

An AWS EC2 example:

```yaml
# inventory/production/aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
  - us-west-2
filters:
  instance-state-name: running
  tag:Environment: production
keyed_groups:
  - key: tags.Role
    prefix: role
  - key: placement.availability_zone
    prefix: az
hostnames:
  - tag:Name
  - private-ip-address
compose:
  ansible_host: private_ip_address
```

This produces groups like `role_web`, `role_db`, `az_us_east_1a` automatically from EC2 tags. The keyed-groups pattern is the workhorse — tag your instances well in Terraform and your Ansible inventory falls out for free.

The big three cloud inventory plugins:

| Plugin | Collection | Auth source |
|---|---|---|
| `amazon.aws.aws_ec2` | `amazon.aws` | AWS SDK chain (env, profile, IRSA, IAM role) |
| `google.cloud.gcp_compute` | `google.cloud` | ADC, service account JSON |
| `azure.azcollection.azure_rm` | `azure.azcollection` | Azure CLI, service principal, MSI |

There's also `community.general.proxmox`, `community.vmware.vmware_vm_inventory`, `kubernetes.core.k8s`, and dozens more. List with `ansible-doc -t inventory -l`.

The old `*.py` dynamic-inventory *scripts* (any executable that prints JSON to stdout) still work and are useful for one-offs — Terraform output, a database query, a Confluence page — but for first-class clouds, plugins are strictly better (caching, parameterization, integration with the rest of the collection).

`meta: refresh_inventory` re-runs the inventory plugin mid-play. Useful when you've just provisioned new hosts inside a play and need them visible to later tasks.

References: [Dynamic inventory plugins](https://docs.ansible.com/ansible/latest/plugins/inventory.html), [aws_ec2 plugin docs](https://docs.ansible.com/ansible/latest/collections/amazon/aws/aws_ec2_inventory.html).

### 2.4 Variables: `group_vars`, `host_vars`, and Precedence

Variables can live in many places. The two cleanest are conventional directories next to the inventory:

```
inventory/production/
  hosts.yml
  group_vars/
    all.yml          # applies to every host
    webservers.yml   # applies to the webservers group
    webservers/      # OR a directory of files, all merged
      ssl.yml
      tuning.yml
  host_vars/
    web01.example.com.yml
```

Ansible automatically loads these. Group vars stack: a host in `webservers` gets `all.yml` overridden by `webservers.yml`. Host vars override group vars. This is the *cleanest* place to put per-environment configuration.

The full variable precedence has [22 documented levels](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence), from least to most authoritative. Worth memorizing the top of the order in practice:

1. Role defaults (`roles/foo/defaults/main.yml`) — lowest, intended to be overridden.
2. Inventory file / dynamic inventory vars.
3. Inventory `group_vars/all` then more-specific group_vars.
4. Inventory `host_vars`.
5. Playbook `group_vars` / `host_vars` (next to the playbook, less common).
6. Host facts (from `setup`).
7. Play `vars`, `vars_files`, `vars_prompt`.
8. Role `vars` (`roles/foo/vars/main.yml`) — high precedence on purpose.
9. Block / task `vars`.
10. `include_vars`, `set_fact` with `cacheable: false`.
11. Extra vars (`-e foo=bar` on the CLI) — **highest**, always wins.

The takeaway: `defaults/` for role values you expect callers to override, `vars/` for values you don't, `group_vars/` for environment-specific config, `-e` for one-off overrides. If you find yourself confused about which value won, run with `-v` and check `--extra-vars` semantics.

References: [Understanding variable precedence](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence).

### 2.5 Host Patterns

The `hosts:` line of a play takes a pattern, not just a group name. Patterns are surprisingly powerful:

| Pattern | Matches |
|---|---|
| `all` | Every host in the inventory |
| `webservers` | The `webservers` group |
| `web01.example.com` | A single host |
| `webservers:dbservers` | Union — webservers OR dbservers |
| `webservers:&production` | Intersection — in webservers AND in production |
| `webservers:!web01.example.com` | webservers EXCEPT web01 |
| `~web\d+\.example\.com` | Regex (note the leading `~`) |
| `webservers[0]` | First host alphabetically |
| `webservers[0:2]` | First two |

Combined with `--limit` (CLI flag that further constrains), this is enough to surgically target almost any subset:

```bash
ansible-playbook site.yml --limit 'webservers:&production:!web01.example.com'
```

References: [Patterns: targeting hosts](https://docs.ansible.com/ansible/latest/inventory_guide/intro_patterns.html).

---

## Phase 3: Modules

### 3.1 The Module Universe

A module is a small program — almost always Python, occasionally a shell script or PowerShell on Windows — that Ansible copies to the managed node, executes, and reads JSON output from. Modules are the *unit of work* in Ansible. Every task invokes exactly one module.

The module namespace is hierarchical: `namespace.collection.module`. The most important namespaces:

| Namespace | Provided by | What lives there |
|---|---|---|
| `ansible.builtin` | ansible-core | The core ~70 modules: `file`, `copy`, `template`, `apt`, `yum`, `service`, `systemd`, `user`, `group`, `lineinfile`, `command`, `shell`, `debug`, `setup` |
| `ansible.posix` | `ansible.posix` collection | POSIX-specific: `mount`, `sysctl`, `selinux`, `firewalld`, `at` |
| `community.general` | `community.general` | The grab-bag: thousands of modules for everything from `pacman` to PagerDuty |
| `community.crypto` | `community.crypto` | OpenSSL, x509, PKI work |
| `amazon.aws`, `google.cloud`, `azure.azcollection` | Cloud vendor collections | Cloud resource management |
| `kubernetes.core` | `kubernetes.core` | Kubernetes/OpenShift |
| `cisco.ios`, `arista.eos`, `junipernetworks.junos` | Network collections | Vendor network gear |

`ansible-doc <module>` is your best friend. `ansible-doc -l` lists every module loaded; `ansible-doc -s file` gives you a YAML snippet you can paste into a playbook.

References: [Module index](https://docs.ansible.com/ansible/latest/collections/index_module.html).

### 3.2 Ad-Hoc Commands with `ansible -m`

Before playbooks, there's ad-hoc — one-task commands against an inventory:

```bash
ansible all -m ping
ansible webservers -m setup
ansible all -m apt -a "name=curl state=present" --become
ansible production -m shell -a "uptime"
ansible web01 -m copy -a "src=/tmp/foo dest=/etc/foo"
```

Ad-hoc is for ops moments: "is everything reachable?", "show me uptime across the fleet," "drain this one box right now." It's also a fantastic teaching tool — every ad-hoc command is exactly equivalent to a one-task playbook.

`-C` puts the command in check mode (Ansible's dry-run). `-D` shows diffs. Both work on ad-hoc and on playbooks.

### 3.3 The Escape Hatches: `command`, `shell`, `raw`

Three modules let you run arbitrary commands. They differ in important ways:

| Module | Shell features | Idempotent? | Needs Python? |
|---|---|---|---|
| `command` | No (no `|`, `$VAR`, `>`, etc.) | Not by default | Yes |
| `shell` | Yes (runs in `/bin/sh -c`) | Not by default | Yes |
| `raw` | Yes (no module overhead at all) | No | **No** |

Default to `command`. Reach for `shell` only when you genuinely need pipes, redirection, or shell variables. Reach for `raw` only when you can't run Python on the target — usually bootstrapping a host that doesn't have Python yet:

```yaml
- name: Install Python (chicken-and-egg)
  ansible.builtin.raw: apt-get install -y python3
  changed_when: false
```

Whenever you use `command` or `shell`, you've taken responsibility for idempotency. The standard tools:

```yaml
- name: Build the thing
  ansible.builtin.command:
    cmd: make build
    chdir: /opt/app
    creates: /opt/app/dist/bundle.js  # skip if this exists
  changed_when: false  # or: 'rc == 0' or a regex over stdout

- name: Curl a URL only if file missing
  ansible.builtin.shell: curl -fsSL https://... > /tmp/blob
  args:
    creates: /tmp/blob
```

`creates` and `removes` are the cheap idempotency wins. `changed_when: false` tells Ansible "I know this isn't really a change," which keeps your run output honest. `failed_when` lets you redefine what failure means.

References: [`command` module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/command_module.html), [`shell` vs. `command`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/shell_module.html).

### 3.4 Return Values and `register`

Every module returns JSON. `register: result` captures it for later use:

```yaml
- name: Read a file
  ansible.builtin.slurp:
    src: /etc/hostname
  register: hostname_blob

- name: Show it
  ansible.builtin.debug:
    msg: "{{ hostname_blob.content | b64decode | trim }}"
```

Standard return keys: `changed` (bool), `failed` (bool), `rc` (return code, for command modules), `stdout`, `stdout_lines`, `stderr`, `msg`. Many modules add their own — `stat` returns a `stat` object, `uri` returns `status`, `json`, etc. `ansible-doc <module>` documents the return shape.

### 3.5 Check Mode and `--diff`

`ansible-playbook --check` is dry-run. Each module reports what it *would* change without changing anything. Not all modules support it perfectly — `command` and `shell` skip by default in check mode unless you set `check_mode: false` on them.

`--diff` (often combined with `--check`) shows file diffs for `template`, `copy`, `lineinfile`, etc. This is the closest thing Ansible has to a `terraform plan`, and it's how you should review playbook changes before applying:

```bash
ansible-playbook site.yml --check --diff --limit web01
```

The honest truth: check mode is *incomplete*. It can't fully simulate everything (handlers don't fire, conditionals that depend on registered results may behave oddly, downstream tasks see "not changed" facts). Treat it as 80% accurate, not 100%. For the last 20%, you use staging environments.

References: [Check mode](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html).

---

## Phase 4: Playbooks

### 4.1 Anatomy of a Play

A playbook is a YAML file containing a list of *plays*. A play binds a set of hosts to a set of tasks (and roles, handlers, variables):

```yaml
- name: Configure webservers
  hosts: webservers
  become: true
  gather_facts: true
  vars:
    nginx_workers: 4
  pre_tasks:
    - name: Update apt cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
  roles:
    - common
    - nginx
  tasks:
    - name: Drop a healthcheck file
      ansible.builtin.copy:
        content: "ok\n"
        dest: /var/www/health
  post_tasks:
    - name: Notify Slack we deployed
      ansible.builtin.uri:
        url: "{{ slack_webhook }}"
        method: POST
        body_format: json
        body: { text: "Deployed to {{ inventory_hostname }}" }
  handlers:
    - name: Restart nginx
      ansible.builtin.systemd:
        name: nginx
        state: restarted
```

Execution order within a play: `pre_tasks` → roles (in declaration order) → `tasks` → `post_tasks` → handlers (only those notified). Handlers run *once at the end of the play*, no matter how many tasks notified them — that's the point.

### 4.2 Tasks

A task is a name (optional but please always provide one), a module invocation, and metadata:

```yaml
- name: Ensure deploy user exists
  ansible.builtin.user:
    name: deploy
    shell: /bin/bash
    groups: sudo
    append: true
    state: present
  become: true
  tags: [user, bootstrap]
```

Every task can carry `become`, `become_user`, `tags`, `when`, `loop`, `register`, `delegate_to`, `run_once`, `ignore_errors`, `changed_when`, `failed_when`, `no_log`, `notify`, plus module-specific args. These are *keywords* and they apply at the task scope.

### 4.3 Handlers and the `notify` Flow

Handlers are tasks that only run when notified, and only once per play even if notified ten times. The canonical use is "restart service after config change":

```yaml
- name: Render nginx config
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    validate: nginx -t -c %s
  notify: Restart nginx

- name: Render upstream config
  ansible.builtin.template:
    src: upstream.conf.j2
    dest: /etc/nginx/conf.d/upstream.conf
  notify: Restart nginx
```

If both templates change, nginx restarts *once* at the end of the play. If neither changes, nginx isn't restarted at all. This is one of Ansible's more elegant mechanics.

`meta: flush_handlers` forces queued handlers to run immediately — useful when later tasks depend on the service actually being restarted:

```yaml
- name: Render config
  template: ...
  notify: Restart nginx

- name: Force handler now
  ansible.builtin.meta: flush_handlers

- name: Hit the new endpoint
  ansible.builtin.uri:
    url: http://localhost/health
    status_code: 200
```

A common bug: handlers don't fire if the play fails before reaching the end. Workaround: `--force-handlers` or `force_handlers: true` on the play.

References: [Handlers](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html).

### 4.4 Plays vs. Tasks vs. Blocks

A **play** binds hosts to work. A **task** is one module invocation. A **block** groups tasks for shared error handling, conditionals, or `become`:

```yaml
- name: Database setup
  block:
    - name: Install postgres
      ansible.builtin.apt: { name: postgresql, state: present }
    - name: Create DB
      community.postgresql.postgresql_db:
        name: app
        state: present
  rescue:
    - name: Notify on failure
      ansible.builtin.debug:
        msg: "Postgres setup failed, rolling back"
  always:
    - name: Always log
      ansible.builtin.debug:
        msg: "Block finished"
  when: ansible_facts.os_family == 'Debian'
  become: true
```

Blocks are Ansible's only real exception handling. `rescue` is the catch; `always` is the finally. Use sparingly — they're powerful but they fragment the linear top-to-bottom mental model.

### 4.5 Facts and the `setup` Module

`gather_facts: true` (the default) runs the `setup` module first, which discovers ~700 facts about the target — OS family, kernel, IPs, disks, mounts, hardware, environment. These end up in `ansible_facts.*`:

```yaml
- debug: var=ansible_facts.distribution
- debug: var=ansible_facts.default_ipv4.address
- debug: var=ansible_facts.memtotal_mb
```

Fact gathering takes 1–3 seconds per host. For tight inner loops, set `gather_facts: false` on plays that don't need them. The `gather_subset` parameter (`!all,!min,network,virtual`) lets you trim the scope. `fact_caching` (jsonfile, redis, memcached) caches facts between runs for big speedups.

`setup` works the same as a regular module — you can call it explicitly, filter it, refresh a subset:

```yaml
- name: Refresh just networking facts
  ansible.builtin.setup:
    gather_subset: network
```

### 4.6 Strategies and Parallelism

By default Ansible runs each task on `forks` hosts in parallel, then waits for *all* to finish before moving to the next task. This is the `linear` strategy.

The `free` strategy lets each host barrel through the playbook as fast as it can, without waiting for siblings. Faster wall-clock when hosts vary in speed, but the output is interleaved and reasoning about state is harder.

```yaml
- hosts: webservers
  strategy: free
  serial: 5
  tasks:
    ...
```

`serial` controls *batching*: do 5 hosts at a time, finish those, then the next 5. Essential for rolling deploys (Phase 11). `serial` can take a number, a percentage (`"25%"`), or a list (`[1, 5, "50%"]`) for canary-then-ramp deploys.

`forks` (in `ansible.cfg` or `-f N` on the CLI) is the global parallelism limit. Default 5; reasonable production value 25–50. Higher than that and you'll start hitting SSH connection limits.

References: [Strategies](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html).

### 4.7 Tags and `--limit`

Tags let you run subsets of a playbook:

```yaml
- name: Install nginx
  ansible.builtin.apt: { name: nginx, state: present }
  tags: [install, packages]

- name: Render config
  ansible.builtin.template: ...
  tags: [config]
```

```bash
ansible-playbook site.yml --tags config
ansible-playbook site.yml --skip-tags packages
ansible-playbook site.yml --list-tasks --tags config  # preview
```

Special tags: `always` (always runs), `never` (only runs if explicitly requested), `tagged`/`untagged`/`all` for `--tags`. Tags propagate from blocks/plays/roles to all their children.

`--limit pattern` restricts the run to a subset of the inventory; it's orthogonal to `--tags`. Together they're the surgical tools you use during incidents.

References: [Tags](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_tags.html).

```quiz
Q: Two tasks in a play both `notify: Restart nginx` and both report a change. How many times does nginx restart?
- [x] Once, at the end of the play, after all notifying tasks have run
- [ ] Twice — once per notifying task
- [ ] Zero — handlers only run with `--force-handlers`
- [ ] Once per host per task, so twice per host
> A handler runs at most once per play no matter how many tasks notify it, and it fires at the *end* of the play's tasks, not inline. That's exactly why it's the right tool for "restart after any of several config files changed": you batch the expensive restart into a single action. If you need it sooner, `meta: flush_handlers` forces queued handlers to run immediately.

Q: A play fails on a task that came *after* a template task already notified `Restart nginx`. By default, does the handler run?
- [ ] Yes — handlers always run on the host that notified them
- [x] No — the play aborted before reaching the handler-flush point, so the restart is skipped
- [ ] Yes, but only if `gather_facts` was true
- [ ] No, and there is no way to make it run
> Handlers run at the end of the play, so a failure before that point leaves them queued but never executed — a classic source of "config changed but service still running the old config" bugs. `force_handlers: true` (or `--force-handlers`) makes queued handlers run even when the play fails.

Q: What does a `block` with `rescue` and `always` give you that ordinary tasks don't?
- [ ] Parallel execution of the grouped tasks
- [ ] Automatic idempotency for `shell` tasks inside it
- [x] Try/catch/finally semantics — `rescue` runs on failure, `always` runs regardless
- [ ] A separate SSH connection per task in the block
> Blocks are Ansible's only real exception handling: `rescue` is the catch (runs only if a task in the block failed) and `always` is the finally (runs no matter what). They also let you attach a shared `when`, `become`, or tags to a group of tasks. Use them sparingly — they fragment the otherwise linear top-to-bottom reading of a play.
```

---

## Phase 5: Variables and Jinja2

### 5.1 Where Variables Come From

Already covered in Phase 2.4. The short version: defaults < inventory < play vars < role vars < `set_fact` < `-e` on the CLI. In real projects the vast majority of values live in `group_vars/` and `roles/*/defaults/`.

### 5.2 `set_fact` vs. `register`

- `register` captures a module's return value as a variable on the current host. Per-host, ephemeral to the play.
- `set_fact` defines a new variable on the current host. Per-host, persistent across plays in the same run.

```yaml
- name: Run a command
  command: hostname -f
  register: hn_result

- name: Pin it as a fact
  ansible.builtin.set_fact:
    fqdn: "{{ hn_result.stdout }}"
    cacheable: true   # also save to fact cache for future runs
```

`set_fact` with `cacheable: true` writes to the configured fact cache — survives between runs. Without it, facts are run-local.

### 5.3 Jinja2 in Anger

Ansible runs every templated string through Jinja2 before evaluating. `{{ }}` is interpolation; `{% %}` is logic; `{# #}` is a comment.

Filters worth knowing — almost daily-use:

| Filter | What it does |
|---|---|
| `default(x)` | Use `x` if undefined or null |
| `default(x, true)` | Use `x` if falsy (empty string, [], etc.) too — the safer form |
| `mandatory` | Fail if undefined — use to enforce required inputs |
| `bool` | Cast a truthy string to a boolean |
| `int`, `float` | Type casts |
| `length`, `count` | Collection sizes |
| `upper`, `lower`, `title`, `replace`, `regex_replace`, `regex_search` | String ops |
| `join(',')` | List → string |
| `split(',')` | String → list |
| `map('attribute', 'name')` | Pluck a field from a list of dicts |
| `selectattr('key', 'eq', 'value')` | Filter list of dicts |
| `to_json`, `to_nice_json`, `from_json` | JSON round-trips |
| `to_yaml`, `to_nice_yaml`, `from_yaml` | YAML round-trips |
| `b64encode`, `b64decode` | Base64 |
| `hash('sha256')` | Hashing |
| `password_hash('sha512', 'salt')` | Crypt-format passwords for the `user` module |
| `ipaddr`, `ipv4`, `ipv6`, `ipaddr('network')` | Network math (`ansible.utils` collection) |
| `combine(a, b, recursive=true)` | Deep-merge dicts — essential for layered config |
| `dict2items` / `items2dict` | Iterate dicts as `{key, value}` pairs |

The `default` filter is the single most important safety habit:

```yaml
nginx_port: "{{ nginx_port | default(80) }}"
nginx_extra_args: "{{ nginx_extra_args | default([], true) }}"  # also catches empty strings
required_thing: "{{ required_thing | mandatory }}"
```

A footgun: `{{ var }}` returns the string `'AnsibleUndefined'` for undefined vars unless you've enabled strict mode. Set `ANSIBLE_JINJA2_NATIVE=true` or `jinja2_native = true` in `ansible.cfg` to get real Python types back from Jinja2 (e.g., a Jinja2 expression that evaluates to a list stays a list, doesn't get coerced to a string). This is almost always what you want.

References: [Templating](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_templating.html), [Built-in filters](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_filters.html).

### 5.4 `lookup` Plugins

Lookups run on the **control node** (not the target) and return data into the play:

```yaml
- name: Read a local file
  debug:
    msg: "{{ lookup('file', '/etc/hostname') }}"

- name: Read an env var
  debug:
    msg: "{{ lookup('env', 'AWS_REGION') }}"

- name: Pull from HashiCorp Vault
  debug:
    msg: "{{ lookup('community.hashi_vault.vault_kv2_get', 'secret/data/api', engine_mount_point='kv') }}"

- name: Pull from AWS SSM Parameter Store
  debug:
    msg: "{{ lookup('amazon.aws.aws_ssm', '/prod/db/password') }}"

- name: Generate or fetch a password
  debug:
    msg: "{{ lookup('password', '/tmp/foo.pwd length=32') }}"
```

Common lookups: `file`, `env`, `password` (generates and persists), `template`, `pipe` (run a local command), `vars`, `dig` (DNS), `url`, `csvfile`, `ini`. Cloud lookups: `aws_ssm`, `aws_secret`, `gcp_secret_manager`, `azure_keyvault_secret`. Secret-manager lookups: `hashi_vault`, `bitwarden`, `1password`.

`lookup` returns a single value; `query` (or `lookup(..., wantlist=true)`) returns a list. Useful when looping over the results.

References: [Using lookups](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_lookups.html).

### 5.5 `ansible-vault` for Secrets

Encrypted strings or files, AES-256-CTR, keyed by a passphrase. Two patterns:

**Whole-file encryption**:

```bash
ansible-vault create group_vars/production/secrets.yml
ansible-vault edit group_vars/production/secrets.yml
ansible-vault view group_vars/production/secrets.yml
ansible-vault rekey group_vars/production/secrets.yml   # change the passphrase
```

**Inline string encryption** (the modern way — diffs better):

```bash
ansible-vault encrypt_string 'super-secret' --name db_password
```

Produces:

```yaml
db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  35663534643732...
```

You can mix encrypted and unencrypted values in the same YAML file. At run time, supply the password:

```bash
ansible-playbook site.yml --ask-vault-pass
ansible-playbook site.yml --vault-password-file ~/.vault_pass
```

**Vault IDs** let you have multiple vaults — `prod`, `staging`, shared — each with its own password:

```bash
ansible-vault encrypt --vault-id prod@~/.vault_pass_prod secrets.yml
ansible-playbook site.yml --vault-id prod@prompt --vault-id staging@~/.vault_pass_staging
```

The honest reality of `ansible-vault` in 2026: it's a passable secret store *if* the passphrase is handled by a real secret manager. In greenfield work, prefer a lookup against HashiCorp Vault, AWS Secrets Manager, or 1Password — keep secrets at rest in the system designed for them, not in the playbook repo.

References: [Encrypting content with Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html).

```quiz
Q: You `register` a command's output in a play, then a later play targeting the same hosts references that variable. What happens?
- [ ] It works — registered vars persist for the whole run
- [x] It's undefined — `register` scope is the current play and host, not the run
- [ ] It works only if `fact_caching` is enabled
- [ ] It silently uses the value from the first host
> `register` captures a module's return value as a per-host variable scoped to the play it ran in. It does not survive into a later play. If you need a value to persist across plays, promote it with `set_fact` (which writes a host fact for the remainder of the run) or cache it — but don't assume a registered variable is visible outside its play.

Q: What does `ansible-vault` actually protect, and what's the honest 2026 recommendation?
- [ ] It protects secrets in transit; for storage use plaintext group_vars
- [x] It encrypts values at rest with AES-256; greenfield work should still prefer a real secret manager via lookup
- [ ] It encrypts the SSH session so secrets never touch disk
- [ ] It rotates secrets automatically on every playbook run
> Vault gives you AES-256 encryption of strings or whole files, keyed by a passphrase — genuinely useful, but only as strong as how you handle that passphrase. In greenfield work the better pattern is a runtime `lookup` against HashiCorp Vault, AWS Secrets Manager, or 1Password, keeping secrets in a system built to store, audit, and rotate them rather than committing ciphertext to the playbook repo.
```

---

## Phase 6: Roles

### 6.1 The Role Directory Layout

A role is a self-contained chunk of automation. Calling a role from a play wires up its tasks, handlers, defaults, templates, files, and metadata in one go. The structure is by convention:

```
roles/nginx/
  defaults/
    main.yml         # default vars — lowest precedence, intended to be overridden
  vars/
    main.yml         # high-precedence role vars — not meant to be overridden by callers
  tasks/
    main.yml         # entry point
    install.yml
    configure.yml
  handlers/
    main.yml         # handlers, scoped to the role
  templates/
    nginx.conf.j2    # Jinja2 templates, used with the template module
  files/
    welcome.html     # raw files, used with the copy module
  meta/
    main.yml         # dependencies, supported platforms, Galaxy metadata
  library/           # custom modules shipped with the role
  module_utils/      # shared Python for those modules
  filter_plugins/    # custom Jinja2 filters
  lookup_plugins/    # custom lookup plugins
  tests/
    test.yml
```

You don't need all of these — most roles have `defaults/`, `tasks/`, `handlers/`, `templates/`, sometimes `files/` and `vars/`, and `meta/main.yml` if it has dependencies.

`tasks/main.yml` is the entry point. Long roles usually use `include_tasks` or `import_tasks` to split into per-concern files (`install.yml`, `configure.yml`, `service.yml`).

### 6.2 When to Use a Role

A good role models **one concern**: install and configure nginx; manage a Postgres cluster; harden SSH. Bad roles try to be giant kitchen sinks ("the prod role"). The shape that works in practice:

- **`common`** — things every host gets (timezone, NTP, locale, baseline packages, base sudoers).
- **One role per service** — `nginx`, `postgres`, `redis`, `app`.
- **A site playbook** that wires roles to host groups.

Roles are also Galaxy's unit of distribution. The `geerlingguy.*` roles are the canonical reference style — terse, well-documented, conservative.

### 6.3 `roles:` vs. `import_role` vs. `include_role`

Three ways to invoke a role; they differ subtly:

| Mechanism | When evaluated | Tags / conditionals |
|---|---|---|
| `roles:` keyword on a play | At parse time, before any tasks run | Tags apply to all role tasks |
| `import_role` (a task) | At parse time (static) | Conditionals on the import apply to *all* role tasks |
| `include_role` (a task) | At runtime (dynamic) | Conditionals on the include apply only to the include itself |

Practical rules:

- Default to `roles:` for the main play-level role list.
- Use `import_role` when you want a role mid-task-list and want it tag-able and statically analyzable.
- Use `include_role` only when you genuinely need runtime behavior — e.g., the role to include depends on a registered variable.

```yaml
- hosts: webservers
  roles:
    - common
    - { role: nginx, nginx_workers: 8 }

  tasks:
    - name: Conditionally apply the cache role
      ansible.builtin.import_role:
        name: redis
      when: cache_required | bool

    - name: Pick a role at runtime
      ansible.builtin.include_role:
        name: "{{ chosen_role }}"
```

### 6.4 Role Dependencies via `meta/main.yml`

```yaml
# roles/app/meta/main.yml
galaxy_info:
  author: Sanjee
  description: Deploys the app
  license: MIT
  min_ansible_version: "2.15"
  platforms:
    - name: Ubuntu
      versions: [jammy, noble]

dependencies:
  - role: common
  - role: nginx
    vars:
      nginx_workers: 4
```

Dependencies run *before* the role itself. They're deduplicated by name + variables: the same role with the same vars only runs once even if multiple roles depend on it. This is occasionally a footgun (you wanted it to run twice with different variables — it won't unless the vars differ).

In modern Ansible, prefer keeping dependencies explicit in the *playbook* rather than buried in `meta/main.yml`. Easier to reason about, easier to refactor.

References: [Roles](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html), [Galaxy role usage](https://docs.ansible.com/ansible/latest/galaxy/user_guide/index.html).

---

## Phase 7: Control Flow

### 7.1 Conditionals — `when`

`when` is Jinja2 evaluated as a Python expression — note: *not* in `{{ }}`:

```yaml
- name: Install on Debian only
  ansible.builtin.apt:
    name: nginx
    state: present
  when: ansible_facts.os_family == 'Debian'

- name: Run if multiple conditions
  ansible.builtin.command: /opt/run
  when:
    - ansible_facts.distribution_major_version | int >= 22
    - inventory_hostname in groups['production']
    - not skip_run | default(false) | bool
```

A list of `when` conditions is AND-ed. For OR, write the expression directly: `when: foo == 'a' or foo == 'b'`.

The common subtle bug: `when: my_var` is truthy even when `my_var = "false"` (it's a non-empty string). Use `| bool` to force boolean semantics.

### 7.2 Loops

The modern syntax is `loop:`. The legacy `with_*` family is still supported but discouraged — `with_items` → `loop`, `with_dict` → `loop: "{{ x | dict2items }}"`, `with_fileglob` → `loop: "{{ query('fileglob', 'pattern') }}"`, etc.

```yaml
- name: Create users
  ansible.builtin.user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
    state: present
  loop:
    - { name: alice, groups: [sudo, deploy] }
    - { name: bob, groups: [deploy] }
  loop_control:
    label: "{{ item.name }}"   # cleaner output

- name: Loop with index
  ansible.builtin.debug:
    msg: "{{ idx }}: {{ item }}"
  loop: "{{ ['a', 'b', 'c'] }}"
  loop_control:
    index_var: idx
```

`loop_control` options worth knowing: `label` (what gets printed per iteration — use this to hide secrets), `index_var`, `pause` (seconds between iterations), `loop_var` (rename `item`).

### 7.3 Blocks, Rescue, Always

Already covered in Phase 4.4. A reminder: blocks are the *only* exception handling. Tasks fail by default; `ignore_errors: true` continues; `failed_when:` redefines failure; `rescue:` catches.

```yaml
- block:
    - name: Try to mount
      ansible.builtin.mount:
        path: /data
        src: /dev/vdb1
        fstype: ext4
        state: mounted
  rescue:
    - name: Report
      ansible.builtin.fail:
        msg: "Mount failed, manual intervention needed"
  always:
    - name: Log
      ansible.builtin.debug: msg="mount block done"
```

### 7.4 Per-Task Error Tuning

| Keyword | Effect |
|---|---|
| `ignore_errors: true` | Don't fail the play if this task fails |
| `failed_when: <expr>` | Treat the task as failed iff the expression is true |
| `changed_when: <expr>` | Treat the task as changed iff the expression is true |
| `ignore_unreachable: true` | Don't fail if the host becomes unreachable on this task |
| `no_log: true` | Don't show the task's args/result in output (use for secrets) |

```yaml
- name: A custom check
  ansible.builtin.shell: /opt/check.sh
  register: r
  changed_when: false
  failed_when: r.rc != 0 and 'WARN' not in r.stdout
```

### 7.5 Play-Wide Failure Control

| Keyword | Effect |
|---|---|
| `any_errors_fatal: true` | Any host failure aborts the entire play across all hosts |
| `max_fail_percentage: 25` | Continue until N% of hosts have failed |
| `serial: 1` + `max_fail_percentage: 0` | Pure canary — first failure halts everything |

`any_errors_fatal` is non-negotiable for orchestration plays where one host succeeding while another fails would leave the system in an inconsistent state (think: a database migration on one node and not another).

References: [Error handling in playbooks](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_error_handling.html).

---

## Phase 8: Templates

### 8.1 Jinja2 in Files: the `template` Module

`template` renders a Jinja2 template on the control node and copies the result to the target. `copy` copies bytes verbatim. Don't conflate them — if your file has `{{ }}` in it, use `template`.

```yaml
- name: Render nginx config
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: "0644"
    validate: nginx -t -c %s   # critical
    backup: true               # keep the previous version
  notify: Restart nginx
```

A template:

```jinja2
# {{ ansible_managed }}
worker_processes {{ nginx_workers | default(ansible_facts.processor_vcpus) }};

events {
    worker_connections {{ nginx_connections | default(1024) }};
}

http {
{% for upstream in nginx_upstreams %}
    upstream {{ upstream.name }} {
{%   for server in upstream.servers %}
        server {{ server }};
{%   endfor %}
    }
{% endfor %}
}
```

The `ansible_managed` variable expands to a configurable header — set in `ansible.cfg` (`ansible_managed = Managed by Ansible, do not edit`). The point: humans who find the file know to edit Ansible, not the file.

### 8.2 The `validate` Parameter — Use It

`validate` runs a syntax check on the rendered file *before* moving it into place. If the check fails, the file is not overwritten and the task fails. This is the difference between a typo and a downed nginx.

| File type | Validate command |
|---|---|
| nginx | `nginx -t -c %s` |
| sshd | `/usr/sbin/sshd -t -f %s` |
| sudoers | `/usr/sbin/visudo -cf %s` |
| apache | `/usr/sbin/apache2ctl -t -f %s` |
| named | `named-checkconf %s` |
| JSON | `python3 -m json.tool %s` |

Add a `validate` for every config file where bad syntax means an outage. The few extra seconds at deploy time are worth the saved 3 AM page.

### 8.3 Whitespace Control

Jinja2 leaves trailing newlines from `{% %}` blocks by default, which leads to ugly extra blank lines. The hyphen modifiers strip:

```jinja2
{% for s in servers -%}
server {{ s }};
{%- endfor %}
```

- `{%-` strips whitespace before the tag.
- `-%}` strips whitespace (including newlines) after the tag.

Use them when the output of a loop ends up with a blank line per iteration. It's fiddly. The `template` module doesn't (yet) format the output for you.

### 8.4 `copy` vs. `template` vs. `lineinfile` vs. `blockinfile`

| Module | Use when |
|---|---|
| `copy` | You own the whole file, no Jinja2 needed |
| `template` | You own the whole file, with Jinja2 |
| `lineinfile` | You need to ensure one line is present/absent in a file someone else owns |
| `blockinfile` | You need to manage a multi-line block in someone else's file (between markers) |
| `replace` | You need regex substitution across a file |

`lineinfile` is appropriate for `/etc/hosts`, `~/.bashrc`, `/etc/sysctl.conf`, sudoers includes — files where the existing content is *not* yours to overwrite. `blockinfile` adds delimiter comments (`# BEGIN ANSIBLE MANAGED BLOCK`) so future runs can find and replace the block:

```yaml
- name: Manage a block in /etc/hosts
  ansible.builtin.blockinfile:
    path: /etc/hosts
    block: |
      10.0.1.10 db01
      10.0.1.11 db02
    marker: "# {mark} ANSIBLE MANAGED HOSTS"
```

For new files you control, prefer `template` — owning the whole file is cleaner than patching it.

References: [`template` module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html), [`lineinfile` module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/lineinfile_module.html).

---

## Phase 9: Collections, Galaxy, and the Ecosystem

### 9.1 The Collections Era

Starting with Ansible 2.10 (late 2020), Ansible split into `ansible-core` (the engine + a small builtin set) and *collections* (everything else). Today every module other than `ansible.builtin.*` lives in a collection that's versioned independently and installed separately.

A collection is just a directory containing modules, roles, plugins, and metadata. They're distributed via Ansible Galaxy (public) or Red Hat's Automation Hub (private/enterprise) — and you can also install them straight from Git, a tarball, or a local path.

`requirements.yml` is the manifest you pin your dependencies in:

```yaml
collections:
  - name: amazon.aws
    version: ">=8.0.0,<9.0.0"
  - name: community.general
    version: "9.0.0"
  - name: community.postgresql
    version: ">=3.4.0"
  - name: kubernetes.core
  - name: https://github.com/myorg/internal-collection.git
    type: git
    version: main

roles:
  - name: geerlingguy.postgresql
    version: "3.6.0"
  - src: git+https://github.com/myorg/role-x.git
    name: role_x
    version: v1.2.0
```

Install:

```bash
ansible-galaxy install -r requirements.yml -p ./collections
ansible-galaxy collection install -r requirements.yml --upgrade
```

Pin versions in production. Ansible Galaxy collections move fast; an unpinned `community.general` upgrade can break a playbook in subtle ways.

### 9.2 The Key Collections to Know

| Collection | What you'd use it for |
|---|---|
| `ansible.builtin` | Core modules |
| `ansible.posix` | POSIX-specific |
| `community.general` | Catch-all — `htpasswd`, `make`, `pacman`, PagerDuty, Slack, Sensu, ... |
| `community.crypto` | x509, PKCS, OpenSSH keypairs, JWT |
| `community.postgresql` / `community.mysql` / `community.mongodb` | DB administration |
| `amazon.aws` / `community.aws` | AWS resources |
| `google.cloud` | GCP resources |
| `azure.azcollection` | Azure resources |
| `kubernetes.core` | K8s management |
| `community.docker` / `containers.podman` | Container management |
| `community.hashi_vault` | HashiCorp Vault lookups |
| `cisco.ios`, `cisco.nxos`, `arista.eos`, `junipernetworks.junos` | Network gear |
| `ansible.windows`, `community.windows` | Windows via WinRM |

`ansible-galaxy collection list` shows what you've got installed; `ansible-doc <collection>.<module>` reads docs for any of them.

### 9.3 Building Your Own Collection

When your team has accumulated enough custom modules, roles, plugins, or filters that copy-paste is hurting, package them as a collection:

```bash
ansible-galaxy collection init mycompany.platform
# scaffolds plugins/, roles/, docs/, galaxy.yml
```

`galaxy.yml` declares the collection's name, version, dependencies, and metadata. `ansible-galaxy collection build` produces a tarball; `ansible-galaxy collection publish` uploads it to Galaxy or your Automation Hub.

References: [Collections overview](https://docs.ansible.com/ansible/latest/collections_guide/index.html), [Developing collections](https://docs.ansible.com/ansible/latest/dev_guide/developing_collections.html).

---

## Phase 10: Testing

### 10.1 The Honest Reality

Testing config management is harder than testing application code. The thing you're testing — a real machine's state — is messy, slow to stand up, and depends on the OS, the kernel, and what the user did last week. Three useful tiers:

1. **Lint** — `ansible-lint`. Catches most stylistic and obvious-correctness issues. Fast. Run in CI.
2. **Check mode + diff** — `ansible-playbook --check --diff`. Catches drift between intent and reality. Doesn't catch logic bugs that depend on runtime values.
3. **Real runs in disposable environments** — Molecule (or just `vagrant up` and `ansible-playbook`). The only way to actually test idempotency, error handling, and integration.

There's no equivalent of pytest for Ansible that gives you full confidence without spinning up real (or container-real) machines.

### 10.2 ansible-lint

```bash
pipx install ansible-lint
ansible-lint .
```

Out-of-the-box it enforces hundreds of rules from the Ansible community style guide — name your tasks, prefer FQCN module names, no hardcoded `sudo`, no shell when command will do, etc. Configure via `.ansible-lint`:

```yaml
profile: production    # or 'basic', 'safety', 'shared'
exclude_paths:
  - .cache/
  - vendor/
skip_list:
  - role-name           # we don't follow that convention
warn_list:
  - experimental
```

The `profile: production` profile is the strictest and what you want before merging code.

### 10.3 Molecule

Molecule is the standard test harness for Ansible roles. It stands up a fresh ephemeral environment (Docker by default; can be Podman, Vagrant, EC2, etc.), runs the role, runs your verification, and tears it all down.

Layout:

```
roles/nginx/
  molecule/
    default/
      molecule.yml      # scenario config
      converge.yml      # the playbook to run (usually just the role)
      verify.yml        # post-run assertions
      requirements.yml  # collections/roles needed for the test
```

`molecule.yml`:

```yaml
dependency:
  name: galaxy
driver:
  name: docker
platforms:
  - name: ubuntu2404
    image: geerlingguy/docker-ubuntu2404-ansible
    pre_build_image: true
    privileged: true
    cgroupns_mode: host
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    command: /lib/systemd/systemd
provisioner:
  name: ansible
verifier:
  name: ansible
scenario:
  test_sequence:
    - destroy
    - syntax
    - create
    - prepare
    - converge
    - idempotence
    - verify
    - destroy
```

```bash
molecule test       # full lifecycle: create → converge → idempotence → verify → destroy
molecule converge   # just run the playbook against the standing instance
molecule login      # SSH into the test box for debugging
```

The `idempotence` step is the cheap, high-value test: Molecule runs the playbook *twice* and fails if the second run reports any changes. If your role isn't idempotent, this surfaces it instantly.

References: [Molecule documentation](https://ansible.readthedocs.io/projects/molecule/), [ansible-lint rules](https://ansible.readthedocs.io/projects/lint/rules/).

### 10.4 Idempotency Testing as the Cheap Win

Even without Molecule, you can run `ansible-playbook site.yml` twice in a row in a sandbox and fail CI if the second run reports any `changed: > 0`. This catches the most common class of bugs — accidentally using `shell` without `changed_when`, modules whose state semantics you misunderstood, templates that produce different output run-to-run.

If you do nothing else for testing, do this.

---

## Phase 11: Production Patterns

### 11.1 Rolling Deploys with `serial`

The pattern: take a fraction of hosts out of the load balancer, deploy to them, health-check, return them, move to the next fraction.

```yaml
- hosts: webservers
  serial: "20%"
  max_fail_percentage: 0
  pre_tasks:
    - name: Drain from load balancer
      community.aws.elb_target:
        target_group_arn: "{{ tg_arn }}"
        target_id: "{{ instance_id }}"
        state: absent
      delegate_to: localhost

    - name: Wait for connections to drain
      ansible.builtin.wait_for:
        port: 8080
        state: drained
        timeout: 60

  roles:
    - app

  post_tasks:
    - name: Health check
      ansible.builtin.uri:
        url: "http://{{ inventory_hostname }}:8080/health"
        status_code: 200
      retries: 30
      delay: 2

    - name: Re-add to load balancer
      community.aws.elb_target:
        target_group_arn: "{{ tg_arn }}"
        target_id: "{{ instance_id }}"
        state: present
      delegate_to: localhost
```

`serial: "20%"` does 20% of hosts at a time. `max_fail_percentage: 0` means any failure halts. The canary variant is `serial: [1, "10%", "50%"]` — first one host alone, then 10%, then 50%, then the rest.

### 11.2 `delegate_to` and `run_once`

`delegate_to: localhost` runs a task on the *control node* instead of the target. Essential for talking to APIs (load balancers, DNS, monitoring) that aren't on the target host.

```yaml
- name: Update DNS to point at the new host
  community.aws.route53:
    state: present
    zone: example.com
    record: "{{ inventory_hostname }}"
    type: A
    value: "{{ ansible_facts.default_ipv4.address }}"
  delegate_to: localhost
```

`run_once: true` means the task runs only once for the whole play, regardless of how many hosts are targeted. Useful for migrations:

```yaml
- name: Run DB migration
  ansible.builtin.command: /opt/app/bin/migrate
  run_once: true
  delegate_to: "{{ groups['dbservers'][0] }}"
```

### 11.3 Async Tasks for Long Operations

By default Ansible holds the SSH connection for the entire duration of a task. For long tasks, this is wasteful (and risks the SSH session dying). `async` + `poll` decouples:

```yaml
- name: Long-running build
  ansible.builtin.command: /opt/build.sh
  async: 3600       # let it run up to 1 hour
  poll: 10          # check every 10s

# or fire-and-forget:
- name: Kick off a backup
  ansible.builtin.command: /opt/backup.sh
  async: 7200
  poll: 0           # don't wait — task ID is saved
  register: backup_job

- name: Other work...

- name: Check backup status later
  ansible.builtin.async_status:
    jid: "{{ backup_job.ansible_job_id }}"
  register: result
  until: result.finished
  retries: 60
  delay: 30
```

### 11.4 `wait_for` and Orchestration

`wait_for` blocks until a condition holds. Cheap orchestration primitive:

```yaml
- name: Wait for service to come up
  ansible.builtin.wait_for:
    port: 5432
    host: "{{ inventory_hostname }}"
    timeout: 120

- name: Wait for a file to be written
  ansible.builtin.wait_for:
    path: /var/run/app.pid
    state: present

- name: Wait for SSH after reboot
  ansible.builtin.wait_for_connection:
    timeout: 600
```

`wait_for_connection` is for re-establishing Ansible's own connection (after a reboot, package update of OpenSSH, etc.).

### 11.5 `pause`, `meta: end_play`, `meta: end_host`

`pause` interactively prompts the operator (or just waits N seconds):

```yaml
- name: Confirm
  ansible.builtin.pause:
    prompt: "Inspect host then press Enter to continue"

- name: Wait 30s
  ansible.builtin.pause:
    seconds: 30
```

`meta: end_play` stops the play immediately for *all* hosts; `meta: end_host` stops only the current host:

```yaml
- name: Maintenance flag check
  ansible.builtin.stat:
    path: /etc/no-deploy
  register: flag

- ansible.builtin.meta: end_host
  when: flag.stat.exists
```

### 11.6 Callback Plugins for Output

The default `default` callback is fine for interactive use; for CI you usually want:

- `yaml` — readable, structured.
- `json` — machine-parseable.
- `oneline` — one line per task, for big runs.
- `profile_tasks` — timing per task; surface slow ones.
- `timer` — total runtime.
- `community.general.slack`, `community.general.pagerduty`, `community.general.mail` — send notifications.

```ini
[defaults]
stdout_callback = yaml
callbacks_enabled = profile_tasks,timer,community.general.slack
```

The `profile_tasks` callback is genuinely worth always running — it tells you which tasks are slow, which is the first step to making the playbook faster.

References: [Callback plugins](https://docs.ansible.com/ansible/latest/plugins/callback.html), [Strategies for rolling updates](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_delegation.html).

```quiz
Q: A play targets 50 webservers with `serial: "20%"` and `max_fail_percentage: 0`. What does this combination do?
- [ ] Deploys to all 50 at once but tolerates 20% failures
- [x] Deploys 10 hosts at a time and halts the whole rollout if any host in a batch fails
- [ ] Deploys to one host, then all remaining 49
- [ ] Runs the play 20% faster by skipping fact gathering
> `serial: "20%"` processes the fleet in batches of 10 (20% of 50), and `max_fail_percentage: 0` means a single failure in a batch stops the rollout before it touches the next batch. That's the core safety property of a rolling deploy: you blast-radius-limit a bad release to one batch instead of the whole fleet. A canary variant like `serial: [1, "10%", "50%"]` starts even smaller.

Q: You need to run a database migration exactly once even though the play targets all dbservers. Which directive expresses that?
- [ ] `serial: 1`
- [ ] `delegate_to: localhost`
- [x] `run_once: true` (typically with `delegate_to` to pin the host)
- [ ] `gather_facts: false`
> `run_once: true` makes a task execute a single time for the whole play regardless of how many hosts are targeted, which is exactly what a migration needs — running it per host would corrupt the database. `serial: 1` only changes batch size (it would still run once per host), and `delegate_to` alone just changes *where* a task runs, not how many times.

Q: Why does `delegate_to: localhost` matter for the load-balancer drain/re-add tasks in a rolling deploy?
- [ ] It makes the task idempotent automatically
- [ ] It runs the task as root on the target
- [x] The LB API call must originate from a host that can reach the API — the control node — not from the target being drained
- [ ] It caches the API response for the rest of the play
> Tasks that talk to external APIs (load balancers, DNS, monitoring) shouldn't run *on* the host being deployed — that host may be drained, restarting, or unable to reach the control plane. `delegate_to: localhost` runs the task on the control node while still iterating per target host, so the drain/health-check/re-add dance works even as the target goes in and out of rotation.
```

---

## Phase 12: Ansible vs. The Alternatives

The interview question and the architecture-meeting question: when do you use Ansible, when do you use something else? Honest, opinionated answers.

### 12.1 Ansible vs. Terraform

Different tools, different jobs. The honest summary in one sentence: **Terraform creates the resource; Ansible configures it**. See [TERRAFORM_STUDY_GUIDE.md](TERRAFORM_STUDY_GUIDE.md) for the depth.

| Aspect | Terraform | Ansible |
|---|---|---|
| Mental model | Declarative — desired end state | Imperative-feeling, declarative-by-convention |
| State | Required, central, locked | None — state lives on the target machine |
| Sweet spot | Cloud APIs, infrastructure | OS, packages, files, services |
| Idempotency | Provider-level | Module-level |
| Day-2 ops | Plan and apply | Targeted runs, ad-hoc, orchestration |
| Drift detection | First-class (`terraform plan`) | Check mode (`--check --diff`), incomplete |
| Dependency model | Resource graph | Linear task order |
| Plays well with | Pulumi, CDK as siblings | Terraform (sequential or via inventory plugins) |

In any real shop, you have both. Terraform stands up the VM; Ansible configures it. Terraform writes the EC2 tags; the Ansible `aws_ec2` inventory plugin reads them. The integration is messy in detail but conceptually clean: Terraform owns "what infrastructure exists"; Ansible owns "what's inside the boxes."

The anti-pattern: trying to do OS configuration in Terraform via `remote-exec` and `local-exec` provisioners. HashiCorp themselves [recommend against it](https://developer.hashicorp.com/terraform/language/v1.1.x/resources/provisioners/syntax). Use the right tool.

### 12.2 Ansible vs. Puppet / Chef

| Aspect | Ansible | Puppet | Chef |
|---|---|---|---|
| Architecture | Push, agentless | Pull, agent | Pull, agent (Chef Solo: agentless) |
| Language | YAML + Jinja2 | Puppet DSL (declarative) | Ruby DSL (procedural-ish) |
| Default mode | Trigger-driven | Continuous (every 30 min) | Continuous |
| Scale (10k+ nodes) | Painful (mitigated by AWX + mitogen) | First-class | First-class |
| Onboarding | Hours | Days | Days |
| Drift correction | When you run it | Automatic | Automatic |

Puppet wins for huge fleets where you want continuous convergence. Chef has a strong dev/test story (test-kitchen, InSpec). Both have steeper learning curves than Ansible.

The trend over the past five years: Ansible has eaten most of the new config-management market because the agentless model + YAML is just easier to onboard onto. Puppet and Chef still dominate big legacy fleets (especially regulated industries that already invested).

### 12.3 Ansible vs. SaltStack

Salt is technically excellent and operationally heavier. Architecturally similar to Puppet (pull-ish, agent-based via the `salt-minion`) but with a ZeroMQ transport that lets it scale to *enormous* fleets — tens of thousands of nodes — with much better performance than Ansible at that scale.

If you have 5,000+ machines and full control over what you install on them, Salt is faster than Ansible. If you have 500 machines and a team of generalists, Ansible is easier. Salt also supports an agentless `salt-ssh` mode that brings it closer to Ansible's operational model, but it's not the primary path.

### 12.4 Ansible vs. cloud-init

[cloud-init](https://cloudinit.readthedocs.io/) is what runs on a fresh cloud VM the first time it boots, configured via the instance's user-data. It can install packages, write files, add users, run scripts.

cloud-init is *better* than Ansible for:
- The bootstrap moment, before Ansible can connect.
- Setting up the SSH key Ansible will use.
- Installing Python so Ansible can run.
- One-time provisioning concerns.

Ansible is better for everything *after* bootstrap. The typical pattern: cloud-init does the absolute minimum (set hostname, install Python, drop an SSH key); Ansible takes over from there.

For purely immutable infrastructure (Packer-baked AMIs deployed via autoscaling), cloud-init or a Packer-time Ansible run is enough — you don't need Ansible at runtime at all.

### 12.5 The Honest Answer

The right answer is almost always **"both Terraform and Ansible, for different things."** Terraform for cloud resources. Ansible for OS configuration and orchestration. Packer (often using Ansible as its provisioner) when you want immutable images. cloud-init for the absolute first-boot moment.

The wrong answer is "one tool for everything." Every team that tries to do all infrastructure in Ansible (or all configuration in Terraform) ends up with grotesque hacks. Pick the right tool per layer.

---

## Phase 13: Performance and Scale

### 13.1 SSH Pipelining and `ControlPersist`

SSH pipelining (covered in Phase 1.6) is the cheapest 30–50% speedup you'll find. Combine it with SSH multiplexing:

```ini
[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
```

`ControlPersist` keeps the SSH master socket alive for 60s after the last channel closes; subsequent tasks reuse it. Massive savings on plays with many small tasks per host.

### 13.2 The `mitogen` Strategy Plugin

[Mitogen for Ansible](https://mitogen.networkgenomics.com/ansible_detailed.html) is a drop-in execution-strategy plugin that replaces Ansible's "run a fresh Python on every task" model with a persistent Python process per target. The result is often **2–7× faster** on plays with many tasks.

```ini
[defaults]
strategy_plugins = /path/to/mitogen/ansible_mitogen/plugins/strategy
strategy = mitogen_linear
```

The cost: Mitogen development pace has slowed; check compatibility against your Ansible version before relying on it. For very fact-heavy or task-heavy playbooks against 100s of hosts, it remains the single largest speedup you can apply.

### 13.3 Fact Caching

By default Ansible re-runs `setup` on every host at the start of every play. Caching avoids this:

```ini
[defaults]
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 7200
```

`smart` gathering means "use the cache if fresh, gather if not." Drivers include `jsonfile` (local), `redis`, `memcached`, `mongodb`. For team workflows with shared facts (e.g., AWX), use Redis.

`gather_subset` lets you trim what's collected: `gather_subset: '!all,!min,network,virtual'` skips hardware details if you don't need them.

### 13.4 `forks` and Batching

Raise `forks` to 25–50 for production fleets. The limit is your control node's CPU + open-FD ceiling and the targets' SSH connection limits (`MaxStartups`, `MaxSessions` in sshd_config). Above ~100 forks you start hitting SSH server defaults; tune both ends if you go higher.

For 1,000+ host fleets, batching with `serial` and an external job-runner (AWX, Tower, GitLab CI matrix jobs) is usually saner than just cranking forks.

### 13.5 When AWX / Ansible Automation Platform Earns Its Keep

You should consider AWX (open source) or Ansible Automation Platform (Red Hat's commercial offering) when:

- More than one human runs playbooks regularly and you need an audit trail.
- You want RBAC: developers can run *some* playbooks against *some* inventories.
- You want scheduled runs (rotate certs every Sunday).
- You want self-service for non-Ansible users via *surveys* (web forms that fill in extra-vars).
- You want centralized inventory, credentials, and notifications.
- You want to delegate workload across multiple control nodes (*execution environments*, *isolated nodes*).

For solo work or small teams running playbooks from their laptops and CI, AWX is overkill. The break-even is somewhere around "5+ engineers regularly run playbooks" or "we need an audit trail for compliance."

References: [AWX](https://github.com/ansible/awx), [Ansible Automation Platform](https://www.redhat.com/en/technologies/management/ansible), [Semaphore](https://semaphoreui.com/) (the lighter-weight community alternative).

```quiz
Q: Why does enabling SSH pipelining give a 30–50% speedup with no behavioral change?
- [ ] It compresses module output over the wire
- [x] It cuts the number of SSH operations per task by avoiding writing modules to a temp file on the target
- [ ] It runs tasks in parallel across hosts
- [ ] It caches facts between runs
> Without pipelining, each task transfers the module to a temp file on the target, executes it, then cleans up — several SSH round trips per task. Pipelining streams the module straight to the remote Python interpreter over the existing connection, roughly halving SSH operations. It's behavior-neutral; the only prerequisite is that `requiretty` is off in sudoers, which it usually already is.

Q: What is the fundamental thing the `mitogen` strategy plugin changes to get 2–7× speedups?
- [ ] It rewrites your playbook into compiled bytecode
- [ ] It increases `forks` automatically
- [x] It replaces "fresh Python per task" with a persistent Python process per target
- [ ] It disables fact gathering
> Stock Ansible starts a new Python interpreter on the target for every task, which dominates runtime on task-heavy plays. Mitogen keeps a persistent interpreter per host and routes calls to it, eliminating that per-task startup cost. The tradeoff is that Mitogen's development has slowed, so you must verify compatibility with your Ansible version before depending on it.

Q: With `gathering = smart` and fact caching configured, when does Ansible actually re-run the `setup` module?
- [ ] On every play, ignoring the cache
- [ ] Never, until you manually clear the cache
- [x] Only when the cached facts for a host are missing or stale past the timeout
- [ ] Only on the first host in each batch
> `smart` gathering means "use the cache if it's fresh, otherwise gather and refresh it." Fact gathering costs 1–3 seconds per host, so caching (jsonfile locally, Redis for shared/AWX setups) eliminates that cost on repeat runs while still picking up changes once the `fact_caching_timeout` expires. That's the cheap structural win before you reach for forks or mitogen.
```

---

## Phase 14: A Real Role — `nginx`

Enough theory. Here's a complete, working role for installing and configuring nginx on Ubuntu. Read it as the model for how a production role is shaped.

### 14.1 Directory Layout

```
roles/nginx/
  defaults/main.yml
  vars/main.yml
  tasks/main.yml
  tasks/install.yml
  tasks/configure.yml
  tasks/sites.yml
  handlers/main.yml
  templates/nginx.conf.j2
  templates/site.conf.j2
  files/dhparam.pem
  meta/main.yml
  molecule/default/converge.yml
  molecule/default/molecule.yml
  README.md
```

### 14.2 `defaults/main.yml`

Defaults are values consumers may override. Keep them realistic.

```yaml
nginx_user: www-data
nginx_worker_processes: auto
nginx_worker_connections: 1024
nginx_keepalive_timeout: 65
nginx_client_max_body_size: 1m
nginx_gzip: true
nginx_log_format: combined

nginx_sites: []     # list of dicts: see README
nginx_remove_default_site: true

nginx_apt_packages:
  - nginx
  - nginx-extras

nginx_service_state: started
nginx_service_enabled: true
```

### 14.3 `vars/main.yml`

Values you don't want callers to override (path constants, OS specifics):

```yaml
nginx_conf_path: /etc/nginx/nginx.conf
nginx_sites_available: /etc/nginx/sites-available
nginx_sites_enabled: /etc/nginx/sites-enabled
nginx_log_dir: /var/log/nginx
```

### 14.4 `tasks/main.yml`

```yaml
- name: Install nginx
  ansible.builtin.import_tasks: install.yml
  tags: [nginx, install]

- name: Configure nginx
  ansible.builtin.import_tasks: configure.yml
  tags: [nginx, configure]

- name: Manage sites
  ansible.builtin.import_tasks: sites.yml
  tags: [nginx, sites]

- name: Ensure nginx service
  ansible.builtin.systemd:
    name: nginx
    state: "{{ nginx_service_state }}"
    enabled: "{{ nginx_service_enabled }}"
  tags: [nginx, service]
```

### 14.5 `tasks/install.yml`

```yaml
- name: Install apt packages
  ansible.builtin.apt:
    name: "{{ nginx_apt_packages }}"
    state: present
    update_cache: true
    cache_valid_time: 3600
  become: true
```

### 14.6 `tasks/configure.yml`

```yaml
- name: Ensure nginx log directory
  ansible.builtin.file:
    path: "{{ nginx_log_dir }}"
    state: directory
    owner: "{{ nginx_user }}"
    group: adm
    mode: "0750"
  become: true

- name: Copy DH params for TLS
  ansible.builtin.copy:
    src: dhparam.pem
    dest: /etc/nginx/dhparam.pem
    owner: root
    group: root
    mode: "0644"
  become: true

- name: Render main nginx.conf
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: "{{ nginx_conf_path }}"
    owner: root
    group: root
    mode: "0644"
    validate: nginx -t -c %s
    backup: true
  become: true
  notify: Reload nginx
```

### 14.7 `tasks/sites.yml`

```yaml
- name: Remove default site
  ansible.builtin.file:
    path: "{{ nginx_sites_enabled }}/default"
    state: absent
  become: true
  when: nginx_remove_default_site | bool
  notify: Reload nginx

- name: Render per-site configs
  ansible.builtin.template:
    src: site.conf.j2
    dest: "{{ nginx_sites_available }}/{{ item.name }}.conf"
    owner: root
    group: root
    mode: "0644"
    validate: nginx -t -c /etc/nginx/nginx.conf
  become: true
  loop: "{{ nginx_sites }}"
  loop_control:
    label: "{{ item.name }}"
  notify: Reload nginx

- name: Enable sites
  ansible.builtin.file:
    src: "{{ nginx_sites_available }}/{{ item.name }}.conf"
    dest: "{{ nginx_sites_enabled }}/{{ item.name }}.conf"
    state: link
  become: true
  loop: "{{ nginx_sites }}"
  loop_control:
    label: "{{ item.name }}"
  when: item.enabled | default(true) | bool
  notify: Reload nginx
```

### 14.8 `handlers/main.yml`

```yaml
- name: Reload nginx
  ansible.builtin.systemd:
    name: nginx
    state: reloaded
  become: true

- name: Restart nginx
  ansible.builtin.systemd:
    name: nginx
    state: restarted
  become: true
```

### 14.9 `templates/site.conf.j2`

```jinja2
# {{ ansible_managed }}
server {
    listen 80;
    server_name {{ item.server_name }};

{% if item.redirect_https | default(true) %}
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name {{ item.server_name }};

    ssl_certificate     {{ item.ssl_cert }};
    ssl_certificate_key {{ item.ssl_key }};
    ssl_dhparam         /etc/nginx/dhparam.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
{% endif %}

    root {{ item.root | default('/var/www/html') }};
    access_log {{ nginx_log_dir }}/{{ item.name }}.access.log;
    error_log  {{ nginx_log_dir }}/{{ item.name }}.error.log;

    client_max_body_size {{ item.client_max_body_size | default(nginx_client_max_body_size) }};

{% for loc in item.locations | default([]) %}
    location {{ loc.path }} {
{%   for k, v in loc.directives.items() %}
        {{ k }} {{ v }};
{%   endfor %}
    }
{% endfor %}
}
```

### 14.10 Consumer Usage

```yaml
- hosts: webservers
  become: true
  roles:
    - role: nginx
      vars:
        nginx_worker_processes: 4
        nginx_sites:
          - name: api
            server_name: api.example.com
            ssl_cert: /etc/letsencrypt/live/api.example.com/fullchain.pem
            ssl_key:  /etc/letsencrypt/live/api.example.com/privkey.pem
            locations:
              - path: /
                directives:
                  proxy_pass: http://127.0.0.1:8080
                  proxy_set_header: "Host $host"
```

This is what a production role looks like: thin task files, fat templates, no surprises, `validate` everywhere, handlers for restarts. Everything overridable by consumers; nothing hidden.

---

## Phase 15: A Real Deploy — Rolling Updates with Health Checks and Rollback

A common job: deploy a new application version to a fleet of webservers behind a load balancer, with health checks and rollback on failure.

### 15.1 The Playbook

```yaml
- name: Deploy app
  hosts: webservers
  become: true
  serial: "25%"
  max_fail_percentage: 0

  vars:
    app_repo: git@github.com:example/app.git
    app_version: "{{ app_version | mandatory }}"
    app_release_dir: "/opt/app/releases/{{ app_version }}"
    app_current_link: /opt/app/current
    app_service: app

  pre_tasks:
    - name: Record current release for rollback
      ansible.builtin.command: readlink -f {{ app_current_link }}
      register: previous_release
      changed_when: false
      failed_when: false

    - name: Drain from target group
      community.aws.elb_target:
        target_group_arn: "{{ tg_arn }}"
        target_id: "{{ ec2_instance_id }}"
        state: absent
      delegate_to: localhost

    - name: Wait for in-flight requests to finish
      ansible.builtin.wait_for:
        port: 8080
        state: drained
        timeout: 60

  tasks:
    - block:
        - name: Check out release
          ansible.builtin.git:
            repo: "{{ app_repo }}"
            dest: "{{ app_release_dir }}"
            version: "{{ app_version }}"
            depth: 1

        - name: Install dependencies
          ansible.builtin.command: /opt/app/bin/install.sh
          args:
            chdir: "{{ app_release_dir }}"
            creates: "{{ app_release_dir }}/.deps_installed"

        - name: Render env file
          ansible.builtin.template:
            src: app.env.j2
            dest: "{{ app_release_dir }}/.env"
            owner: app
            group: app
            mode: "0600"

        - name: Switch the current symlink
          ansible.builtin.file:
            src: "{{ app_release_dir }}"
            dest: "{{ app_current_link }}"
            state: link
            force: true

        - name: Restart app
          ansible.builtin.systemd:
            name: "{{ app_service }}"
            state: restarted

        - name: Local health check
          ansible.builtin.uri:
            url: "http://127.0.0.1:8080/health"
            status_code: 200
          retries: 30
          delay: 2
          register: health
          until: health.status == 200

      rescue:
        - name: Rollback symlink
          ansible.builtin.file:
            src: "{{ previous_release.stdout }}"
            dest: "{{ app_current_link }}"
            state: link
            force: true
          when: previous_release.stdout | length > 0

        - name: Restart app on previous version
          ansible.builtin.systemd:
            name: "{{ app_service }}"
            state: restarted

        - name: Fail loudly
          ansible.builtin.fail:
            msg: "Deploy of {{ app_version }} on {{ inventory_hostname }} failed — rolled back to {{ previous_release.stdout }}"

  post_tasks:
    - name: Add back to target group
      community.aws.elb_target:
        target_group_arn: "{{ tg_arn }}"
        target_id: "{{ ec2_instance_id }}"
        state: present
      delegate_to: localhost

    - name: Wait for healthy in target group
      community.aws.elb_target_info:
        target_group_arn: "{{ tg_arn }}"
        target_id: "{{ ec2_instance_id }}"
      register: tg
      until: tg.target_health_descriptions[0].target_health.state == 'healthy'
      retries: 30
      delay: 5
      delegate_to: localhost

    - name: Prune old releases
      ansible.builtin.shell: |
        ls -1dt /opt/app/releases/*/ | tail -n +6 | xargs -r rm -rf
      changed_when: false
```

### 15.2 What's Going On

- **`serial: "25%"`** — quarter of the fleet at a time. Combined with `max_fail_percentage: 0`, any host failure halts the deploy.
- **Pre-task drain** — out of the LB before touching the box. `wait_for` with `state: drained` is the rare module that watches for *connections* to fall to zero, not just port closure.
- **`block` / `rescue`** — if anything inside the block fails, roll back the symlink. Then `fail` to surface the error.
- **`creates: .deps_installed`** — cheap idempotency guard on a `command` task.
- **Symlink swap** — the actual deploy moment. Atomic, instant, easy to roll back.
- **Local health check** — `uri` with retries against `127.0.0.1`. Proves the new code is running.
- **Post-task re-add to LB** — and *wait* for the LB to mark it healthy before we move to the next batch.
- **Prune old releases** — keep the last 5. Standard housekeeping.

### 15.3 What's Not in This Playbook (and Why)

- **Database migrations** — should run *once*, before the deploy, against a single host. A separate play with `run_once: true` and `delegate_to: groups['dbservers'][0]`.
- **Cache warm-up** — depends on your app. Could live in `post_tasks`.
- **Slack notifications** — fold in via callback plugin (`community.general.slack`) so every play reports.
- **Cleanup of orphaned releases on rollback** — left intentionally; rollback's release is the *previous* directory, which is still on disk. Pruning happens only on successful deploy.

---

## Phase 16: Common Patterns Cookbook

### 16.1 Provisioning a Fresh Ubuntu Box

The "what you do to every new server" play. Run right after Terraform stands the box up.

```yaml
- hosts: new_hosts
  become: true
  gather_facts: false
  pre_tasks:
    - name: Wait for SSH
      ansible.builtin.wait_for_connection:
        timeout: 300
    - name: Ensure Python is installed (raw — no facts yet)
      ansible.builtin.raw: |
        if ! command -v python3 >/dev/null; then
          apt-get update && apt-get install -y python3
        fi
      changed_when: false
    - name: Now gather facts
      ansible.builtin.setup:

  tasks:
    - name: Set hostname
      ansible.builtin.hostname:
        name: "{{ inventory_hostname_short }}"

    - name: Set timezone
      community.general.timezone:
        name: UTC

    - name: Upgrade base packages
      ansible.builtin.apt:
        upgrade: safe
        update_cache: true
        cache_valid_time: 3600

    - name: Install base toolchain
      ansible.builtin.apt:
        name:
          - curl
          - wget
          - git
          - htop
          - jq
          - unattended-upgrades
          - ufw
          - fail2ban
        state: present

    - name: Configure unattended upgrades
      ansible.builtin.copy:
        content: |
          APT::Periodic::Update-Package-Lists "1";
          APT::Periodic::Unattended-Upgrade "1";
        dest: /etc/apt/apt.conf.d/20auto-upgrades

    - name: Configure firewall
      community.general.ufw:
        state: enabled
        policy: deny
        direction: incoming

    - name: Allow SSH
      community.general.ufw:
        rule: allow
        port: "22"
        proto: tcp
```

### 16.2 Idempotent User and Group Management

```yaml
- name: Manage groups
  ansible.builtin.group:
    name: "{{ item }}"
    state: present
  loop: [deploy, developers, ops]

- name: Manage users
  ansible.builtin.user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
    append: true
    shell: /bin/bash
    state: present
    password: "{{ item.password | password_hash('sha512') }}"
  loop:
    - { name: alice, groups: [developers, deploy], password: "{{ vault_alice_pwd }}" }
    - { name: bob,   groups: [developers],        password: "{{ vault_bob_pwd }}" }
  loop_control:
    label: "{{ item.name }}"
  no_log: true       # keep password hashes out of output

- name: Manage authorized SSH keys
  ansible.posix.authorized_key:
    user: "{{ item.name }}"
    key: "{{ lookup('file', 'keys/' + item.name + '.pub') }}"
    state: present
  loop:
    - { name: alice }
    - { name: bob }

- name: Drop sudoers files
  ansible.builtin.copy:
    content: "{{ item.user }} ALL=(ALL) NOPASSWD: {{ item.cmds }}\n"
    dest: "/etc/sudoers.d/{{ item.user }}"
    mode: "0440"
    validate: visudo -cf %s
  loop:
    - { user: deploy, cmds: "/bin/systemctl restart app, /opt/app/bin/migrate" }
```

`no_log: true` on the user-creation loop hides the password hashes. `validate: visudo -cf %s` on sudoers means a broken sudoers file fails the task instead of breaking the system.

### 16.3 Managing Dotfiles for Engineers

```yaml
- hosts: workstations
  tasks:
    - name: Clone dotfiles
      ansible.builtin.git:
        repo: git@github.com:user/dotfiles.git
        dest: "{{ ansible_user_dir }}/.dotfiles"
        version: main
        update: true

    - name: Symlink each dotfile
      ansible.builtin.file:
        src: "{{ ansible_user_dir }}/.dotfiles/{{ item }}"
        dest: "{{ ansible_user_dir }}/.{{ item }}"
        state: link
        force: true
      loop:
        - zshrc
        - vimrc
        - gitconfig
        - tmux.conf
```

### 16.4 Bootstrapping Secrets via Vault Lookup

```yaml
- hosts: all
  vars:
    db_password: "{{ lookup('community.hashi_vault.vault_kv2_get',
                            'secret/data/prod/db',
                            engine_mount_point='kv').data.password }}"
  tasks:
    - name: Render app config with secret
      ansible.builtin.template:
        src: app.env.j2
        dest: /etc/app/env
        mode: "0600"
      no_log: true
```

`lookup` runs on the control node. The secret never lands in playbook source, never gets cached on disk. `no_log: true` hides the rendered content from Ansible's output.

---

## Phase 17: Anatomy of a Production Playbook

A pragmatic walkthrough of what a real, mature Ansible repo looks like for a small-to-medium ops team. Roughly 30 hosts across staging and production, behind AWS ALBs, deploying a Python web app.

### 17.1 The Repo

```
ansible/
  ansible.cfg
  collections/
    requirements.yml
  inventory/
    production/
      aws_ec2.yml
      group_vars/
        all/
          common.yml
          vault.yml             # ansible-vault encrypted
        webservers.yml
        dbservers.yml
      host_vars/
    staging/
      aws_ec2.yml
      group_vars/
        all/
          common.yml
          vault.yml
        webservers.yml
        dbservers.yml
  roles/
    common/         # baseline: users, NTP, monitoring agent, log shipper
    nginx/          # the role from Phase 14
    app/            # deploys the application
    postgres/       # DB cluster
    monitoring/     # node_exporter, journalbeat
  playbooks/
    site.yml        # full convergence — runs everything against everything
    deploy.yml      # the rolling deploy from Phase 15
    bootstrap.yml   # the fresh-box play from Phase 16.1
    rotate-certs.yml
    patch.yml       # apt upgrades + reboot if needed
  Makefile          # documented entrypoints
  .ansible-lint
  .pre-commit-config.yaml
  .github/workflows/ci.yml
  README.md
```

### 17.2 The Choices, Called Out

**Inventory**
- **Dynamic via `aws_ec2`.** Tags drive groups (`role_web`, `role_db`, `env_prod`). No static host lists.
- **Separate inventory directory per environment.** `inventory/production/` and `inventory/staging/` are disjoint. Easier to reason about than workspaces or environment variables; harder to "accidentally run prod commands against staging."

**Variables**
- **`group_vars/all/common.yml`** holds environment-wide values (region, AMI, base domain).
- **`group_vars/all/vault.yml`** is ansible-vault encrypted. Holds the secrets that aren't already in HashiCorp Vault.
- **Role `defaults/`** is heavily populated — every consumer-facing knob has a reasonable default. Roles work out of the box.

**Roles**
- **`common`** runs on every host, applies the baseline. Owns users, sudoers, NTP, monitoring agent, log shipper, firewall.
- **One role per service.** No "big role" anti-pattern.
- **Roles do not depend on each other.** The `site.yml` playbook wires them up, not `meta/main.yml` dependencies.

**Playbooks**
- **`site.yml`** is the "convergence" play. Run weekly; it's safe to re-run.
- **`deploy.yml`** is the rolling app deploy. Run on every release.
- **`bootstrap.yml`** is run once per new host. Cloud-init handles the *absolute* bootstrap; Ansible takes over from `bootstrap.yml` onward.
- **`rotate-certs.yml`**, **`patch.yml`** are scheduled. Run from AWX on a cron.

**Testing**
- `ansible-lint` runs in pre-commit and CI.
- Each role has a `molecule/default/` scenario that boots an Ubuntu Docker container, applies the role, runs `verify.yml`, and checks idempotence.
- The site playbook is *not* tested in CI — too expensive. Tested by re-running against staging weekly.

**Secrets**
- Application secrets live in HashiCorp Vault. Roles pull them at render time via `community.hashi_vault.vault_kv2_get`.
- Bootstrap secrets (the Vault token, the AWS deploy keys) live in `group_vars/all/vault.yml`, ansible-vault encrypted, with the vault password in a file outside the repo, sourced from 1Password.

**Orchestration**
- AWX runs scheduled playbooks (patching, cert rotation, weekly convergence).
- Deploys run from GitHub Actions via `ansible-playbook` invocations.
- Ad-hoc ops work runs from engineers' laptops with the production inventory — read-only by convention, but no technical enforcement (a trade-off accepted for the team size).

### 17.3 The Operational Realities

- **The pager-able playbook**: the deploy. If it fails mid-rolling-update, the alert fires and an engineer rolls back manually or via `--limit` to only the bad hosts.
- **`Makefile` as the entry point**: `make deploy VERSION=v2.3.1`, `make patch ENV=staging`. Engineers never type the full `ansible-playbook` command — they go through `make`, which sets `ANSIBLE_CONFIG`, vault passwords, and the inventory.
- **Drift detection**: `make check ENV=production` runs `ansible-playbook site.yml --check --diff` weekly. Output goes to Slack. Drift is investigated.
- **Audit**: AWX provides the audit log for everything it runs. For laptop-initiated runs, the convention is to post into a `#ops-actions` Slack channel.
- **Onboarding**: an engineer can clone the repo, install ansible-core + collections from `requirements.yml`, and apply a role against staging within their first day.

### 17.4 Why This Architecture

The decisions:

1. **Dynamic inventory** — because hosts change. We tag in Terraform; Ansible reads tags.
2. **One role per service** — composable, reusable, testable.
3. **`site.yml` does everything; `deploy.yml` does just deploys** — separate the "make the box correct" play from the "ship the new version" play. Different cadence, different blast radius.
4. **Secrets in Vault, bootstrap secrets in ansible-vault** — secrets-of-secrets is the only thing in ansible-vault; everything else lives where secrets belong.
5. **AWX for scheduled work, GitHub Actions for deploys** — orchestration tools where they're strong, no monolith.
6. **Molecule per role, no test for the whole site** — economic. We test the units; we test the system in staging.

This shape is not "the right Ansible architecture." It's *an* opinionated answer for a 30-host fleet with a small ops team. A 1,000-host fleet would push harder on AWX, fact caching, and `mitogen`. A heavily compliant environment would tighten RBAC, audit, and the deploy path. The *principles* — separation of inventory and code, roles as units, secrets where they belong, tested idempotency — generalize.

---

## Mastery Checklist

You're solid on Ansible when you can, without looking anything up:

- Explain the agentless/push model and why it requires Python on the target.
- Diff `command`, `shell`, and `raw` and pick the right one (and add the right idempotency guards).
- Build a dynamic AWS / GCP / Azure inventory with keyed groups from tags.
- Reason about variable precedence — where does this value come from, what could shadow it.
- Use `set_fact` and `register` correctly, including `cacheable`.
- Write Jinja2 templates with `default`, `mandatory`, `combine`, `selectattr`, `map('attribute', ...)`.
- Use `ansible-vault` with vault IDs, and explain when to use Vault lookups instead.
- Lay out a role with `defaults`, `vars`, `tasks`, `handlers`, `templates`, `files`, `meta`.
- Choose between `roles:`, `import_role`, and `include_role` and justify the choice.
- Use blocks with `rescue` and `always` for transactional groups of tasks.
- Write a rolling-deploy playbook with `serial`, `max_fail_percentage`, drain, health-check, re-add.
- Use `delegate_to`, `run_once`, `async`, `wait_for`, `wait_for_connection` correctly.
- Explain `linear` vs. `free` strategy and when each makes sense.
- Tune Ansible for performance: SSH pipelining, `ControlPersist`, fact caching, `mitogen`, forks.
- Articulate when AWX/AAP earns its keep vs. running from a laptop.
- Stand up a Molecule scenario that tests a role's idempotence in Docker.
- Articulate Ansible vs. Terraform vs. Puppet vs. Salt vs. cloud-init — when each wins, when each loses.
- Pick the right `validate` command for nginx, sshd, sudoers, named.
- Read `ansible-playbook -vvv` output and diagnose an SSH or module failure.
- Write an `ansible.cfg` with the settings that matter (forks, pipelining, fact_caching, callbacks).

---

## Recommended Reading Path

1. **[Ansible documentation](https://docs.ansible.com/ansible/latest/)** — start with the *User Guide*, then *Collections Guide*, then *Developer Guide*. The official docs are unusually good.
2. **[Ansible for DevOps](https://www.ansiblefordevops.com/)** (Jeff Geerling) — the canonical practitioner book. Read it cover to cover; it teaches the *why* more than the *what*.
3. **[Ansible 101 on YouTube](https://www.youtube.com/playlist?list=PL2_OBreMn7FqZkvMYt6ATmgC0KAGGJNAN)** (Jeff Geerling) — free video companion to the book.
4. **[Jeff Geerling's blog](https://www.jeffgeerling.com/blog)** — practical posts on real problems, the `geerlingguy.*` Galaxy roles as reference examples.
5. **[ansible-lint rules](https://ansible.readthedocs.io/projects/lint/rules/)** — read every rule. They encode hard-won community conventions.
6. **[Molecule documentation](https://ansible.readthedocs.io/projects/molecule/)** — the testing harness.
7. **[Ansible Galaxy](https://galaxy.ansible.com/)** — browse the high-quality collections (`amazon.aws`, `community.general`, `kubernetes.core`) and read their source. The best way to learn idiomatic Ansible is to read it.
8. **[The Ansible Mailing List Archives](https://groups.google.com/g/ansible-project)** and **[Reddit r/ansible](https://www.reddit.com/r/ansible/)** — for when the docs don't cover the edge case you've hit.
9. **[HashiCorp Vault + Ansible](https://www.hashicorp.com/blog/managing-secrets-with-vault-and-ansible)** — when ansible-vault stops being enough.
10. **[Mitogen for Ansible](https://mitogen.networkgenomics.com/ansible_detailed.html)** — read when you have a slow playbook and need the speedup.

**Adjacent guides in this repo:** [Linux Fundamentals](LINUX_FUNDAMENTALS_STUDY_GUIDE.md) (the systems Ansible configures), [Terraform](TERRAFORM_STUDY_GUIDE.md) (provisioning vs configuration — the boundary worth getting right), [Docker](DOCKER_STUDY_GUIDE.md), and [GitHub Actions](GITHUB_ACTIONS_STUDY_GUIDE.md) (running playbooks in CI).

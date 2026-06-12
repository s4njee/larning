# Linux Networking Study Guide

A practical, command-line-first guide to Linux networking for engineers who need to debug real machines, containers, VMs, lab boxes, and production hosts. The [Networking Fundamentals guide](NETWORKING_FUNDAMENTALS.md) explains the protocols; this guide is about operating the Linux network stack with modern tools: `ip`, `ss`, `nc`/netcat, `iperf3`, namespaces, routes, sockets, and file-transfer workflows.

The thesis: **Linux networking becomes manageable when you think in kernel objects.** Interfaces, addresses, routes, neighbors, sockets, namespaces, firewall rules, and queues are all inspectable. The job is to ask the kernel the right question.

Primary references: the iproute2 [`ip(8)` manual](https://manpages.debian.org/bookworm/iproute2/ip.8.en.html), the iproute2 [`ss(8)` manual](https://man7.org/linux/man-pages/man8/ss.8.html), the OpenBSD [`nc(1)` manual](https://man.openbsd.org/nc.1), [iperf3 documentation](https://software.es.net/iperf/), the OpenSSH [`scp(1)` manual](https://man7.org/linux/man-pages/man1/scp.1.html), [OpenSSH release notes](https://www.openssh.org/releasenotes.html), [rsync upstream](https://rsync.samba.org/), and the [GNU tar manual](https://www.gnu.org/software/tar/manual/tar.html).

---

## Table of Contents

1. [Part 1 - The Linux Network Mental Model](#part-1-the-linux-network-mental-model)
2. [Part 2 - Lab Setup and Safety](#part-2-lab-setup-and-safety)
3. [Part 3 - Interfaces, Addresses, and Links with ip](#part-3-interfaces-addresses-and-links-with-ip)
4. [Part 4 - Routes, Rules, and Neighbors](#part-4-routes-rules-and-neighbors)
5. [Part 5 - Sockets and Services with ss](#part-5-sockets-and-services-with-ss)
6. [Part 6 - Netcat for Real Debugging](#part-6-netcat-for-real-debugging)
7. [Part 7 - Measuring Throughput with iperf3](#part-7-measuring-throughput-with-iperf3)
8. [Part 8 - Network Namespaces and veth Labs](#part-8-network-namespaces-and-veth-labs)
9. [Part 9 - Practical Troubleshooting Playbooks](#part-9-practical-troubleshooting-playbooks)
10. [Part 10 - File Transfer Cookbook](#part-10-file-transfer-cookbook)
11. [Part 11 - Tool Cheat Sheets](#part-11-tool-cheat-sheets)

---

## Part 1 - The Linux Network Mental Model

Modern Linux networking is not a pile of magic commands. It is a set of kernel objects:

| Object | What it means | Main tools |
|---|---|---|
| Link/interface | A network endpoint: physical NIC, loopback, veth, bridge, bond, VLAN, tunnel | `ip link`, `ethtool` |
| Address | An IPv4/IPv6 address assigned to an interface | `ip addr` |
| Route | A decision about where packets go next | `ip route` |
| Rule | A policy-routing selector before the route table lookup | `ip rule` |
| Neighbor | ARP/NDP cache entry: IP address -> link-layer address | `ip neigh` |
| Socket | A local endpoint owned by a process | `ss`, `lsof`, `/proc` |
| Namespace | A separate network stack with its own interfaces/routes/sockets | `ip netns`, `nsenter` |
| Firewall/NAT state | Packet filter, connection tracking, and address translation state | `nft`, `iptables`, `conntrack` |
| Queue/qdisc | Packet scheduling and shaping state | `tc` |

The old commands still exist on many machines:

| Old habit | Modern default |
|---|---|
| `ifconfig` | `ip addr`, `ip link` |
| `route -n` | `ip route` |
| `arp -n` | `ip neigh` |
| `netstat -tulpn` | `ss -tulpn` |
| `brctl` | `bridge`, `ip link` |
| `iptables` for new firewalls | `nft` where the distro supports it |

This guide focuses on the modern defaults, because they map better to how the kernel actually works. `ip` and `ss` are part of iproute2 and speak to the kernel over netlink. They are not just nicer output; they are the native operator interface.

### The Debugging Ladder

When a network problem appears, walk downward:

1. **Name resolution:** does the name resolve to the expected address?
2. **Local service:** is a process listening on the expected address and port?
3. **Local routing:** which interface would Linux use to reach the destination?
4. **Link state:** is the interface up, does it have carrier, are counters increasing?
5. **Neighbor resolution:** can Linux resolve the next-hop MAC address?
6. **Remote reachability:** does ICMP/TCP reach the target?
7. **Firewall/NAT:** is a packet being dropped or rewritten?
8. **Throughput:** is the link slow, or is the application/disk/CPU slow?

Most incidents become obvious if you do not skip steps.

### The Addresses Used in Examples

The examples use documentation ranges:

| Purpose | IPv4 range |
|---|---|
| Examples | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` |
| Private LAN | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |

Replace them with your real interface names and addresses.

---

## Part 2 - Lab Setup and Safety

Install the core tools:

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y iproute2 iputils-ping dnsutils netcat-openbsd iperf3 rsync tar openssh-client pv jq ethtool nftables conntrack

# Fedora/RHEL-family
sudo dnf install -y iproute iputils bind-utils nmap-ncat iperf3 rsync tar openssh-clients pv jq ethtool nftables conntrack-tools

# Arch
sudo pacman -Syu iproute2 iputils bind netcat iperf3 rsync tar openssh pv jq ethtool nftables conntrack-tools
```

Check versions:

```bash
ip -Version
ss --version
nc -h 2>&1 | head -20
iperf3 --version
rsync --version
ssh -V
tar --version
```

### Runtime vs Persistent Configuration

Most `ip` commands are runtime changes. They disappear on reboot or when NetworkManager/systemd-networkd/netplan reapplies configuration.

Use `ip` for:

- Debugging.
- Labs.
- Emergency temporary fixes.
- Proving what persistent config should be.

Use your distro's network manager for persistent config:

```bash
# NetworkManager
nmcli dev status
nmcli con show

# systemd-networkd
networkctl status

# Ubuntu netplan
ls /etc/netplan/
```

### Safety Rules

On a remote machine:

- Do not delete the default route unless you have console access.
- Do not bring the management interface down over SSH.
- Prefer `ip route replace` over delete/add when changing routes.
- Start a rollback timer before risky changes:

```bash
# Reboot in 5 minutes unless you cancel it.
sudo shutdown -r +5 "network rollback timer"

# After confirming networking works:
sudo shutdown -c
```

For firewall work, use the same pattern. A saved rollback is cheap; a locked-out server is not.

---

## Part 3 - Interfaces, Addresses, and Links with ip

Start with the compact view:

```bash
ip -br link
ip -br addr
```

Common output:

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             10.0.2.15/24 fe80::5054:ff:fe12:3456/64
docker0          DOWN           172.17.0.1/16
```

Meaning:

- `lo` is loopback.
- `eth0` is up and has IPv4 and link-local IPv6 addresses.
- `docker0` exists but has no active link.

### Inspect a Link

```bash
ip link show dev eth0
ip -d link show dev eth0
ip -s link show dev eth0
```

Look for:

- `state UP` vs `state DOWN`.
- `LOWER_UP`, which usually means carrier/link detected.
- MTU.
- `rx`/`tx` errors, drops, overruns, carrier errors.

For hardware details:

```bash
sudo ethtool eth0
sudo ethtool -S eth0 | egrep 'err|drop|timeout|crc|miss|coll|reset'
```

If `ip link` says the interface is up but `ethtool` says no link detected, you likely have a cable, switch port, VM attachment, or NIC problem.

### Bring a Link Up or Down

```bash
sudo ip link set dev eth0 up
sudo ip link set dev eth0 down
```

Do not run the second command on the interface carrying your SSH session unless you are at the console.

### Add and Remove an Address

Temporary address:

```bash
sudo ip addr add 192.0.2.10/24 dev eth0
ip -br addr show dev eth0
```

Remove it:

```bash
sudo ip addr del 192.0.2.10/24 dev eth0
```

Flush all addresses on an interface:

```bash
sudo ip addr flush dev eth0
```

That is destructive. Do not do it remotely unless you know exactly what you are flushing.

### JSON Output for Scripts

Prefer JSON over parsing human output:

```bash
ip -j addr show dev eth0 | jq .
ip -j route get 1.1.1.1 | jq .
```

This matters in automation. Human formats change; JSON is much safer.

### Change MTU

```bash
sudo ip link set dev eth0 mtu 9000
ip link show dev eth0
```

Jumbo frames only work if every hop in the Layer 2 path supports them. A mismatch creates strange loss and stalls. For internet-facing traffic, 1500 is the ordinary default.

### Watch Network Events

```bash
ip monitor
```

Then in another terminal:

```bash
sudo ip addr add 192.0.2.99/24 dev eth0
sudo ip addr del 192.0.2.99/24 dev eth0
```

`ip monitor` is excellent for catching DHCP renewals, NetworkManager changes, interfaces flapping, and routes being injected or removed.

---

## Part 4 - Routes, Rules, and Neighbors

The route table answers: "Where would this packet go?"

```bash
ip route
ip -6 route
```

Typical output:

```text
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
```

Meaning:

- Traffic to `10.0.2.0/24` is local on `eth0`.
- Everything else goes to the default gateway `10.0.2.2`.

### The Best Route Debug Command

Use `ip route get` constantly:

```bash
ip route get 8.8.8.8
ip route get 203.0.113.20 from 10.0.2.15
```

It tells you the chosen interface, source address, gateway, and route decision. When a host has multiple NICs, VPNs, containers, or policy routing, `ip route get` is the truth.

### Add a Temporary Route

```bash
sudo ip route add 203.0.113.0/24 via 10.0.2.1 dev eth0
```

Replace an existing route:

```bash
sudo ip route replace default via 10.0.2.1 dev eth0 metric 100
```

Delete a route:

```bash
sudo ip route del 203.0.113.0/24
```

### Multiple Default Routes

Servers with several NICs often have several defaults:

```bash
ip route show default
```

Example:

```text
default via 10.10.0.1 dev eth0 metric 100
default via 192.168.50.1 dev eth1 metric 200
```

Lower metric wins. If traffic leaves through the wrong interface, check:

```bash
ip route get 1.1.1.1
ip rule
```

### Policy Routing

Policy routing means: before looking at the normal route table, choose a table based on source address, mark, incoming interface, or other selectors.

Example: send traffic sourced from `192.168.50.10` out `eth1`:

```bash
echo "100 wan2" | sudo tee -a /etc/iproute2/rt_tables
sudo ip route add default via 192.168.50.1 dev eth1 table wan2
sudo ip rule add from 192.168.50.10/32 table wan2 priority 1000

ip rule
ip route show table wan2
ip route get 8.8.8.8 from 192.168.50.10
```

Temporary cleanup:

```bash
sudo ip rule del from 192.168.50.10/32 table wan2 priority 1000
sudo ip route flush table wan2
```

Policy routing is powerful and easy to forget. Always document it.

### ARP and IPv6 Neighbors

Neighbor entries map IP addresses to link-layer addresses:

```bash
ip neigh
ip neigh show dev eth0
ip neigh show nud failed
```

States:

| State | Meaning |
|---|---|
| `REACHABLE` | Recently confirmed |
| `STALE` | Known, but not recently confirmed |
| `DELAY` / `PROBE` | Linux is checking reachability |
| `FAILED` | Neighbor resolution failed |
| `PERMANENT` | Static entry |

Flush a bad neighbor entry:

```bash
sudo ip neigh flush to 10.0.2.2 dev eth0
```

If a route is correct but packets do not leave, neighbor resolution may be stuck. Check `ip neigh` before blaming DNS or the application.

### DNS Is Not Routing

DNS maps names to addresses. Routing decides how to reach addresses.

Useful checks:

```bash
getent hosts example.com
resolvectl status
resolvectl query example.com
dig example.com
dig @1.1.1.1 example.com
```

If `dig @1.1.1.1 example.com` works but `getent hosts example.com` fails, the problem is local resolver configuration. If both work but connections fail, the problem is not DNS.

---

## Part 5 - Sockets and Services with ss

`ss` answers: "What sockets exist, what state are they in, and which processes own them?"

### Listening Ports

```bash
sudo ss -tulpn
sudo ss -ltnp
sudo ss -lunp
```

Flags:

| Flag | Meaning |
|---|---|
| `-t` | TCP |
| `-u` | UDP |
| `-l` | listening sockets |
| `-p` | process info |
| `-n` | numeric addresses/ports |

Example:

```text
State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process
LISTEN 0      4096   127.0.0.1:5432      0.0.0.0:*     users:(("postgres",pid=1234,fd=5))
LISTEN 0      511    0.0.0.0:80          0.0.0.0:*     users:(("nginx",pid=2222,fd=6))
```

Important distinction:

- `127.0.0.1:5432` listens only on localhost.
- `0.0.0.0:80` listens on all IPv4 interfaces.
- `[::]:443` may listen on IPv6 and sometimes IPv4 too, depending on `net.ipv6.bindv6only`.

### Established Connections

```bash
ss -tan state established
ss -tan state syn-sent
ss -tan state time-wait
```

Common states:

| State | Meaning |
|---|---|
| `LISTEN` | Server socket waiting for connections |
| `SYN-SENT` | Local host sent SYN, waiting for SYN-ACK |
| `SYN-RECV` | Server received SYN, not fully established |
| `ESTAB` | Connection established |
| `TIME-WAIT` | Closed recently; kernel keeps state briefly |
| `CLOSE-WAIT` | Remote closed; local process has not closed |

Many `CLOSE-WAIT` sockets usually mean an application bug: the peer closed but your process is not closing its side.

### Filter by Port or Host

```bash
ss -tan '( sport = :443 or dport = :443 )'
ss -tan dst 203.0.113.20
ss -tan state established dst 203.0.113.20
```

Find who owns a port:

```bash
sudo ss -ltnp 'sport = :8080'
```

### TCP Details

```bash
ss -ti dst 203.0.113.20
ss -tmi state established
```

Look for:

- RTT estimates.
- Congestion window (`cwnd`).
- Retransmissions.
- Send/receive memory.
- Stalled queues.

This is where `ss` becomes more than a netstat replacement. It shows TCP behavior without packet capture.

### Backlog Problems

If a service is overloaded:

```bash
sudo ss -ltn
```

Look at `Recv-Q` and `Send-Q` on listening sockets. A large receive queue can mean connections are arriving faster than the application accepts them.

Also inspect:

```bash
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_max_syn_backlog
```

Do not blindly tune these. First confirm the application is actually accepting connections and has enough workers.

### Unix Domain Sockets

Not all sockets are TCP/UDP:

```bash
ss -xap
```

This helps with local services like Docker, Postgres, systemd, Wayland, and agents that communicate over filesystem socket paths.

---

## Part 6 - Netcat for Real Debugging

`nc`/netcat is a raw network multitool. It can connect, listen, send bytes, receive bytes, scan ports, and emulate simple clients and servers.

Netcat has variants:

| Variant | Common on | Notes |
|---|---|---|
| OpenBSD `nc` | Debian/Ubuntu, BSDs | Good default; common flags include `-l`, `-N`, `-z`, `-w`, `-U` |
| GNU netcat | Older Linux systems | Different EOF flags; often uses `-q` |
| Nmap `ncat` | RHEL/Fedora via `nmap-ncat` | Extra proxy/TLS features |
| BusyBox `nc` | Alpine/embedded | Smaller feature set |

Always check:

```bash
nc -h 2>&1 | head -40
```

### Test Whether a TCP Port Is Reachable

```bash
nc -vz 203.0.113.10 443
nc -vz -w 3 203.0.113.10 1-1024
```

Use this when:

- `curl` fails but you want to know if TCP connects at all.
- You need to distinguish "service not listening" from "HTTP is broken."
- You are testing a firewall rule.

Exit status matters:

```bash
if nc -z -w 2 app.example.com 443; then
  echo "tcp reachable"
else
  echo "tcp not reachable"
fi
```

### Talk HTTP by Hand

```bash
printf 'GET /health HTTP/1.1\r\nHost: app.example.com\r\nConnection: close\r\n\r\n' \
  | nc -N app.example.com 80
```

If your `nc` does not support `-N`, try:

```bash
printf 'GET /health HTTP/1.1\r\nHost: app.example.com\r\nConnection: close\r\n\r\n' \
  | nc -q 0 app.example.com 80
```

The point is to send EOF after stdin closes. Without that, some servers wait.

### Create a Test TCP Server

Terminal 1:

```bash
nc -l 8080
```

Terminal 2:

```bash
printf 'hello\n' | nc -N 127.0.0.1 8080
```

This is a fast way to prove local firewall, routing, and port-forward behavior.

### Return a Fake HTTP Response

```bash
while true; do
  printf 'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK' \
    | nc -l 8080
done
```

Then:

```bash
curl -v http://127.0.0.1:8080/
```

Use this to test a reverse proxy or load balancer before the real backend exists.

### UDP Smoke Test

Receiver:

```bash
nc -u -l 9999
```

Sender:

```bash
printf 'packet\n' | nc -u -w 1 203.0.113.10 9999
```

UDP has no connection handshake. A successful sender exit does not prove the receiver got the packet. Use packet capture or application logs for confirmation.

### Unix Socket Test

```bash
nc -U /var/run/docker.sock
```

Be careful: local Unix sockets often expose powerful APIs. Docker's socket is effectively root-equivalent on many systems.

---

## Part 7 - Measuring Throughput with iperf3

`iperf3` measures the network path without your application protocol, database, filesystem, or object store in the way. Use it before blaming an app for being slow.

### Basic TCP Test

Server:

```bash
iperf3 -s
```

Client:

```bash
iperf3 -c 203.0.113.10
```

Run longer and report every 2 seconds:

```bash
iperf3 -c 203.0.113.10 -t 30 -i 2
```

### Reverse Direction

Default mode sends from client to server. Reverse mode sends from server to client:

```bash
iperf3 -c 203.0.113.10 -R
```

Use this for asymmetric links, cloud egress checks, and "downloads are slow but uploads are fine" reports.

### Bidirectional Test

```bash
iperf3 -c 203.0.113.10 --bidir
```

This uses separate sockets for both directions. It can expose duplex issues and oversubscribed links.

### Parallel Streams

```bash
iperf3 -c 203.0.113.10 -P 4
```

Parallel streams can fill high-bandwidth/high-latency paths where one TCP flow cannot. Interpret carefully: if one stream is slow but four streams are fast, the network may be fine while a single application's flow is constrained by TCP window, congestion, or middleboxes.

### UDP Test

```bash
iperf3 -c 203.0.113.10 -u -b 100M -t 20
```

UDP tests answer different questions:

- How much loss appears at a target rate?
- How much jitter is present?
- Does a firewall treat UDP differently?

Do not run unlimited UDP tests on shared networks. You can create real congestion.

### JSON for Automation

```bash
iperf3 -c 203.0.113.10 -t 10 --json > iperf.json
jq '.end.sum_received.bits_per_second' iperf.json
```

Use JSON in CI, lab validation, and capacity reports.

### Bind to an Interface or Address

Server:

```bash
iperf3 -s -B 192.0.2.10
```

Client:

```bash
iperf3 -c 192.0.2.10 -B 192.0.2.20
```

This matters on multihomed hosts and VPN machines.

### Zero-Copy Mode

```bash
iperf3 -c 203.0.113.10 -Z
```

Zero-copy mode can reduce CPU overhead. If throughput jumps only with `-Z`, CPU copying may be part of the bottleneck.

### Interpret Results Like an Operator

Compare:

1. `iperf3` throughput.
2. Real file transfer throughput.
3. Disk read/write throughput.
4. CPU usage during encryption/compression.
5. Retransmits and RTT from `ss -ti`.

Example:

```bash
# Network path
iperf3 -c nas.local -t 30

# Disk read path
dd if=/data/bigfile of=/dev/null bs=16M status=progress

# Transfer path
rsync -a --info=progress2 /data/bigfile nas:/data/
```

If `iperf3` shows 940 Mbit/s on gigabit Ethernet but `rsync` gets 90 Mbit/s, the link is probably not the bottleneck. Look at disk, CPU, SSH cipher, compression, small-file overhead, or remote filesystem behavior.

---

## Part 8 - Network Namespaces and veth Labs

Network namespaces are how containers get separate interfaces, routes, firewall state, and sockets. You can build a tiny container-like network by hand.

### Two Namespaces Connected by a veth Pair

Create namespaces:

```bash
sudo ip netns add red
sudo ip netns add blue
```

Create a virtual Ethernet pair:

```bash
sudo ip link add veth-red type veth peer name veth-blue
sudo ip link set veth-red netns red
sudo ip link set veth-blue netns blue
```

Assign addresses:

```bash
sudo ip -n red addr add 10.10.0.1/24 dev veth-red
sudo ip -n blue addr add 10.10.0.2/24 dev veth-blue
```

Bring links up:

```bash
sudo ip -n red link set lo up
sudo ip -n blue link set lo up
sudo ip -n red link set veth-red up
sudo ip -n blue link set veth-blue up
```

Test:

```bash
sudo ip netns exec red ping -c 3 10.10.0.2
sudo ip -n red route
sudo ip -n blue addr
```

### Use nc Across Namespaces

Receiver:

```bash
sudo ip netns exec blue nc -l 8080
```

Sender:

```bash
printf 'hello from red\n' | sudo ip netns exec red nc -N 10.10.0.2 8080
```

If your `nc` lacks `-N`, try `-q 0`.

### Use iperf3 Across Namespaces

Server:

```bash
sudo ip netns exec blue iperf3 -s
```

Client:

```bash
sudo ip netns exec red iperf3 -c 10.10.0.2 -t 10
```

This tests the local kernel path, not a physical NIC. It is still useful for learning veth behavior and container plumbing.

### Add a Router Namespace

This pattern models two LANs connected by a router:

```bash
sudo ip netns add left
sudo ip netns add right
sudo ip netns add rtr

sudo ip link add veth-left type veth peer name veth-rtr-left
sudo ip link add veth-right type veth peer name veth-rtr-right

sudo ip link set veth-left netns left
sudo ip link set veth-rtr-left netns rtr
sudo ip link set veth-right netns right
sudo ip link set veth-rtr-right netns rtr

sudo ip -n left addr add 10.1.0.2/24 dev veth-left
sudo ip -n rtr addr add 10.1.0.1/24 dev veth-rtr-left
sudo ip -n right addr add 10.2.0.2/24 dev veth-right
sudo ip -n rtr addr add 10.2.0.1/24 dev veth-rtr-right

for ns in left right rtr; do sudo ip -n "$ns" link set lo up; done
sudo ip -n left link set veth-left up
sudo ip -n rtr link set veth-rtr-left up
sudo ip -n right link set veth-right up
sudo ip -n rtr link set veth-rtr-right up

sudo ip -n left route add default via 10.1.0.1
sudo ip -n right route add default via 10.2.0.1
sudo ip netns exec rtr sysctl -w net.ipv4.ip_forward=1
```

Test:

```bash
sudo ip netns exec left ping -c 3 10.2.0.2
sudo ip netns exec left ip route get 10.2.0.2
```

Cleanup:

```bash
for ns in left right rtr red blue; do
  sudo ip netns del "$ns" 2>/dev/null || true
done
```

### Why This Matters

Docker, containerd, Kubernetes, Podman, systemd-nspawn, and many CNI plugins all use these primitives. A pod is not magic: it is a process in a network namespace, usually connected to the host through a veth pair and routed or bridged by host networking rules.

---

## Part 9 - Practical Troubleshooting Playbooks

This section is deliberately procedural. Run the commands in order. Do not jump straight to packet capture unless the simpler checks are exhausted.

### Playbook: "The Service Is Down"

On the server:

```bash
sudo ss -ltnp 'sport = :443'
ip -br addr
ip route
sudo nft list ruleset | less
```

On the client:

```bash
getent hosts app.example.com
addr=$(getent ahostsv4 app.example.com | awk 'NR==1 {print $1}')
ip route get "$addr"
nc -vz -w 3 app.example.com 443
curl -vk https://app.example.com/
```

Interpretation:

| Observation | Likely cause |
|---|---|
| Nothing listening on server | Application is down or bound to wrong port |
| Listening on `127.0.0.1` only | Service is local-only; bind to real interface or proxy it |
| Client cannot resolve name | DNS/resolver issue |
| `ip route get` chooses wrong interface | Route or policy-routing issue |
| `nc` times out | Firewall, routing, security group, or packet loss |
| `nc` says refused | Host reachable, port closed or rejected |
| `curl` connects but HTTP fails | App/proxy/TLS layer, not TCP reachability |

### Playbook: "It Works Locally but Not Remotely"

On the server:

```bash
sudo ss -ltnp
ip -br addr
```

Look for this:

```text
LISTEN 0 128 127.0.0.1:8080 0.0.0.0:* users:(("app",pid=1234,fd=7))
```

The app is only listening on loopback. Fix the bind address:

- `127.0.0.1` means local only.
- `0.0.0.0` means all IPv4 interfaces.
- `::` means IPv6 wildcard and may also cover IPv4 depending on system settings.

### Playbook: "The Default Route Is Wrong"

```bash
ip route show default
ip rule
ip route get 8.8.8.8
ip -br addr
ip route get 8.8.8.8 from 192.0.2.10
```

Fix temporarily:

```bash
sudo ip route replace default via 10.0.2.1 dev eth0 metric 100
```

Then make the same change persistently with NetworkManager, netplan, systemd-networkd, or your cloud-init config.

### Playbook: "DNS Is Broken"

```bash
getent hosts internal.service
resolvectl status
resolvectl query internal.service
dig internal.service
dig @10.0.0.53 internal.service
dig @1.1.1.1 example.com
```

Interpretation:

| Observation | Meaning |
|---|---|
| `dig @1.1.1.1 example.com` works, `getent` fails | Local resolver config problem |
| Internal DNS works, public DNS fails | Upstream/forwarder problem |
| Public DNS works, internal DNS fails | Search domain, split DNS, VPN, or internal resolver problem |
| DNS returns wrong IP | Zone/config issue, not Linux routing |

### Playbook: "The Network Is Slow"

Separate network from everything else:

```bash
iperf3 -s                       # on target
iperf3 -c target -t 30 -i 2      # on source
iperf3 -c target -R -t 30        # reverse direction
iperf3 -c target --bidir -t 30   # both directions
```

Then inspect TCP:

```bash
ss -ti dst target
ip -s link show dev eth0
sudo ethtool -S eth0 | egrep 'err|drop|crc|timeout|reset'
```

Then compare with disk and file transfer:

```bash
dd if=/data/bigfile of=/dev/null bs=64M status=progress
rsync -a --info=progress2 /data/bigfile target:/tmp/
```

Common conclusions:

| Result | Interpretation |
|---|---|
| `iperf3` fast, rsync slow | Disk/CPU/SSH/small files, not raw network |
| `iperf3` slow both directions | Link/path/firewall/VM host issue |
| `iperf3` fast one direction, slow reverse | Asymmetric link, shaping, routing, or duplex path |
| Many retransmits in `ss -ti` | Loss or congestion |
| Interface CRC errors | Physical/NIC/switch problem |

### Playbook: "MTU Black Hole"

Symptoms:

- Small requests work.
- Large transfers stall.
- VPN, tunnel, or cloud overlay is involved.

Test:

```bash
ping -M do -s 1472 target       # 1500-byte IPv4 packet: 1472 payload + 28 header
ping -M do -s 1400 target
tracepath target
```

If 1400 works and 1472 fails, MTU is part of the story. Fix the tunnel MTU or TCP MSS clamping at the correct boundary. Do not randomly lower every host to 1200 unless you understand the path.

### Playbook: "A Port Is Filtered Somewhere"

Server:

```bash
sudo ss -ltnp 'sport = :9000'
sudo nft list ruleset | less
```

Client:

```bash
nc -vz -w 3 server 9000
```

Middlebox/cloud:

- Security group / firewall rule.
- Host firewall.
- Network ACL.
- Kubernetes NetworkPolicy.
- Load balancer listener/target health.

`connection refused` usually means the host replied but the port is closed. `timed out` usually means no reply reached the client.

---

## Part 10 - File Transfer Cookbook

File transfer is where networking meets disk, CPU, encryption, metadata, and operational risk. The fastest method is not always the best method.

### Decision Matrix

| Method | Best for | Encrypted | Resumable | Preserves metadata | Good for repeat sync | Main risk |
|---|---|---:|---:|---:|---:|---|
| `scp` | Simple one-off copy over SSH | Yes | No | Basic with `-p` | No | Slow-ish, no resume/incremental |
| `rsync` over SSH | Repeat syncs, large trees, resumable copies | Yes | Yes | Excellent with right flags | Yes | `--delete` can erase good data |
| `tar` over SSH | One-time exact tree stream, no remote rsync needed | Yes | No | Excellent with right flags | No | Restart from zero if interrupted |
| `tar` + `nc` | Fast trusted-LAN bulk copy | No | No | Good because tar carries metadata | No | No auth/encryption/integrity |
| Direct `nc` file | Fast single file on trusted isolated network | No | No | No | No | Easy to corrupt/mis-send silently |

Short version:

- Use **scp** for a quick encrypted copy.
- Use **rsync** when you may run it more than once.
- Use **tar over SSH** when you need a faithful tree stream and the remote may not have rsync.
- Use **tar + netcat** only on a trusted network when speed matters more than security.
- Use **direct netcat** for labs, rescue work, and isolated direct cables, not ordinary production transfer.

### Before Any Large Transfer

Measure the network:

```bash
iperf3 -s                  # receiver
iperf3 -c receiver -t 20   # sender
```

Check disk speed:

```bash
dd if=/data/bigfile of=/dev/null bs=64M status=progress
```

Estimate transfer time:

```bash
# 500 GiB over a real 940 Mbit/s gigabit link is roughly 75 minutes before overhead.
```

Use `tmux` or `screen` for long transfers:

```bash
tmux new -s transfer
```

Always verify important transfers:

```bash
sha256sum bigfile > bigfile.sha256
sha256sum -c bigfile.sha256
```

### scp: Simple Encrypted Copy

OpenSSH `scp` uses SFTP by default in modern OpenSSH, while keeping the familiar `scp` interface.

Copy one file:

```bash
scp ./backup.tar.zst user@server:/srv/restore/
```

Copy a directory:

```bash
scp -r ./site user@server:/srv/
```

Preserve times and modes:

```bash
scp -p ./backup.tar.zst user@server:/srv/restore/
```

Use a nonstandard SSH port:

```bash
scp -P 2222 ./file user@server:/tmp/
```

Use a jump host:

```bash
scp -J bastion.example.com ./file user@app.internal:/tmp/
```

Limit bandwidth. OpenSSH `scp -l` is in Kbit/s:

```bash
scp -l 50000 ./bigfile user@server:/srv/
```

That is about 50 Mbit/s.

Use compression only when data is compressible and CPU is not the bottleneck:

```bash
scp -C ./logs.tar user@server:/srv/
```

Do not expect `scp` to resume interrupted transfers. For large or unreliable transfers, use `rsync`.

### rsync: The Default for Serious Copies

The most common safe pattern:

```bash
rsync -aP --info=progress2 ./data/ user@server:/srv/data/
```

Important: trailing slash semantics matter.

```bash
rsync -a ./data  user@server:/srv/   # creates /srv/data
rsync -a ./data/ user@server:/srv/   # copies contents into /srv/
```

Resume and keep partial files:

```bash
rsync -aP --partial-dir=.rsync-partial ./bigfile user@server:/srv/
```

For an interrupted append-like large file:

```bash
rsync -aP --append-verify ./bigfile user@server:/srv/
```

Mirror a directory, but preview deletion first:

```bash
rsync -aHAX --numeric-ids --delete --dry-run /srv/app/ root@server:/srv/app/
rsync -aHAX --numeric-ids --delete           /srv/app/ root@server:/srv/app/
```

Flags:

| Flag | Meaning |
|---|---|
| `-a` | archive mode: recursive plus common metadata |
| `-P` | `--partial --progress` |
| `--info=progress2` | overall progress |
| `-H` | preserve hard links |
| `-A` | preserve ACLs |
| `-X` | preserve xattrs |
| `--numeric-ids` | do not map uid/gid names |
| `--delete` | delete files on destination not present on source |
| `--dry-run` | show what would happen |
| `--bwlimit=50M` | throttle transfer |

Compression:

```bash
rsync -azP ./logs/ user@server:/srv/logs/
```

Use `-z` for text/logs over slow links. Avoid it for already compressed data, media, VM images, and fast LANs where CPU becomes the bottleneck.

Custom SSH options:

```bash
rsync -aP -e 'ssh -J bastion.example.com -p 2222' ./data/ user@app:/srv/data/
```

The rule: if you might need to run the transfer twice, start with rsync.

### tar Over SSH: Faithful One-Shot Tree Transfer

`tar` streams a filesystem tree. SSH provides encryption and authentication.

Copy a directory tree:

```bash
tar -C /src -cpf - . \
  | ssh user@server 'mkdir -p /dst && tar -C /dst -xpf -'
```

Preserve advanced Linux metadata:

```bash
sudo tar --xattrs --acls --selinux --numeric-owner -C / -cpf - var/lib/app \
  | ssh root@server 'sudo tar --xattrs --acls --selinux --numeric-owner -C / -xpf -'
```

Sparse VM image or database-like file:

```bash
sudo tar --sparse -C /vmstore -cpf - images \
  | ssh root@server 'sudo tar --sparse -C /vmstore -xpf -'
```

Compress with zstd in the pipeline:

```bash
tar -C /src -cpf - . \
  | zstd -T0 -3 \
  | ssh user@server 'zstd -d | tar -C /dst -xpf -'
```

Show progress with `pv`:

```bash
tar -C /src -cpf - . \
  | pv \
  | ssh user@server 'tar -C /dst -xpf -'
```

When to use tar over SSH:

- Remote host has SSH but not rsync.
- You want an exact stream of a tree.
- You are migrating a service directory once.
- You need xattrs/ACLs/SELinux labels and know both sides support them.

When not to use it:

- Unreliable links.
- Transfers you may need to resume.
- Continuous mirroring.

### Direct netcat: Single File, Trusted Network Only

Direct netcat is raw TCP. No encryption, no authentication, no file metadata, no resume. Use it on direct cables, private lab VLANs, or emergency trusted networks.

Receiver first:

```bash
nc -l 9000 > bigfile
```

Some variants require:

```bash
nc -l -p 9000 > bigfile
```

Sender:

```bash
pv bigfile | nc -N receiver 9000
```

If `-N` is not supported:

```bash
pv bigfile | nc -q 0 receiver 9000
```

Verify:

```bash
# sender before transfer
sha256sum bigfile

# receiver after transfer
sha256sum bigfile
```

Firewall:

```bash
sudo ufw allow from sender_ip to any port 9000 proto tcp
# or with nftables, add the narrow equivalent rule for your ruleset.
```

Close the port when done.

### tar + netcat: Fast Directory Transfer on Trusted LAN

Receiver:

```bash
mkdir -p /dst
nc -l 9000 | tar -C /dst -xpf -
```

Sender:

```bash
tar -C /src -cpf - . | pv | nc -N receiver 9000
```

Compressed:

Receiver:

```bash
mkdir -p /dst
nc -l 9000 | zstd -d | tar -C /dst -xpf -
```

Sender:

```bash
tar -C /src -cpf - . | zstd -T0 -3 | pv | nc -N receiver 9000
```

With metadata:

Receiver:

```bash
sudo nc -l 9000 \
  | sudo tar --xattrs --acls --selinux --numeric-owner -C /dst -xpf -
```

Sender:

```bash
sudo tar --xattrs --acls --selinux --numeric-owner -C /src -cpf - . \
  | pv \
  | nc -N receiver 9000
```

Use this only when the network is trusted. Anyone who can connect to the listening port can send bytes.

### Split Archives for Fragile Links

If you cannot use rsync and need restartability, split the archive:

```bash
tar -C /src -cpf - . | zstd -T0 -3 | split -b 4G - backup.tar.zst.
rsync -aP backup.tar.zst.* user@server:/srv/restore/
```

On receiver:

```bash
cat backup.tar.zst.* | zstd -d | tar -C /dst -xpf -
```

This combines tar's metadata preservation with rsync's resumable file transfer.

### Preserve Metadata Correctly

For normal user data:

```bash
rsync -aP ./photos/ server:/backup/photos/
```

For system trees:

```bash
sudo rsync -aHAX --numeric-ids /srv/app/ root@server:/srv/app/
```

For tar:

```bash
sudo tar --xattrs --acls --selinux --numeric-owner -C / -cpf app.tar srv/app
```

Metadata checklist:

| Metadata | scp | rsync | tar |
|---|---:|---:|---:|
| File contents | Yes | Yes | Yes |
| Directory tree | `-r` | Yes | Yes |
| Mode bits | With `-p` basic | Yes with `-a` | Yes |
| Timestamps | With `-p` | Yes with `-a` | Yes |
| Owners/groups | Limited unless root | `-o -g`, `--numeric-ids` | `--numeric-owner` |
| ACLs | No | `-A` | `--acls` |
| xattrs | No | `-X` | `--xattrs` |
| SELinux labels | No | xattrs if supported | `--selinux` |
| Hard links | No | `-H` | Usually yes in archive |
| Sparse files | Poor | `-S` | `--sparse` |

### Transfer Many Small Files

Many small files are slow because each file means metadata operations.

Good:

```bash
tar -C /src -cpf - . | ssh server 'tar -C /dst -xpf -'
```

Also good if repeated:

```bash
rsync -a --delete /src/ server:/dst/
```

Bad:

```bash
for f in /src/*; do scp "$f" server:/dst/; done
```

That creates a new SSH/SFTP session pattern or at least per-file overhead that scales poorly.

### Transfer One Huge File

Best default:

```bash
rsync -aP --partial-dir=.rsync-partial ./huge.img server:/dst/
```

If the link is a trusted direct cable and you need raw speed:

```bash
# receiver
nc -l 9000 > huge.img

# sender
pv huge.img | nc -N receiver 9000
```

Verify checksums either way.

### Move a Live Application Directory

Preferred pattern:

1. Initial sync while app is running.
2. Stop app.
3. Final sync with delete.
4. Start app on destination.

```bash
rsync -aHAX --numeric-ids /srv/app/ root@new:/srv/app/

sudo systemctl stop app
rsync -aHAX --numeric-ids --delete /srv/app/ root@new:/srv/app/
ssh root@new 'systemctl start app'
```

Do not use direct `nc` for a live tree unless you can guarantee a quiescent source.

### Copy Through a Bastion

SCP:

```bash
scp -J bastion.example.com ./file user@app.internal:/tmp/
```

Rsync:

```bash
rsync -aP -e 'ssh -J bastion.example.com' ./data/ user@app.internal:/srv/data/
```

Tar over SSH:

```bash
tar -C /src -cpf - . \
  | ssh -J bastion.example.com user@app.internal 'tar -C /dst -xpf -'
```

Netcat through a bastion is the wrong tool. Use SSH.

### Validate a Transfer

Single file:

```bash
sha256sum bigfile
ssh server 'sha256sum /dst/bigfile'
```

Directory spot check:

```bash
rsync -aHAX --numeric-ids --dry-run --checksum /src/ server:/dst/
```

Count files and bytes:

```bash
find /src -type f -printf '.' | wc -c
du -sh /src
ssh server 'find /dst -type f -printf "." | wc -c; du -sh /dst'
```

`rsync --checksum` is expensive but useful for verification because it reads file contents instead of trusting size/time.

### File Transfer Decision Tree

```text
Need encryption/auth over an untrusted network?
  yes -> use SSH-based transfer.
    One file or small tree, one time? -> scp.
    Repeat, resume, mirror, or big tree? -> rsync.
    Remote lacks rsync but has tar+ssh? -> tar over SSH.
  no -> isolated trusted LAN/direct cable?
    One huge file and you can verify checksum? -> nc.
    Directory tree and you can verify? -> tar + nc.
    Anything production or repeatable? -> rsync anyway.
```

---

## Part 11 - Tool Cheat Sheets

### ip

```bash
ip -br addr
ip -br link
ip -d link show dev eth0
ip -s link show dev eth0
ip route
ip route get 8.8.8.8
ip rule
ip neigh
ip monitor
ip -j addr | jq .
```

Temporary changes:

```bash
sudo ip link set dev eth0 up
sudo ip addr add 192.0.2.10/24 dev eth0
sudo ip route replace default via 192.0.2.1 dev eth0
sudo ip neigh flush dev eth0
```

### ss

```bash
sudo ss -tulpn
sudo ss -ltnp 'sport = :8080'
ss -tan state established
ss -tan '( sport = :443 or dport = :443 )'
ss -ti dst 203.0.113.10
ss -xap
```

### nc / netcat

```bash
nc -vz -w 3 host 443
printf 'GET / HTTP/1.1\r\nHost: host\r\nConnection: close\r\n\r\n' | nc -N host 80
nc -l 8080
nc -u -l 9999
pv file | nc -N receiver 9000
nc -l 9000 > file
```

Variant fallback:

```bash
# If -N is missing:
pv file | nc -q 0 receiver 9000

# If "nc -l 9000" fails:
nc -l -p 9000 > file
```

### iperf3

```bash
iperf3 -s
iperf3 -c server -t 30 -i 2
iperf3 -c server -R
iperf3 -c server --bidir
iperf3 -c server -P 4
iperf3 -c server -u -b 100M
iperf3 -c server --json > result.json
iperf3 -c server -Z
```

### scp

```bash
scp file user@host:/dst/
scp -r dir user@host:/dst/
scp -p file user@host:/dst/
scp -P 2222 file user@host:/dst/
scp -J bastion file user@host:/dst/
scp -l 50000 file user@host:/dst/
```

### rsync

```bash
rsync -aP --info=progress2 src/ user@host:/dst/
rsync -aP --partial-dir=.rsync-partial bigfile user@host:/dst/
rsync -aHAX --numeric-ids --delete --dry-run src/ root@host:/dst/
rsync -aHAX --numeric-ids --delete src/ root@host:/dst/
rsync -aP -e 'ssh -J bastion' src/ user@host:/dst/
rsync -a --bwlimit=50M src/ user@host:/dst/
```

### tar

```bash
tar -C /src -cpf - . | ssh host 'tar -C /dst -xpf -'
tar -C /src -cpf - . | zstd -T0 -3 | ssh host 'zstd -d | tar -C /dst -xpf -'
sudo tar --xattrs --acls --selinux --numeric-owner -C / -cpf - srv/app \
  | ssh root@host 'sudo tar --xattrs --acls --selinux --numeric-owner -C / -xpf -'
tar -C /src -cpf - . | pv | nc -N receiver 9000
```

---

## Final Mental Model

Linux networking is a debugging advantage if you use the right layer:

- `ip` tells you what the kernel would do with packets.
- `ss` tells you what processes and sockets are doing.
- `nc` lets you send and receive raw bytes to prove reachability.
- `iperf3` tells you what the path can carry without application noise.
- `rsync`, `scp`, `tar`, and `nc` are not interchangeable; they trade security, resumability, metadata, and speed.

If you remember one operational rule, make it this: **prove the path before blaming the application, and choose the transfer tool based on risk, not just speed.**

---

## Where to Go Next

- **Build the namespace lab from Part 8 on a real machine** — two veth-connected namespaces, a bridge, and `tcpdump` watching the wire. Every concept in this guide becomes concrete inside a lab you can break and rebuild in seconds.
- **Read the man pages as references, not lore:** [`ip(8)`](https://man7.org/linux/man-pages/man8/ip.8.html) and its per-object pages (`ip-route(8)`, `ip-link(8)`), [`ss(8)`](https://man7.org/linux/man-pages/man8/ss.8.html), and the kernel's [networking documentation](https://docs.kernel.org/networking/index.html) for the sysctls behind Part 9's playbooks.
- **Go one layer down with the [Advanced Linux guide](ADVANCED_LINUX_STUDY_GUIDE.md)** (Part 4: nftables, BBR, conntrack, traffic control) and the [eBPF guide](EBPF_STUDY_GUIDE.md) (XDP, Cilium — where modern Linux networking is headed).
- **Go one layer up with the [Networking Fundamentals guide](NETWORKING_FUNDAMENTALS.md)** (the protocols these tools inspect) and the [Docker & Kubernetes Networking guide](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md) (the namespaces/veth/bridge model at container-platform scale).
- **Adopt one playbook.** Next time something "can't connect," run Part 9's connectivity playbook verbatim instead of guessing — link → address → route → neighbor → firewall → socket. The discipline of asking the kernel in order is the entire skill.

# Networking Fundamentals Study Guide

A depth-first foundational guide to how computer networks actually work. Aimed at working engineers who use networks every day but were never forced to learn what's under the hood. Each phase builds on the previous. This is the substrate that other guides — [Docker & Kubernetes Networking](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md), the future Nginx guide, [Cryptography Fundamentals](CRYPTO_FUNDAMENTALS.md) for the TLS layer — lean on.

> The point of learning networking is to stop being scared of `tcpdump` output. Once you can name every byte on the wire, every layer above stops being magic.

---

## Phase 1: Foundations

### 1.1 Why Networks Are Layered

A network has to do many things at once: turn voltages into bits, group bits into frames, find a destination across the globe, ensure delivery, encrypt, format. Doing this in one giant module would be unmaintainable. The answer, decided in the 1970s and unchanged in spirit: **layering**.

A layer takes data from the layer above, adds its own header (and sometimes trailer), and hands it to the layer below. Receiving works in reverse. Each layer only needs to understand its own header and its neighbors' interfaces. Ethernet doesn't know about HTTP; HTTP doesn't know about Ethernet. Both work because TCP/IP in between provides a clean contract.

The trade-off: layering hides information. A retransmission at the TCP layer is invisible to HTTP, which sometimes mismeasures latency. A packet drop in the middle of the internet looks the same to TCP regardless of whether it was a buffer overflow or a misconfigured firewall. Knowing the layers means knowing where the abstraction is leaking.

### 1.2 OSI vs. TCP/IP

Two reference models, both useful, neither matches reality exactly.

**OSI** (the academic model): 7 layers — Physical, Data Link, Network, Transport, Session, Presentation, Application. Beautiful conceptually. Almost nobody implements it as drawn — sessions and presentations basically disappeared into the application layer.

**TCP/IP** (what actually got deployed): 4 or 5 layers — Link, Internet (IP), Transport (TCP/UDP), Application. The internet runs on this.

What people *actually* talk about in 2026:

| Layer name (TCP/IP) | OSI # | What lives here                              |
|---------------------|-------|----------------------------------------------|
| Application         | 5–7   | HTTP, DNS, SSH, gRPC, anything you'd write code against |
| Transport           | 4     | TCP, UDP, QUIC                               |
| Internet            | 3     | IP, ICMP, BGP, OSPF                          |
| Link                | 2     | Ethernet, Wi-Fi, ARP, MAC addresses          |
| Physical            | 1     | Voltages, light pulses, radio waves          |

When you hear "L4 load balancer" people mean TCP/UDP-layer routing. "L7 load balancer" means HTTP-layer. "L2 switch" means Ethernet-layer. "L3 routing" means IP-layer. Internalize the numbers.

### 1.3 Encapsulation, Concretely

A single HTTP request crossing your home network produces a packet that looks like this on the wire (outermost first):

```
[Ethernet header | IP header | TCP header | HTTP payload | Ethernet trailer]
   14 bytes        20 bytes     20 bytes     ~100s of B      4 bytes
```

- The Ethernet frame says "this goes from MAC A to MAC B on the local network."
- The IP packet says "this goes from IP X to IP Y on the global internet."
- The TCP segment says "this is stream-port-Z, sequence number N, expecting ack M."
- The HTTP payload says "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"

At each hop across the internet, the IP header stays mostly the same (only TTL and a checksum change); the Ethernet frame is *stripped* and *re-added* with the next hop's MAC addresses. This is the key insight: **Ethernet is hop-local; IP is end-to-end**.

### 1.4 The Two Identifier Systems

This trips up everyone learning networking once:

- **MAC addresses** identify *interfaces* (network cards). 48-bit. Burned in at the factory (mostly — modern OSes can override). Only meaningful on the local segment. Format: `aa:bb:cc:dd:ee:ff`.
- **IP addresses** identify *hosts* on the global internet. 32-bit (IPv4) or 128-bit (IPv6). Assigned by the network. Routable across the world. Format: `192.168.1.1` or `2001:db8::1`.

A packet traveling from your laptop to a server in another country goes:
```
my MAC → router MAC      [Ethernet hop 1]
router MAC → ISP MAC      [Ethernet hop 2]
... ~15 more Ethernet hops, each with new MACs ...
last hop MAC → server MAC [Ethernet hop N]
```
Meanwhile the IP header reads `my IP → server IP` for the entire journey, unchanged.

This is why your laptop only needs to know one MAC (the default gateway) and one IP (the destination) to talk to anything on Earth. The router maps the rest.

References: [RFC 1122 (Host Requirements)](https://datatracker.ietf.org/doc/html/rfc1122), [Tanenbaum & Wetherall, *Computer Networks*](https://www.pearson.com/store/p/computer-networks/P100002579376) (the canonical textbook)

---

## Phase 2: The Link Layer

### 2.1 Ethernet, the Lingua Franca

Ethernet, invented at Xerox PARC in 1973, is the dominant L2 technology on wired networks (with Wi-Fi being the dominant wireless L2). It defines:

- A frame format (preamble, MAC addresses, EtherType, payload, frame check sequence).
- A medium-access mechanism (originally CSMA/CD; now mostly switched full-duplex so collisions don't happen).
- Physical signaling (5Base-T, 100Base-TX, 1000Base-T, 10GBase-T, 100Gbe, etc.).

A standard Ethernet frame:

```
| Preamble | Dest MAC | Src MAC | EtherType | Payload          | FCS   |
| 8 B      | 6 B      | 6 B     | 2 B       | 46–1500 B        | 4 B   |
```

- **EtherType** says what's inside: `0x0800` for IPv4, `0x86DD` for IPv6, `0x0806` for ARP, `0x8100` for VLAN-tagged.
- **Payload size** is bounded at 1500 bytes by default — the **MTU** (Maximum Transmission Unit). This bounds how large your IP packets can be without fragmentation, which has consequences (Phase 13).
- **Jumbo frames** (typically MTU 9000) exist for data centers and storage networks. End-to-end support is required; one device with smaller MTU and your traffic gets fragmented or dropped.

### 2.2 MAC Addresses, Demystified

A 48-bit number, conventionally written `aa:bb:cc:dd:ee:ff`. The first 24 bits identify the vendor (OUI — Organizationally Unique Identifier, assigned by IEEE). Apple's OUIs start with `00:1C:B3`, `28:5A:EB`, and dozens of others. The remaining 24 bits are vendor-assigned.

Two important bits in the very first byte:
- **U/L bit** (second-lowest of byte 1) — set means the MAC is locally administered, not factory-assigned. macOS Wi-Fi MAC randomization sets this.
- **I/G bit** (lowest of byte 1) — set means the MAC is a multicast/broadcast address. `ff:ff:ff:ff:ff:ff` is the broadcast MAC; multicast MACs start with `01:00:5e:` for IPv4 and `33:33:` for IPv6.

### 2.3 ARP — How Hosts Find Each Other's MAC

You want to send a packet to `192.168.1.10` on your local network. You know the destination *IP*, but the Ethernet frame needs the destination *MAC*. How do you find it?

**ARP** (Address Resolution Protocol): broadcast a "who has 192.168.1.10?" frame. Every host on the segment sees it. The host with that IP replies with its MAC. Your OS caches the result.

```
arp -n              # Show the cache (Linux/macOS)
ip neigh show       # Modern Linux equivalent
```

ARP is a layer-2 broadcast protocol — it doesn't traverse routers. Each subnet runs its own ARP. This is part of why subnets exist (Phase 3).

**ARP cache poisoning** / **spoofing** is a classic attack: an attacker replies "I have that IP, my MAC is XX" before the legitimate host does. Your traffic to the gateway goes to the attacker instead. Mitigations are at higher layers (TLS) and at the switch (dynamic ARP inspection on managed switches).

IPv6 doesn't use ARP; it uses **NDP** (Neighbor Discovery Protocol) over ICMPv6 instead. Same concept, more features.

### 2.4 Switches vs. Hubs

- **Hub** (obsolete) — repeats every frame to every port. Half-duplex. Collisions. Don't exist in any modern network.
- **Switch** — learns which MAC is reachable on which port (by watching source MACs of incoming frames), and forwards frames only to the port where the destination MAC lives.

A switch's brain is the **MAC table** (also called CAM table — Content-Addressable Memory). Entries time out after a few minutes. On an unknown destination MAC, the switch *floods* — sends the frame to every port except the source. This is normal.

Switches are L2 devices. They don't understand IP. They have IPs only for management (SSH'ing into them to configure).

### 2.5 VLANs

A **VLAN** (Virtual LAN, 802.1Q) is a way to split one physical switched network into multiple logical broadcast domains. Frames get a 4-byte VLAN tag inserted after the source MAC. Frames in VLAN 10 cannot see frames in VLAN 20, even on the same switch.

Why this matters:
- **Security segmentation** — separate guests from servers, IoT from main network.
- **Multi-tenancy** — one physical infrastructure, multiple tenants on isolated VLANs.
- **Trunking** — a single "trunk" port between two switches carries frames for many VLANs, tagged.
- **Access ports** — typical end-host ports are untagged ("access") on a single VLAN.

Modern cloud and overlay networks use **VXLAN** (a UDP-encapsulated extension) to scale beyond VLAN's 4096-VLAN limit to ~16 million IDs. K8s networking heavily uses VXLAN or its alternatives (Geneve, etc.). See the [K8s Networking guide](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md) for depth.

References: [IEEE 802.3 (Ethernet)](https://standards.ieee.org/standard/802_3-2018.html), [IEEE 802.1Q (VLAN)](https://standards.ieee.org/standard/802_1Q-2018.html), [RFC 826 (ARP)](https://datatracker.ietf.org/doc/html/rfc826)

---

## Phase 3: IP and Routing

### 3.1 IPv4

A 32-bit address space (~4.3 billion addresses), written as four octets in decimal: `192.168.1.1` = `0xC0A80101`. Exhausted in 2011 at the IANA level; reclaimed unused blocks have extended availability but the basic answer is that IPv4 addresses are a scarce resource.

Reserved ranges to know cold:
- `0.0.0.0/8` — "this network."
- `10.0.0.0/8` — private (RFC 1918). 16M addresses.
- `100.64.0.0/10` — carrier-grade NAT. You'll see this from cellular networks.
- `127.0.0.0/8` — loopback. Always `127.0.0.1` in practice.
- `169.254.0.0/16` — link-local (auto-configured when DHCP fails). Also the AWS metadata endpoint at `169.254.169.254`.
- `172.16.0.0/12` — private (RFC 1918). 1M addresses.
- `192.168.0.0/16` — private (RFC 1918). 65K addresses. The classic home network.
- `224.0.0.0/4` — multicast.
- `255.255.255.255` — broadcast.

### 3.2 CIDR and Subnets

**CIDR** (Classless Inter-Domain Routing) replaced the old "class A/B/C" system. An IP plus a prefix length: `192.168.1.0/24` means "the first 24 bits are the network; the last 8 bits are the host."

You will subnet networks. The mental model:

| CIDR | Hosts | Use case                              |
|------|-------|---------------------------------------|
| /30  | 2     | Point-to-point links                   |
| /29  | 6     | Small server group                     |
| /27  | 30    | Office floor                           |
| /24  | 254   | Home network                           |
| /22  | 1022  | Building                               |
| /16  | 65534 | Large corp                             |
| /8   | 16M   | An entire RFC1918 range                |

(Host count = `2^(32-prefix) - 2`. The minus 2 is for network address and broadcast.)

CIDR notation everywhere. Practice converting `/19` to a netmask in your head: `/19` = 19 ones = `255.255.224.0`. The `224` comes from `1110_0000` = 224.

The **subnet mask** in dotted-decimal form is equivalent. `/24` = `255.255.255.0`. They are different notations for the same idea.

### 3.3 The IPv4 Header

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version|  IHL  |   DSCP   |ECN|       Total Length              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Identification         |Flags|    Fragment Offset        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    TTL        |   Protocol    |        Header Checksum          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Source IP Address                            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  Destination IP Address                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Options (if IHL > 5)                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

The fields worth knowing:
- **TTL** (Time To Live) — decremented at every router. When 0, the packet is dropped and an ICMP "Time Exceeded" is sent back to the source. This is what `traceroute` exploits to map paths.
- **Protocol** — what's in the payload. `6` = TCP, `17` = UDP, `1` = ICMP, `47` = GRE, `50/51` = IPsec. The `/etc/protocols` file lists them all.
- **DSCP/ECN** — quality-of-service marking and explicit congestion notification.
- **Flags + Fragment Offset** — IPv4 fragmentation. Disabled in modern networks (DF — Don't Fragment — bit usually set).
- **Total Length** — including header. 16-bit, so max IPv4 packet is 65535 bytes. Real-world MTU is 1500.

### 3.4 IPv6

128-bit addresses. `~3.4 × 10^38` of them. Written in eight groups of four hex digits, with `::` allowed once to compress consecutive zero groups: `2001:0db8:0000:0000:0000:ff00:0042:8329` = `2001:db8::ff00:42:8329`.

Key facts:
- No broadcast. Multicast replaces it. `ff02::1` is "all nodes on the local link."
- **Link-local** addresses (`fe80::/10`) are auto-configured on every interface. Always present. Used by NDP.
- **SLAAC** (Stateless Address Autoconfiguration) lets hosts derive their own global IPv6 addresses from a router advertisement, without DHCP.
- **No ARP** — NDP handles neighbor discovery via ICMPv6.
- **No NAT** in normal deployments. Each host gets a real, globally-routable address. (NAT66 exists but is rare and discouraged.)
- **DHCPv6** exists but is often unnecessary.

The IPv6 header is much simpler than IPv4 (fixed 40 bytes, fewer fields). Extension headers replace options.

**Why IPv6 has been "coming" for 30 years and still isn't dominant**:
- IPv4 + NAT works "well enough" to keep the internet running.
- Carrier-grade NAT (CGN) lets ISPs hand out one IPv4 to many customers.
- Application devs almost never need to think about it (DNS resolves to whatever is available).
- Operational tooling is uneven.

That said, IPv6 traffic is now a majority on major mobile networks and many ISPs. The transition is happening, slowly. Modern apps need to be dual-stack aware — see "Happy Eyeballs" in Phase 13.

### 3.5 Routing

A **routing table** says "for this destination prefix, send via this gateway out this interface." Every host has one. View it:

```bash
ip route                        # Linux
netstat -rn                     # macOS / older Linux
route print                     # Windows
```

A typical home machine's routing table looks like:

```
default via 192.168.1.1 dev wlan0
192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.42
```

Read: "to reach the default destination (`0.0.0.0/0`, everything), send via `192.168.1.1`. For destinations in `192.168.1.0/24`, deliver directly (link-scope)."

**Longest-prefix match** — when multiple routes could apply, the most specific wins. `192.168.1.0/24` beats `0.0.0.0/0` for any IP in that range.

### 3.6 BGP at the Level You Need to Know

**BGP** (Border Gateway Protocol) is how the internet's routes propagate between Autonomous Systems (ASes). Every ISP, large cloud provider, and content network runs BGP. There are no central routers — BGP routers gossip routes among each other.

You don't run BGP unless you operate a network with multiple upstream ISPs (multi-homed). But you should know:

- **AS numbers**: a globally unique identifier per organization (AWS is AS16509; Cloudflare is AS13335; Google is AS15169).
- **BGP route hijacking** has caused major outages (the 2008 YouTube/Pakistan incident; the 2024 Klayswap heist) when an AS advertises a prefix it doesn't own and other ASes accept it.
- **RPKI** (Resource Public Key Infrastructure) cryptographically attests which ASes are allowed to originate which prefixes. Adoption is broad enough now that mis-originations are usually caught.
- **Anycast** — multiple sites advertise the same prefix from different locations. BGP picks the topologically nearest. CDNs and DNS root servers heavily use this.

For application developers: BGP failures look like "the internet is broken for some users but not others." When AWS us-east-1 ate the world in 2017 it was BGP-related.

References: [RFC 791 (IPv4)](https://datatracker.ietf.org/doc/html/rfc791), [RFC 8200 (IPv6)](https://datatracker.ietf.org/doc/html/rfc8200), [RFC 4271 (BGP-4)](https://datatracker.ietf.org/doc/html/rfc4271), [BGP for All](https://github.com/bgp/RouteViews)

---

## Phase 4: NAT and Firewalls

### 4.1 Why NAT Exists

There are ~4 billion IPv4 addresses and ~25 billion connected devices. They obviously don't all have public IPs. **NAT** (Network Address Translation) lets many devices share one public IP by rewriting addresses (and ports) at the network boundary.

A typical home network:
- Devices have RFC1918 private IPs (`192.168.1.x`).
- Home router has one public IP from the ISP.
- The router rewrites outbound packets to look like they came from its public IP, remembering the mapping. Inbound replies get translated back.

This is so universal it's invisible — but it shapes everything from "why peer-to-peer is hard" to "why your container can't be reached from outside."

### 4.2 The NAT Variants

People say "NAT" to mean many different things:

- **SNAT** (Source NAT) — rewrites the source address of outbound packets. The classic "home router" NAT. Also called **Masquerading** in Linux iptables when the public IP is dynamic.
- **DNAT** (Destination NAT) — rewrites the destination address. "Port forwarding" is DNAT: traffic to `<public_ip>:8080` gets rewritten to `192.168.1.5:80`.
- **PAT** (Port Address Translation) / **NAPT** — multiple internal IPs share one external IP by also rewriting ports. This is what every home router actually does. Cisco terminology, but the concept is universal.
- **1:1 NAT** — one internal IP maps to one external IP, no port rewriting. Common in cloud (assign an Elastic IP to an instance).
- **Hairpin NAT** (NAT loopback) — when an internal host tries to access its own public IP. Many home routers don't support this, leading to "I can reach my server from outside but not from inside the LAN."
- **NAT64** — IPv6-to-IPv4 translation. Lets IPv6-only hosts reach IPv4 destinations.
- **CGN / CGNAT** (Carrier-Grade NAT) — your ISP NATs your home behind another NAT. You see a CGNAT IP (often `100.64.0.0/10`) as your "public" IP. Common on mobile networks.

### 4.3 The Conntrack Table

Linux's NAT and stateful firewall machinery is **conntrack**. Every flow gets an entry in a kernel hash table:

```
tcp 6 432000 ESTABLISHED src=192.168.1.42 dst=151.101.1.140 sport=51234 dport=443
    src=151.101.1.140 dst=203.0.113.10 sport=443 dport=51234 [ASSURED]
```

This is one connection (HTTPS to Fastly), with both forward (`192.168.1.42 → 151.101.1.140`) and reverse (`151.101.1.140 → 203.0.113.10`) sides tracked. The reverse line shows the NAT translation.

Conntrack matters when:
- **It fills up**. Default size is ~64K entries; busy gateways hit this. `cat /proc/sys/net/netfilter/nf_conntrack_max`.
- **Timeouts trip you up**. The default TCP ESTABLISHED timeout is 5 days. If your application uses long-lived connections without keepalives, NAT mappings can expire mid-conversation.
- **You're debugging stateful firewall rules**. `conntrack -L` shows you what the kernel sees.

### 4.4 The NAT Problem for Applications

NAT breaks many things that "should" work:

- **Inbound connections** to NATed hosts require explicit port forwarding or hole-punching.
- **Peer-to-peer** needs **STUN/TURN/ICE** to navigate NATs. WebRTC, VoIP, BitTorrent all do this.
- **Protocols that embed IPs in payloads** (FTP, SIP) need application-layer gateways (ALGs) that the NAT understands. ALGs are buggy and frequently disabled.
- **End-to-end encryption** can hide IP-embedded data from ALGs, breaking them.

IPv6 was meant to eliminate NAT. It hasn't fully, but in pure-IPv6 networks, every host is reachable, and life is simpler.

### 4.5 Stateful vs. Stateless Firewalls

- **Stateless firewall** — apply rules to each packet in isolation. Fast, cheap. Cannot tell "this is a reply to a connection we initiated" from "this is an unsolicited inbound." You have to allow whole ports both ways.
- **Stateful firewall** — track flows in a conntrack table. Rules can match "established or related" flows, so you allow outbound and the inbound reply is implicitly allowed. This is what every modern firewall does.

The classic Linux stateful pattern:
```
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -j DROP
```

Allows all replies, allows loopback, allows SSH, drops everything else. The first rule is what makes it stateful — established flows are recognized.

Modern Linux is replacing iptables with **nftables**, and Kubernetes/Cilium increasingly uses **eBPF** for the same purpose (Phase 10).

### 4.6 Cloud VPC Security Groups vs. NACLs

In AWS (and similar in GCP/Azure):

- **Security groups** — stateful firewalls attached to instances. Whitelist-only ("allow rules"); if not allowed, dropped. Implicit "allow established" — reply traffic works.
- **Network ACLs** — stateless firewalls attached to subnets. Allow and deny rules; you must explicitly allow both directions.

Use security groups for almost everything. NACLs for coarse subnet-level policy if needed.

References: [RFC 3022 (Traditional NAT)](https://datatracker.ietf.org/doc/html/rfc3022), [RFC 5389 (STUN)](https://datatracker.ietf.org/doc/html/rfc5389), [Linux Conntrack tools](https://conntrack-tools.netfilter.org/)

---

## Phase 5: Transport Layer

The layer that turns "packets that might arrive" into "byte streams" (TCP) or "datagrams" (UDP). All real protocols sit here.

### 5.1 UDP — The Honest One

UDP is barely a protocol. It adds 8 bytes to an IP packet:

```
| Source Port | Dest Port | Length | Checksum |
| 2 B         | 2 B       | 2 B    | 2 B      |
```

That's it. No connection. No reliability. No ordering. No flow control. The OS hands a UDP datagram to the wire and forgets about it. If it's lost, you don't know. If it arrives out of order, you don't know.

This sounds bad, but it's exactly what some applications want:

- **DNS** — small request, small reply. Retransmit at the application layer. TCP's three-way handshake would double latency.
- **Game traffic** — losing one position update is fine; waiting for retransmission is not. Send the latest state every tick.
- **Video calls / VoIP** — late audio is worse than missing audio. Drop and move on.
- **DTLS, QUIC, WireGuard** — all built on UDP. QUIC implements reliability and congestion control at the application layer (Phase 8).

UDP packet size limit: theoretically 64 KB, practically MTU minus headers (~1472 bytes for plain Ethernet). Larger UDP datagrams require IP fragmentation, which is now widely broken (PMTUD black holes — Phase 13).

### 5.2 TCP — Stream Semantics over Packet Reality

TCP is much more elaborate. It provides:

- **Connection-oriented** — explicit handshake before data, explicit close.
- **Reliable** — lost packets retransmitted.
- **Ordered** — receiver sees bytes in order regardless of network reordering.
- **Stream-oriented** — `send(data)` doesn't preserve message boundaries; reader gets a byte stream.
- **Full-duplex** — both directions independent.
- **Flow-controlled** — receiver advertises a window; sender doesn't exceed it.
- **Congestion-controlled** — sender slows down when the network drops packets.

The TCP header (20 bytes minimum):

```
| Source Port    | Dest Port      |
| Sequence Number                  |
| Ack Number                       |
| Data Offset | Flags | Window     |
| Checksum    | Urgent Pointer     |
| Options (variable)               |
```

Key flags:
- **SYN** — initiate connection.
- **ACK** — acknowledge data.
- **FIN** — graceful close.
- **RST** — abort, throw away state.

### 5.3 The Three-Way Handshake

```
Client                              Server
  |                                    |
  |-------- SYN seq=X ---------------->|
  |                                    |
  |<------ SYN-ACK seq=Y ack=X+1 ------|
  |                                    |
  |-------- ACK ack=Y+1 -------------->|
  |                                    |
  |-------- (data flows) -------------|
```

1. Client sends SYN with its initial sequence number.
2. Server sends SYN-ACK with its own initial sequence number plus an ACK of the client's.
3. Client sends ACK.
4. Connection established. Data can now flow.

Initial sequence numbers are randomized (RFC 6528) to prevent off-path spoofing.

**TCP Fast Open** (TFO) lets the client send data in the SYN itself on repeat connections, saving an RTT. Supported widely but rarely used in practice — middleboxes drop it.

### 5.4 The TCP State Machine

You don't memorize this, but you should be able to read it when debugging:

```
        +---------+
        | CLOSED  |
        +---------+
             | active open: send SYN
             v
        +----------+
        | SYN_SENT |
        +----------+
             | recv SYN-ACK, send ACK
             v
       +-------------+
       | ESTABLISHED |  <--- data flows here
       +-------------+
             | active close: send FIN
             v
        +-----------+
        | FIN_WAIT_1 |
        +-----------+
             | recv ACK
             v
        +-----------+
        | FIN_WAIT_2 |
        +-----------+
             | recv FIN, send ACK
             v
        +-----------+
        | TIME_WAIT |  <--- linger here ~60s
        +-----------+
             |
             v
        +---------+
        | CLOSED  |
        +---------+
```

A few specific states matter operationally:

- **TIME_WAIT** — after closing a connection, the side that initiated the close lingers in TIME_WAIT for `2 * MSL` (Maximum Segment Lifetime, ~30–120s) to absorb stray packets. Servers that initiate many short-lived connections can have *tens of thousands* of TIME_WAIT entries. Mostly harmless on modern kernels, sometimes problematic if you exhaust ephemeral ports.
- **CLOSE_WAIT** — local side received a FIN but hasn't called `close()` yet. A pile of CLOSE_WAIT entries means the application isn't closing sockets it should be. *This is a bug.*
- **SYN_RECV** with no progression — possible SYN flood attack. Mitigated by **SYN cookies**.

`ss -tan state established` to see active TCP connections. `ss -tan state time-wait | wc -l` to count TIME_WAIT.

### 5.5 Congestion Control, Briefly

The most consequential thing TCP does beyond reliability: **slow itself down when the network is congested**. Without this, the internet would collapse.

The algorithms have evolved:
- **Reno** (1990) — additive increase, multiplicative decrease (AIMD). Classic.
- **CUBIC** (2008) — Linux default. Aggressive on high-bandwidth-delay-product links.
- **BBR** (2016, Google) — models the network instead of just reacting to drops. Significantly faster on lossy links. Now widely deployed (YouTube, Google services).
- **BBRv2/v3** — refinements addressing fairness issues with CUBIC.

Switch Linux to BBR:
```bash
sysctl -w net.ipv4.tcp_congestion_control=bbr
sysctl -w net.core.default_qdisc=fq
```

The visible effect: throughput on long, fat networks (cross-continent transfers) often doubles or triples. Try it before reaching for "the network is slow."

### 5.6 Flow Control vs. Congestion Control

Easy to confuse. Distinct:

- **Flow control** — protect the *receiver* from overflow. The receiver advertises a window ("I can accept N more bytes"); the sender doesn't exceed it. Set by the receiver.
- **Congestion control** — protect the *network* from overflow. The sender estimates available bandwidth and adjusts. Set by the sender.

The sender uses the *minimum* of the receive window and the congestion window for its actual send rate.

### 5.7 Nagle, Delayed ACK, and the Classic Pitfall

**Nagle's algorithm** (1984): if you have small data to send and there's already unacknowledged data in flight, wait — maybe more small data is coming, and you can batch. Saves header overhead on chatty applications like Telnet.

**Delayed ACK**: instead of acknowledging every received segment, wait up to 40–200ms to see if you have data to send back, then piggyback the ACK.

These two interact catastrophically: sender holds a small write waiting for ack; receiver holds the ack waiting for a write to piggyback. Result: a 200ms stall on every small write. Famous bug in many request-response protocols.

The fix: `TCP_NODELAY` socket option (disables Nagle). Most modern HTTP libraries and frameworks set this. If you write low-level networking code, set it.

### 5.8 Keepalives

TCP has a built-in keepalive mechanism: after `tcp_keepalive_time` (default 2 hours!) of idle, send a probe; if no response after `tcp_keepalive_probes` × `tcp_keepalive_intvl`, declare dead.

2 hours is too long for almost any production use case. Either:
- Tune the kernel: `sysctl -w net.ipv4.tcp_keepalive_time=60`
- Enable per-socket via `SO_KEEPALIVE` + `TCP_KEEPIDLE`/`TCP_KEEPINTVL`/`TCP_KEEPCNT`.
- Implement application-layer pings (HTTP/2 PING frames, WebSocket pings).

Without keepalives, an idle connection can linger forever (in EST state on your side, but the other end and any intermediate NATs have long forgotten). The next write times out only when the OS gives up on retransmits — minutes later.

References: [RFC 9293 (TCP)](https://datatracker.ietf.org/doc/html/rfc9293), [RFC 768 (UDP)](https://datatracker.ietf.org/doc/html/rfc768), [BBR paper](https://research.google/pubs/pub45646/), [Cloudflare on TCP TIME_WAIT](https://blog.cloudflare.com/this-is-strictly-a-violation-of-the-tcp-specification/)

---

## Phase 6: DNS

### 6.1 The Hierarchy

DNS is a globally distributed, hierarchical, eventually-consistent key-value store. Names map to records. The hierarchy:

```
.                          (root)
├── com.
│   └── example.com.
│       ├── www.example.com.
│       └── api.example.com.
├── org.
└── io.
```

The trailing dot is the actual root. You usually omit it.

### 6.2 The Players

When your laptop wants to resolve `www.example.com`:

1. Application calls `getaddrinfo("www.example.com")`.
2. OS resolver checks the local cache and `/etc/hosts`.
3. If not cached, OS sends a query to a **recursive resolver** (e.g., `8.8.8.8`, `1.1.1.1`, or your ISP's).
4. The recursive resolver does the work:
   - Queries a **root server** for `.com`'s nameservers.
   - Queries a `.com` **TLD nameserver** for `example.com`'s nameservers.
   - Queries the `example.com` **authoritative nameserver** for the record.
5. Returns the answer to your laptop, caches it for the record's TTL.

You query the recursive resolver. The recursive resolver queries authoritative nameservers. Don't confuse the two.

### 6.3 The Record Types

| Type     | What it does                                  |
|----------|-----------------------------------------------|
| **A**    | Name → IPv4 address                           |
| **AAAA** | Name → IPv6 address                           |
| **CNAME**| Name → another name (alias)                   |
| **MX**   | Mail exchanger for a domain                   |
| **TXT**  | Arbitrary text (SPF, DKIM, verification, etc.)|
| **NS**   | Authoritative nameservers for a zone          |
| **SOA**  | Start of authority — zone metadata            |
| **PTR**  | Reverse DNS (IP → name)                       |
| **SRV**  | Service locator (host + port)                 |
| **CAA**  | Which CAs may issue certs for this name       |
| **DNSKEY/DS/RRSIG** | DNSSEC machinery                   |
| **HTTPS/SVCB** | Modern records carrying HTTP service info |
| **TLSA** | DANE — pin certs in DNS                       |

A few non-obvious facts:

- **CNAMEs can't coexist with other records at the same name.** You can't have `example.com` be a CNAME and also have an MX record. This is why the root domain (`example.com`) almost never CNAMEs; you use **ALIAS** / **ANAME** (provider-specific extensions) or HTTPS records.
- **CNAMEs chain.** `www → app → app-1234.heroku.com → 192.0.2.1`. Each chain step costs a lookup.
- **CNAMEs and apex domains** — historically conflicting; modern providers (Cloudflare, Route 53) implement CNAME flattening at the apex.
- **MX records have priorities** — lower number = higher preference.
- **TXT records carry SPF, DKIM, DMARC, domain-verification challenges, and arbitrary data**. The 255-byte-per-string limit (with multiple strings concatenated) trips people up occasionally.

### 6.4 TTL and Caching

Every record has a **TTL** (Time To Live) in seconds. Recursive resolvers cache for up to this long. Setting TTL is a trade-off:

- **High TTL** (hours/days) — fewer queries, lower load on authoritative servers, slower propagation when records change.
- **Low TTL** (60s) — fast propagation, higher query load, useful around planned changes.

The pragmatic pattern: drop TTL low (60–300s) a day before a planned change so caches expire quickly, do the change, raise TTL back to 3600+ afterward.

Note that **resolvers may ignore TTL** in either direction. Some cache aggressively beyond TTL; some don't cache at all. "DNS propagation" is fundamentally a stochastic process.

### 6.5 DNSSEC

**DNSSEC** signs DNS responses with public-key crypto so resolvers can verify they came from the authoritative source.

- **Chain of trust**: root signs `.com`'s DS record, `.com` signs `example.com`'s DS record, `example.com` signs its own records. Resolver walks the chain.
- **Adoption**: complicated. Many domains have it; many resolvers don't validate. Cloudflare validates by default.
- **DANE (TLSA records)** uses DNSSEC to publish cert pins. Adoption low outside email.

Worth enabling on domains you own. Validation is fine; signing is operational overhead (key rotation, ZSK/KSK, etc.) — most domain operators delegate this to their DNS provider.

### 6.6 DoH, DoT, DoQ

Classical DNS is plaintext over UDP/53 (and TCP/53 for big responses or AXFR). This means:
- ISPs and middleboxes can see every DNS query.
- ISPs can inject responses (block, hijack, censor).
- No integrity outside DNSSEC.

The modern alternatives:
- **DoT** (DNS over TLS, port 853) — encrypted, authenticated. Adopted by mobile OSes ("private DNS").
- **DoH** (DNS over HTTPS, port 443) — same goal, but indistinguishable from regular HTTPS so harder for middleboxes to block. Browsers default to DoH against Cloudflare/Google in many regions.
- **DoQ** (DNS over QUIC, port 853) — newer, fewer connection setup costs. Limited adoption.

The trade-off: encrypted DNS pushes resolution off ISPs and onto a smaller set of providers (Cloudflare, Google, NextDNS), which has its own centralization concerns.

### 6.7 Why DNS Is Slow More Often Than It Should Be

Common pathologies:
- **Recursive resolver cold cache** — first query takes the full hierarchy walk. Subsequent queries are fast.
- **CNAME chains** — multiple lookups, multiplied latency.
- **Slow authoritative servers** — geographically distant from the resolver, no anycast.
- **TTL too low** — every page load triggers a new lookup.
- **`/etc/nsswitch.conf` misconfiguration** — falling back to mDNS or LDAP causes pauses on every lookup.
- **IPv6 AAAA queries timing out** — see Happy Eyeballs in Phase 13.
- **DNS load balancing** (multiple A records returned, application picks one — Java historically caches forever) — connections can target slow or dead IPs.

`dig +stats www.example.com` shows query time. Anything above 50ms warrants investigation.

References: [RFC 1034/1035 (DNS)](https://datatracker.ietf.org/doc/html/rfc1034), [RFC 9499 (DNS Terminology)](https://datatracker.ietf.org/doc/html/rfc9499), [DNS for Rocket Scientists](https://www.zytrax.com/books/dns/)

---

## Phase 7: TLS (the Networking View)

[CRYPTO_FUNDAMENTALS.md](CRYPTO_FUNDAMENTALS.md) Phase 7 covers TLS in cryptographic depth. Here we cover the **networking** view: where TLS fits in the stack, what bytes go where, and why it sometimes stalls.

### 7.1 Where TLS Sits

TLS is a session-layer protocol that runs *over* TCP (or UDP, via DTLS) and *under* an application protocol like HTTP. The stack:

```
| HTTP                       |
| TLS                        |
| TCP                        |
| IP                         |
| Ethernet                   |
```

The same HTTP that runs over TLS (HTTPS) can run over plain TCP (HTTP). TLS adds confidentiality + authenticity. From the application's perspective, it's still a byte stream.

### 7.2 The Handshake, Operationally

TLS 1.3 handshake (the one to know in 2026):

```
Client                                Server
  |                                     |
  |---- ClientHello (SNI, ALPN, ----->|
  |     key shares, supported           |
  |     cipher suites)                  |
  |                                     |
  |<--- ServerHello (chosen cipher,---|
  |     key share)                      |
  |<--- {EncryptedExtensions}          |
  |<--- {Certificate}                  |
  |<--- {CertificateVerify}            |
  |<--- {Finished}                     |
  |                                     |
  |---- {Finished} ------------------>|
  |                                     |
  |---- (encrypted application data)--|
```

One round-trip. (TLS 1.2 was two.) Items in `{}` are encrypted; the early ClientHello/ServerHello are plaintext (necessary to negotiate which keys to derive).

What you'll see on the wire (`tcpdump port 443`):
- 3-way TCP handshake.
- ClientHello (~200–400 bytes).
- ServerHello + Certificate + Finished (often ~1500–4000 bytes — the cert chain is big).
- Client Finished.
- Application data.

The cert chain dominates the bytes. This is why TLS handshakes are noticeably slower on first connection than session resumption.

### 7.3 SNI

**Server Name Indication** — in the ClientHello, the client says which hostname it wants. Lets the server pick the right certificate when many hostnames share an IP.

Operational consequences:
- Without SNI, you can only host one HTTPS site per IP. SNI is universal in practice; ancient Windows XP clients without SNI are no longer relevant.
- SNI is *plaintext* in the ClientHello. Censoring middleboxes can block by hostname even without seeing the encrypted payload.
- **ECH** (Encrypted Client Hello) encrypts the SNI. Adoption is growing slowly. Cloudflare offers it; browsers are rolling out support.

### 7.4 ALPN

**Application-Layer Protocol Negotiation** — in the ClientHello, the client lists the application protocols it's willing to speak (`h2`, `http/1.1`, `h3`, etc.). The server picks one.

This is how HTTP/2 negotiation works: ALPN says "h2," both sides switch to it after the handshake. Without ALPN, you'd need a separate port for HTTP/2 (which nobody wanted).

### 7.5 Session Resumption

Full TLS handshakes are expensive. Resumption avoids them on subsequent connections:

- **Session IDs / session tickets** (TLS 1.2) — server gives the client an opaque ticket; client presents it on reconnect; server short-circuits the handshake.
- **PSK (Pre-Shared Key) resumption** (TLS 1.3) — modern equivalent. Lets the server skip cert verification.
- **0-RTT data** (TLS 1.3) — client can send application data in the very first packet of the resumed connection. Saves a round-trip. Cost: replay vulnerable; only safe for idempotent operations.

Browsers and HTTP clients use this aggressively. The first page load is slow; everything after benefits.

### 7.6 Common Operational Issues

- **Cert expiry** — annual or quarterly outage source. Monitor with `cert-manager`, Prometheus blackbox-exporter, or just `openssl s_client -connect host:443 </dev/null 2>/dev/null | openssl x509 -noout -enddate`.
- **Missing intermediate certs** — server presents leaf only; clients without the intermediate cached fail. Test from a fresh machine, or use `testssl.sh`.
- **Hostname mismatch** — cert doesn't cover the requested SNI hostname. `subjectAltName` must include it.
- **Old TLS versions still enabled** — 1.0/1.1 are deprecated. Disable.
- **Weak ciphers still enabled** — RC4, 3DES, CBC suites. Disable.

References: [RFC 8446 (TLS 1.3)](https://datatracker.ietf.org/doc/html/rfc8446), [Cloudflare's TLS 1.3 deep dive](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/), and [CRYPTO_FUNDAMENTALS.md](CRYPTO_FUNDAMENTALS.md) Phase 7

---

## Phase 8: HTTP/1.1, HTTP/2, HTTP/3

The application-layer protocol that runs the web. The semantics (request/response, methods, headers, status codes) have been stable since HTTP/1.1. What's changed across versions is *how those semantics get on the wire*.

### 8.1 HTTP/1.1

The version everyone learned. Plaintext (over TLS, becoming HTTPS), human-readable.

```
GET /index.html HTTP/1.1
Host: example.com
User-Agent: curl/8.0
Accept: */*

HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 138

<html>...</html>
```

Features that matter:
- **Persistent connections** (keep-alive) — multiple requests on one TCP connection. Default in 1.1.
- **Pipelining** — sending multiple requests before responses arrive. Theoretically supported, practically broken by middleboxes. Almost nobody uses it.
- **Chunked transfer encoding** — `Transfer-Encoding: chunked` for streaming responses without a `Content-Length`.
- **Header bloat** — every request and response has a ~hundred-byte header. Compresses badly because text repeats.

The performance limitation: **head-of-line (HOL) blocking at the request level**. On one TCP connection, response 2 can't start being sent until response 1 finishes. Browsers worked around this by opening 6 parallel connections per origin.

### 8.2 HTTP/2

Released 2015. Same semantics; new wire format. Binary, multiplexed, framed.

Key features:
- **Multiplexing** — multiple concurrent streams over one TCP connection. Browsers stop opening 6 connections.
- **Binary framing** — headers and body in distinct frame types (HEADERS, DATA, SETTINGS, PING, etc.).
- **HPACK header compression** — dictionary + static table compresses HTTP headers to a fraction of HTTP/1.1 size.
- **Server push** — server can preemptively send resources. *Removed by Chrome in 2022* due to wide misuse and minimal benefit. Don't use.
- **Stream prioritization** — clients can hint relative priority of streams. Mostly ignored in practice.

The performance gain: enormous in high-RTT, many-asset scenarios (the web). Most modern HTTPS traffic is HTTP/2.

The fatal flaw: **TCP-level head-of-line blocking**. Streams are independent at the HTTP/2 layer, but TCP delivers bytes in order. A single dropped packet stalls *all* streams on the connection until retransmission completes. The very problem multiplexing was supposed to fix re-emerges below the application layer.

### 8.3 HTTP/3 (over QUIC)

Released as RFC 9114 in 2022. Same semantics; runs over QUIC instead of TCP.

**QUIC** (Quick UDP Internet Connections, RFC 9000) is a transport protocol on top of UDP that implements:
- Multiple independent streams (no TCP-level HOL blocking — each stream is its own ordered flow).
- Built-in TLS 1.3 (one handshake establishes both connection and encryption).
- Connection migration — connections survive IP changes (your laptop switching Wi-Fi to cellular).
- 0-RTT for repeat visits.
- Modern congestion control (BBR by default in most implementations).
- Encrypted headers — middleboxes can see far less.

The wins:
- Faster handshake (one round-trip combined TLS+transport vs. TCP-then-TLS in HTTP/2).
- No head-of-line blocking across streams.
- Connection survives network changes.

The trade-offs:
- UDP is sometimes blocked/rate-limited by middleboxes.
- More CPU than TCP (kernel TCP is highly optimized; QUIC is mostly userland).
- Operational tooling lagging — tcpdump shows encrypted blobs.

### 8.4 Choosing Between Them

- **HTTP/1.1** — still the universal fallback. APIs and load balancers often handle it more uniformly than 2/3. Fine for low-concurrency back-end traffic.
- **HTTP/2** — the default for HTTPS browsers and many APIs. Best when many small requests share a connection.
- **HTTP/3** — increasingly the right default for public-facing traffic, especially mobile. Cloudflare/Google deploy it broadly; most major CDNs offer it.

Negotiation: HTTP/2 via ALPN at TLS handshake. HTTP/3 via the `Alt-Svc` HTTP header or DNS HTTPS records (the modern approach) — the server tells the client "I'm also reachable on HTTP/3 over UDP/443," and the client switches on the next request.

### 8.5 The Bits You Actually Tune

- **Connection reuse** — keepalive on; libraries default-on. If you see 10× too many TCP handshakes, your client is creating new connections per request.
- **Concurrent streams** — HTTP/2 default is 100 concurrent streams per connection. Usually enough.
- **Header limits** — HTTP/2 has frame size limits; servers often default-cap at 8 KB. Big cookies or auth headers can hit this.
- **gzip / brotli** — content compression. Brotli compresses HTML/JS/CSS noticeably better than gzip; widely supported.

References: [RFC 9110 (HTTP semantics)](https://datatracker.ietf.org/doc/html/rfc9110), [RFC 9113 (HTTP/2)](https://datatracker.ietf.org/doc/html/rfc9113), [RFC 9114 (HTTP/3)](https://datatracker.ietf.org/doc/html/rfc9114), [RFC 9000 (QUIC)](https://datatracker.ietf.org/doc/html/rfc9000)

---

## Phase 9: Load Balancing

A load balancer (LB) takes incoming connections or requests and distributes them across many backend servers. Conceptually simple; the details matter enormously.

### 9.1 L4 vs. L7

The first decision:

- **L4 load balancer** — operates at TCP/UDP level. Forwards connections by hashing or round-robin. Doesn't read the payload. Fast, simple, protocol-agnostic. Examples: AWS NLB, HAProxy in TCP mode, IPVS, Linux's BPF-based LBs.
- **L7 load balancer** — operates at the application level (HTTP, gRPC). Reads headers, can route based on path/host/cookie, can rewrite, can terminate TLS. Slower, far more capable. Examples: AWS ALB, Nginx, HAProxy in HTTP mode, Envoy, Traefik.

Use L4 when:
- Protocol isn't HTTP (or routing decisions don't depend on application data).
- Latency-critical paths.
- Backend handles its own TLS.

Use L7 when:
- HTTP routing (path-based, host-based).
- Need authentication, rate limiting, response transformation at the LB.
- Multiple HTTPS sites behind one LB IP (TLS termination + SNI).

Many real architectures stack them: L4 at the network edge for raw scale; L7 closer to the application for smarts.

### 9.2 Algorithms

How does the LB decide which backend gets the next connection/request?

- **Round-robin** — strict rotation. Simple. Doesn't account for backend variance.
- **Weighted round-robin** — same, but with per-backend weights (heavier hosts get more). Useful when backends are heterogeneous.
- **Least connections** — pick the backend with fewest active connections. Good for long-lived connections (websockets, gRPC streams).
- **Least time / EWMA** — pick the backend with lowest exponentially-weighted moving average response time. Handles variance well.
- **Power of two choices (P2C)** — pick two backends at random, choose the one with fewer connections (or lower load). Mitigates the "thundering herd" pathologies of pure least-connections.
- **Ring hash (consistent hashing)** — hash the request (by URL, by client IP) onto a ring of backends. Lets you keep cache locality and minimize churn when backends are added/removed. Memcached and CDN selection use this.
- **Maglev** — Google's variant of consistent hashing with stronger uniformity guarantees. Used in Envoy.
- **IP hash / session affinity** — same client always goes to same backend. Required when sessions are local to backends and no shared store exists.

The pragmatic recommendation: **P2C with least connections** is the right default for most workloads. Round-robin is the right default *only* when backends are homogeneous and requests are short.

### 9.3 Health Checks

The LB must detect dead backends. Three flavors:

- **Active health checks** — LB pings the backend periodically (TCP connect, HTTP GET to a health endpoint).
- **Passive health checks** — LB watches for failures on real traffic; ejects a backend after N consecutive failures.
- **Outlier detection** — statistical: eject the backend that's much slower than its peers, even without overt failures.

The best LBs do all three. Typical settings: active check every 5–10s, eject after 2–3 failures, ban for 30s, recheck.

Health-check endpoints are not free. A `/health` that hits the database is a foot-gun: a database hiccup ejects every backend simultaneously. The right pattern is a lightweight "yes I'm running" check, with a separate, optional deeper check for orchestration.

### 9.4 Connection Draining

When you remove a backend from the pool (deploy, scale-down), in-flight requests need to complete. **Connection draining** (or "graceful shutdown") is the LB feature that:

1. Stops sending new requests to the backend.
2. Lets existing connections finish.
3. Removes the backend after a drain timeout (typically 30s–5min).

This is the difference between a clean rolling deploy and a deploy that 502s some users. Almost every LB supports it; almost every misconfigured deploy forgets to enable it.

### 9.5 Sticky Sessions

Sometimes you want a client's subsequent requests to hit the same backend (in-memory session state, WebSocket connections). Options:

- **Cookie-based stickiness** — LB issues its own cookie tracking the backend. Modern, L7.
- **Source IP hash** — same client IP → same backend. Cheap, but mobile users behind CGN appear as one IP; many users → one backend.
- **TLS session ID** — same session → same backend. Subtle but useful.

Stickiness is a smell. It usually means session state should be externalized (Redis, JWT). When you can avoid it, do.

### 9.6 The Major Products

- **Nginx** — the workhorse. Configuration language is gnarly but mature. Strong as a reverse proxy + L7 LB.
- **HAProxy** — pure-play LB. Best L4 performance; excellent L7. Statistics page is iconic.
- **Envoy** — modern, programmable, observable. Powers Istio service mesh, Cloudflare's edge, many cloud LBs. xDS API for dynamic config. Steeper learning curve.
- **Traefik** — container-native (Docker/K8s labels drive config). Easy to start; fewer features than Envoy.
- **Caddy** — HTTPS-by-default web server with built-in LB. Great for simple cases.
- **AWS ALB / NLB / GCLB** — managed L7 / L4 / global. Pay for the abstraction.
- **IPVS** — Linux kernel L4 LB. Used by Kubernetes' `kube-proxy` in IPVS mode. Very fast.

### 9.7 Anycast and Global LB

The next level: load-balance across geographies via DNS or anycast.

- **DNS-based GSLB** — return different IPs based on the resolver's location. Cheap, fast to deploy, but DNS caching slows failover.
- **Anycast** — advertise the same IP from multiple sites via BGP. Routing picks the topologically nearest. Fast failover, no DNS cache fights. Cloudflare's entire model.
- **Hybrid** — anycast to a regional cluster, then L7 LB within.

CDNs are the productized form of this. Use them.

References: [HAProxy docs](https://www.haproxy.org/), [Envoy architecture](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/intro/intro), ["Maglev: A Fast and Reliable Software Network Load Balancer"](https://research.google/pubs/pub44824/)

---

## Phase 10: Modern Realities

The bits of networking that have changed in the last decade.

### 10.1 CDNs

A **CDN** (Content Delivery Network) caches your content close to users. The big ones in 2026: Cloudflare, Fastly, Akamai, AWS CloudFront, Google Cloud CDN, Bunny, KeyCDN.

What a CDN actually does:
- **Edge caching** — static assets cached at hundreds of POPs globally. First user in a region pays the latency; everyone else gets local response.
- **Anycast routing** — your DNS points to one IP; BGP delivers each user to the nearest edge.
- **TLS termination** — handshake at the edge; cheap onward connection to origin (often kept warm).
- **Compression** — modern codecs (Brotli, Zstandard) applied at edge.
- **HTTP/2 and HTTP/3 termination** — even if origin only speaks HTTP/1.1.
- **Security** — WAF, DDoS mitigation, bot detection. The "Cloudflare in front of everything" pattern.
- **Edge compute** — Workers (Cloudflare), Lambda@Edge (AWS), Compute@Edge (Fastly). Run code at the edge.

For most public-facing sites, putting a CDN in front is the single highest-leverage network optimization available.

### 10.2 eBPF — Networking as Code

**eBPF** is a Linux kernel feature that lets you run small, verified, sandboxed programs in the kernel — including in the networking path. It's eating the networking stack:

- **Cilium** — eBPF-based K8s CNI; replaces kube-proxy and many iptables paths with eBPF programs. Faster, more observable.
- **Katran** — Facebook's eBPF-based L4 LB.
- **bpftrace, bpf_trace_printk** — live-tracing the kernel network stack without losing packets.
- **Pixie, Hubble, Inspektor Gadget** — eBPF-based observability for K8s.

If you operate K8s, eBPF is increasingly unavoidable. It replaces a decade of iptables-based plumbing with something far more inspectable and faster at scale.

### 10.3 Service Mesh

In K8s and similar, a **service mesh** (Istio, Linkerd, Cilium Service Mesh, Consul Connect) injects a sidecar (or, increasingly, an eBPF dataplane) into every pod that handles:

- mTLS between services.
- L7-aware retry/timeout/circuit-breaking policies.
- Traffic shifting / canarying.
- Observability — distributed tracing, request-level metrics.

Service meshes solve real problems at the cost of substantial operational complexity. They're the right answer at scale, an overkill at small scale. The K8s networking guide goes deeper.

### 10.4 IPv6 in 2026

Status check: IPv6 traffic is a majority on most mobile networks and many ISPs. Major cloud providers are dual-stack everywhere. New deployments should target dual-stack at minimum, IPv6-first when possible.

If you've never paid attention to v6, the operational habits to pick up:
- ACLs and firewall rules need v6 versions or they're effectively disabled.
- DNS AAAA records need to be correct or browsers fall back via Happy Eyeballs (slow).
- Logging that assumes 15-char IPv4 addresses breaks.
- The 7-day-renewable SLAAC prefix can change; long-lived ACLs against host addresses fail.

References: [Cloudflare's eBPF posts](https://blog.cloudflare.com/tag/ebpf/), [Cilium documentation](https://docs.cilium.io/), [APNIC IPv6 measurement](https://stats.labs.apnic.net/ipv6)

---

## Phase 11: Diagnosing Network Problems

Knowing the tools is half the job. The other half is knowing which tool to reach for first.

### 11.1 The Toolkit

| Tool                | What it does                              | First reach for...                                  |
|---------------------|-------------------------------------------|------------------------------------------------------|
| `ping`              | ICMP echo to a host                       | Is the host reachable at all?                        |
| `dig`               | DNS queries with detail                   | Is DNS resolution working?                           |
| `traceroute` / `mtr`| Map the path between hosts                | Where in the network is the problem?                 |
| `tcpdump` / `wireshark` | Capture and inspect packets            | What's actually on the wire?                         |
| `ss` (or `netstat`) | Show local socket state                    | What connections does this host have open?           |
| `nc` (netcat)       | Raw TCP/UDP client and server              | Does the port respond at all?                        |
| `curl -v`           | HTTP request with full visibility          | Where does the HTTP exchange fail?                   |
| `openssl s_client`  | Manual TLS connection                      | Cert / handshake / TLS protocol issues               |
| `iperf3`            | Bandwidth measurement                      | Is the link actually as fast as advertised?          |
| `nmap`              | Port scanning, OS fingerprinting           | What's listening?                                    |
| `ip` / `ifconfig`   | Interface and routing inspection           | What does this host think its network looks like?    |
| `host` / `nslookup` | Quick DNS lookups                          | Lighter than `dig` for a sanity check.               |

### 11.2 Prescriptive Usage

**"This host is unreachable"**:
1. `ping <host>` — works? Connectivity is fine; problem is higher up.
2. `ping <gateway>` — works? Local network is fine; problem is upstream.
3. `traceroute <host>` — where do the packets stop?
4. `ip route` — is the route as expected?
5. `dig <host>` — does the name resolve to what you expect?

**"The application sees connection refused / timeout"**:
1. `nc -zv <host> <port>` — does the port respond at all?
2. If refused: nothing listening, or firewall actively rejecting.
3. If timeout: firewall silently dropping, or host unreachable.
4. `ss -tlnp` on the destination — is something actually bound to that port?
5. `iptables -L -n` (or `nftables list ruleset`) on the destination — is there a rule blocking?

**"HTTPS is slow / failing"**:
1. `curl -v https://host/` — read the full negotiation. Where does it stop?
2. `openssl s_client -connect host:443 -servername host` — manual TLS. See cert chain, alerts, protocol.
3. `dig +trace host` — slow DNS adding latency?
4. `curl -w '@curl-format.txt' -o /dev/null -s https://host/` — break down DNS / TCP / TLS / TTFB / transfer.

A useful `curl-format.txt`:
```
time_namelookup:    %{time_namelookup}\n
time_connect:       %{time_connect}\n
time_appconnect:    %{time_appconnect}\n
time_pretransfer:   %{time_pretransfer}\n
time_starttransfer: %{time_starttransfer}\n
time_total:         %{time_total}\n
```

**"Random packet loss / weird latency"**:
1. `mtr --report -c 100 <host>` — runs traceroute + ping continuously. Loss at hop N but not N+1 = problem at that hop.
2. `ping -f <host>` (flood) — saturates the path; reveals burst loss.
3. `iperf3` — measure actual throughput. Compare to expected link speed.

**"What's happening on the wire?"**:
```bash
tcpdump -i any -nn -s 0 host 10.0.0.5 and port 443 -w capture.pcap
# Then open in Wireshark for analysis.
```

`tcpdump` flags worth remembering:
- `-i any` — capture on all interfaces (Linux).
- `-nn` — don't resolve names or ports.
- `-s 0` — capture full packets (default is truncated).
- `-w file.pcap` — write to file (read with `tcpdump -r` or Wireshark).
- BPF filters: `host`, `port`, `net`, `and`, `or`, `not`.

**"Who is bound to that port?"**:
```bash
ss -tlnp                # All TCP listeners + process info
ss -tan state established   # Active connections
ss -s                   # Summary statistics
```

### 11.3 The Habit That Pays Off

When something breaks: start at L1 and walk up. Cable in? Link lit? IP assigned? Gateway pingable? DNS resolving? TCP handshaking? TLS handshaking? HTTP returning 200? Each layer ruled out is a piece of the problem space eliminated. Skipping levels because "it's probably DNS" wastes time when it's actually a loose RJ45.

References: [`tcpdump` man page](https://www.tcpdump.org/manpages/tcpdump.1.html), [Wireshark User's Guide](https://www.wireshark.org/docs/wsug_html_chunked/), ["Brendan Gregg's networking tools"](https://www.brendangregg.com/Perf/network.html)

---

## Phase 12: Practical Recipes

### 12.1 Connecting Two Linux Machines with an Ethernet Cable

Two machines, one Ethernet cable, no router. The most direct possible network. Useful for:
- Transferring large files between machines without saturating Wi-Fi.
- Bringing up a headless Raspberry Pi without a network.
- Doing controlled bandwidth/latency tests with `iperf3`.
- Backing up a laptop to a desktop at gigabit speed.

**Step 1: The cable**

Modern NICs (anything made in the last ~15 years) implement **Auto-MDI-X**, which detects the wiring and crosses internally if needed. So **any** Ethernet cable works — you do not need a crossover cable. A standard Cat 5e or Cat 6 patch cable from your nearest drawer is fine.

For gigabit (1000 Mbps), all four pairs must be wired. Older or damaged cables sometimes have only two pairs working and you fall back to 100 Mbps without warning. If speed feels wrong, check.

**Step 2: Verify the link comes up**

Plug both ends in. On each machine:

```bash
ip link show               # Find your wired interface (e.g., eth0, enp3s0, eno1)
sudo ethtool enp3s0        # Or whatever your interface is named
```

Look for:
```
Link detected: yes
Speed: 1000Mb/s
Duplex: Full
```

If "Link detected: no" — bad cable, bad port, or interface administratively down (`sudo ip link set enp3s0 up`).

**Step 3: Assign static IPs (manual approach)**

The simplest setup: pick a private subnet that's not in use elsewhere. `10.42.0.0/24` is safe. Give each machine an IP in it.

Machine A (let's call it `desktop`):
```bash
sudo ip addr add 10.42.0.1/24 dev enp3s0
sudo ip link set enp3s0 up
```

Machine B (`laptop`):
```bash
sudo ip addr add 10.42.0.2/24 dev enp4s0
sudo ip link set enp4s0 up
```

Test connectivity:
```bash
# On laptop:
ping -c 3 10.42.0.1
```

If the ping works, you're done with the networking part. Total elapsed time: ~30 seconds.

These addresses are **not persistent across reboot**. They live in the running kernel state, not in any config. For a one-off transfer that's exactly what you want — no cleanup needed.

**Step 3 (alternative): NetworkManager**

If you'd rather use the desktop's network tool:

```bash
nmcli connection add type ethernet ifname enp3s0 con-name direct \
    ip4 10.42.0.1/24 ipv4.method manual
nmcli connection up direct
```

To remove later: `nmcli connection delete direct`.

**Step 3 (alternative): link-local automatic**

If you don't want to assign anything manually, both Linux and macOS will auto-configure a **link-local** address (in the `169.254.0.0/16` range) when no DHCP server responds. Just bring both interfaces up and wait ~30 seconds. Find each other with:

```bash
avahi-browse -a    # Or just look at `ip addr` on both sides.
```

Speeds and conveniences are the same; addresses are uglier.

**Step 4: Transferring files**

You have several options, ordered roughly from "most familiar" to "fastest":

**`scp` — familiar, encrypted, slow-ish**

```bash
# On laptop, copy big.tar to desktop:
scp big.tar user@10.42.0.1:/home/user/
```

Pros: zero setup if SSH already works between the boxes. Authenticated, encrypted.
Cons: encryption overhead can cap you at ~50–80 MB/s on older hardware. Doesn't resume.

**`rsync` over SSH — resumable, incremental, slightly faster**

```bash
rsync -avP --info=progress2 big.tar user@10.42.0.1:/home/user/
# Or, to mirror a directory:
rsync -avP --delete src/ user@10.42.0.1:/home/user/dst/
```

Pros: resumes on disconnect (`-P` = `--partial --progress`). Skips unchanged files on re-run. The right default for backups.
Cons: still SSH-encrypted, so same speed cap as `scp`. Use `-z` for compression *only* if the data is highly compressible AND your CPU is fast enough not to bottleneck the link — for local gigabit transfers of binary data, leave compression off.

**`rsync` over SSH with a fast cipher**

The default OpenSSH cipher (chacha20-poly1305) is good but not the fastest. For LAN-only transfers where you've decided you trust the link:

```bash
rsync -avP -e 'ssh -c aes128-gcm@openssh.com' big.tar user@10.42.0.1:/home/user/
```

`aes128-gcm` benefits from AES-NI on most modern CPUs and can substantially raise the throughput ceiling.

**`nc` (netcat) — fastest, unencrypted, single-shot**

When you don't care about encryption (you're literally on a direct cable), netcat moves bytes at line rate:

```bash
# On the receiver (desktop):
nc -l -p 9000 > big.tar

# On the sender (laptop):
nc 10.42.0.1 9000 < big.tar
```

Pros: zero protocol overhead, gigabit-saturating, works without any auth setup.
Cons: no auth, no encryption, no resume, no progress display, can't detect the file actually arrived complete (you have to verify with `sha256sum`).

Add a progress display:
```bash
# Sender:
pv big.tar | nc 10.42.0.1 9000
```

(`pv` = pipe viewer; `apt install pv`.)

Pipe through compression on the fly if the data is compressible:
```bash
# Receiver:
nc -l -p 9000 | zstd -d > big.tar

# Sender:
zstd -1 -c big.tar | nc 10.42.0.1 9000
```

`zstd -1` is fast enough that even with the CPU work, total throughput often exceeds an uncompressed gigabit link for compressible data.

**`python -m http.server` — quick HTTP server**

```bash
# On the source:
cd /path/to/share
python3 -m http.server 8000

# On the destination:
curl -O http://10.42.0.1:8000/big.tar
# Or just open http://10.42.0.1:8000/ in a browser.
```

Useful for browsing directories from another box, or pulling files from a phone/tablet that won't run rsync.

**`dd | nc` — raw block-device cloning**

Imaging a disk over the wire (e.g., cloning a Pi SD card to a backup):

```bash
# On the destination:
nc -l -p 9000 | zstd -d > /home/user/disk.img

# On the source:
sudo dd if=/dev/sdX bs=1M | zstd -1 -c | pv | nc 10.42.0.1 9000
```

Doubly useful: `dd` for the raw block read, `zstd` to compress the empty-space-filled bytes, `pv` for progress.

**Speed expectations**

| Link              | Theoretical | Practical (TCP, sustained)        |
|-------------------|-------------|-----------------------------------|
| 100Base-T         | 100 Mbps    | ~11 MB/s                          |
| 1000Base-T (gig)  | 1 Gbps      | ~112 MB/s                         |
| 2.5GBase-T        | 2.5 Gbps    | ~280 MB/s                         |
| 10GBase-T         | 10 Gbps     | ~1.1 GB/s — if disk can keep up   |

If you don't get close to the expected ceiling:
1. Run `iperf3` to test the raw link without the disk/CPU in the way.
2. Check disk read/write speed (`hdparm -t /dev/sdX` on Linux).
3. Verify both sides actually negotiated the expected speed (`ethtool`).
4. Check cable category — a Cat 5 (not 5e) won't reach gigabit.
5. SSH-encrypted transfers will cap below the line rate on older CPUs.

**Bonus: sharing an internet connection over the direct cable**

Sometimes you want to bring up a freshly-installed Pi or a Raspberry Pi Zero 2 W that has no Wi-Fi yet — and you want it to have internet through the desktop's connection. This is "Internet Connection Sharing" in Windows; on Linux:

```bash
# On the gateway machine (with internet), set up NAT and forwarding.
# Replace eth-uplink with the interface that has internet (e.g., wlan0),
# and eth-direct with the direct cable interface.

# Enable forwarding:
sudo sysctl -w net.ipv4.ip_forward=1

# Set up masquerade NAT:
sudo iptables -t nat -A POSTROUTING -o eth-uplink -j MASQUERADE
sudo iptables -A FORWARD -i eth-direct -o eth-uplink -j ACCEPT
sudo iptables -A FORWARD -i eth-uplink -o eth-direct \
    -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Give the other machine an IP if it doesn't have one:
sudo ip addr add 10.42.0.1/24 dev eth-direct
```

On the Pi side, set the default gateway and a DNS server:
```bash
sudo ip route add default via 10.42.0.1
echo 'nameserver 1.1.1.1' | sudo tee /etc/resolv.conf
```

For permanent setup, install `dnsmasq` on the gateway machine and let it serve DHCP and DNS on the direct-cable interface — far easier than configuring each new device by hand.

**Bonus: bidirectional file sharing with `sshfs`**

If you'd rather mount the remote filesystem instead of copying:
```bash
mkdir ~/remote
sshfs user@10.42.0.1:/home/user/ ~/remote/
# Use ~/remote/ as any local directory. Unmount with:
fusermount -u ~/remote
```

### 12.2 Other Quick Recipes

**Checking what your public IP is**:
```bash
curl https://ifconfig.me
curl https://icanhazip.com
```

Note that what you see is the *post-NAT* address. Your machine's interface address is internal.

**Testing for IPv6 connectivity**:
```bash
curl -6 https://ifconfig.co
ping6 google.com
```

If you have v6, the first command prints your v6 address; the second pings. If not, both fail.

**Reverse DNS lookup**:
```bash
dig -x 8.8.8.8
host 8.8.8.8
```

**Resolving a name from a specific DNS server** (useful for verifying authoritative answers vs. cached):
```bash
dig @8.8.8.8 example.com
dig @1.1.1.1 example.com
dig +trace example.com         # Follow from root
```

**Checking what cert a site is serving**:
```bash
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
    | openssl x509 -noout -text \
    | grep -E "(Subject:|Not (Before|After)|DNS:|Issuer:)"
```

**Watching live TCP connections**:
```bash
watch -n 1 'ss -tan state established | head -20'
```

**Finding the process holding a port**:
```bash
sudo ss -tlnp sport = :8080
sudo lsof -i :8080
```

---

## Phase 13: Real-World Problems

The classics that keep showing up. If you've never seen these, you will.

### 13.1 MTU and Path MTU Discovery Black Holes

You set up a VPN or a GRE tunnel or anything that encapsulates IP packets. Suddenly *some* websites work and others time out. The symptom: small responses fine; large responses hang.

The cause: the tunnel reduces effective MTU below 1500. Large packets, sent with the Don't-Fragment (DF) bit set, hit a router that says "too big, fragment please" — but its ICMP Fragmentation Needed reply gets silently dropped by some firewall, leaving the sender to retransmit the same too-big packet forever. This is **PMTUD black hole**.

Fixes:
- **MSS clamping** — at the tunnel, rewrite outgoing TCP SYNs to advertise a smaller MSS, so the other end never sends packets too big in the first place.
  ```bash
  iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
      -j TCPMSS --clamp-mss-to-pmtu
  ```
- **Lower the interface MTU** explicitly on the tunnel.
- Stop dropping ICMP everywhere. (Cultural problem; usually the firewall team won't budge.)

### 13.2 Happy Eyeballs and the IPv6 Slowdown

A site has both A and AAAA records. Your client tries IPv6 first. If v6 is broken (no route, slow path), pure TCP timeout is 30+ seconds, and you blame the site.

**Happy Eyeballs** (RFC 8305) is the solution: try v6 and v4 in parallel with a small head start for v6 (~200ms), use whichever succeeds first. Implemented by browsers, modern OS resolvers, and most networking libraries.

If you're writing networking code, use a library that implements Happy Eyeballs. If you're operating a dual-stack network, monitor v6 path health — broken AAAA records are a silent 200ms latency tax that's invisible to users with happy-eyeballs clients and catastrophic to ones without.

### 13.3 The Slow DNS Tax

Symptom: page loads "stutter" on first connect to each resource. `curl --resolve` (skip DNS) makes it fast.

Causes:
- Resolver is far away. Switch to a fast local resolver (1.1.1.1, 8.8.8.8, your CDN's).
- DNS over a slow link (cellular). Switch to DoH/DoT, sometimes paradoxically faster because it uses warm TCP connections.
- IPv6 AAAA timing out (Happy Eyeballs to the rescue, but the first query is still affected).
- TTL too low; every resource triggers a new lookup.
- Long CNAME chain.

`dig +stats` is your friend.

### 13.4 TLS Handshake Stalls

Symptom: HTTPS connections feel slow on first connection to a new host, fast on subsequent connections.

Usually fine — TLS handshakes are inherently expensive. But pathological:
- OCSP-must-staple set, but OCSP responder is slow. Browser blocks waiting.
- Certificate chain incomplete; client has to fetch missing intermediates.
- TLS 1.2 still in use; consider 1.3.
- HTTP/3 disabled; you're paying the full TCP+TLS handshake.

The diagnostic: `curl -w '@format' -o /dev/null https://...` to split DNS / TCP / TLS / TTFB time.

### 13.5 Asymmetric Routing

In multi-homed setups (multiple uplinks, multi-region clouds), outbound traffic goes one way and inbound replies come back another. Most of the time this works fine. When it doesn't:
- Stateful firewalls drop the "replies" because they didn't see the SYN on this interface.
- Source-address-based load balancing breaks session affinity.
- IPsec VPNs that expect symmetric flows fail randomly.

Diagnostics: `tcpdump` simultaneously on both possible paths.

Fixes: route policy (Linux `ip rule`), TCP-MSS-clamping, or making one path the "preferred" with the other as standby.

### 13.6 The Connection Pool Surprise

Your application has a connection pool to a database. Pool min=10, max=100. Idle connections sit there for hours. Then suddenly, every request to that DB fails with "connection reset" or hangs forever.

The cause: a NAT or stateful firewall between you and the DB has expired your connection from its conntrack table (default 5 days, but often shorter). The DB still thinks the connection is open; you still think it's open; the NAT in the middle has forgotten. Your next packet on that connection gets dropped or RST'd.

Fixes:
- Enable TCP keepalives (Phase 5.8) with intervals well under the NAT timeout.
- Cycle pool connections periodically (every N minutes).
- Validate connections on borrow (do a `SELECT 1` before handing out a pool connection).

### 13.7 The IPv4 Source-Port Exhaustion

A busy proxy or NAT box hits the limit of source ports. Default ephemeral port range is ~28K on Linux. Combined with 60-second TIME_WAIT, you cap at ~466 connections/sec to a single destination IP+port.

Symptoms: `EADDRNOTAVAIL`, "Cannot assign requested address." Connections start failing intermittently.

Fixes:
- Widen the ephemeral port range: `sysctl -w net.ipv4.ip_local_port_range='10000 65535'`.
- Enable port reuse: `sysctl -w net.ipv4.tcp_tw_reuse=1`.
- Use connection pooling on the client.
- Add more source IPs and round-robin across them.
- Talk to multiple destination IPs (each is its own ephemeral-port namespace).

### 13.8 The "Works on the Other Machine" Problem

DNS, hosts file, route table, firewall, TLS trust store, proxy environment variables, IP address conflicts, ISP transparent proxies — any of these can differ between two machines and create the "but it works for me" mystery.

A debugging script that's worth its weight:

```bash
echo "=== resolv.conf ==="; cat /etc/resolv.conf
echo "=== hosts ==="; cat /etc/hosts
echo "=== ip route ==="; ip route
echo "=== iptables ==="; sudo iptables -L -n -v
echo "=== env proxies ==="; env | grep -i proxy
echo "=== DNS test ==="; dig +short example.com @1.1.1.1; dig +short example.com
echo "=== TLS test ==="; echo | openssl s_client -connect example.com:443 -servername example.com 2>&1 | grep -E "(Verify|subject=|issuer=)"
echo "=== curl test ==="; curl -sSI https://example.com/ -w 'HTTP %{http_code}, total %{time_total}s\n' -o /dev/null
```

References: [RFC 8305 (Happy Eyeballs v2)](https://datatracker.ietf.org/doc/html/rfc8305), [Cloudflare on PMTUD black holes](https://blog.cloudflare.com/path-mtu-discovery-in-practice/), [Vincent Bernat — Linux TIME_WAIT](https://vincent.bernat.ch/en/blog/2014-tcp-time-wait-state-linux)

---

## Phase 14: What Happens When You Type `google.com` and Press Enter

The classic interview question. Use it as a capstone to integrate every layer.

### 14.1 The Browser Does Some Pre-Work

Before any network: browser autocompletes the URL, checks its own cache (memory, then disk) for cached responses, applies HSTS (if `google.com` is in the HSTS preload list, the browser refuses HTTP). Sets up a request: `GET / HTTP/1.1` (or `/2` or `/3`), with the user's cookies for the domain.

### 14.2 DNS Resolution

Browser asks the OS to resolve `google.com`.

- OS checks its own cache.
- If miss, OS asks the system resolver (configured in `/etc/resolv.conf` or via NetworkManager / systemd-resolved on Linux; via SystemConfiguration on macOS).
- The system resolver checks its cache.
- If miss, it queries a recursive resolver — typically `1.1.1.1` or `8.8.8.8` or the ISP's. The query may be UDP/53, or DoT/853, or DoH/443.
- The recursive resolver (if it's cold-cached) walks the hierarchy: root → `.com` TLD → `google.com` authoritative — and gets the A/AAAA records.
- Anycast routing means the recursive resolver's queries take very short paths.
- Modern browsers query A and AAAA in parallel; pick whichever returns first.

For `google.com`, the answer comes back nearly instantly — Google's anycast DNS infrastructure is among the fastest in the world.

### 14.3 TCP (or QUIC) Connection

Browser opens a connection to the resolved IP, port 443.

- If HTTP/3 is supported (and a recent Alt-Svc cached, or DNS HTTPS records indicate it), the browser tries QUIC over UDP/443 first. Otherwise TCP.
- TCP: three-way handshake. SYN → SYN-ACK → ACK. One RTT.
- The IP packet hops through your home router, your ISP's edge, an IXP (Internet Exchange Point), Google's network. The path is whatever BGP has decided; for `google.com` from most places, it's short — Google's network is one BGP hop from many ISPs.

### 14.4 TLS Handshake

Once TCP is up:

- ClientHello: cipher suites, SNI (`google.com`), ALPN (`h2`, `http/1.1`, `h3`), key shares.
- ServerHello + Certificate + Finished. Cert chain: leaf (`*.google.com`) → intermediate (`GTS CA 1C3`) → root (in browser's trust store).
- Client Finished.
- If TLS 1.3: one round-trip. If session resumed: 0-RTT possible.

The browser validates the cert chain (issuer, expiry, SAN match, OCSP/CT checks). If anything fails: scary red page.

### 14.5 The HTTP Request

Encrypted data flows. The browser sends:

```
GET / HTTP/2
:authority: google.com
:scheme: https
:method: GET
:path: /
accept: text/html,application/xhtml+xml...
accept-encoding: gzip, deflate, br, zstd
accept-language: en-US,en;q=0.9
user-agent: ...
cookie: NID=...; 1P_JAR=...
```

(HTTP/2 binary frames; rendered here as text for readability.)

The server processes the request. Behind the scenes:
- A Google front-end load balancer (anycast) terminated the TLS.
- Routes the decrypted request to the appropriate backend (`google.com` serves the homepage, but also handles redirects, A/B testing, user-specific routing).
- Backend assembles a response. Often this is cached at the edge for unauthenticated users.

### 14.6 The HTTP Response

```
HTTP/2 200
content-type: text/html; charset=UTF-8
content-encoding: gzip
cache-control: private, max-age=0
set-cookie: ...
strict-transport-security: max-age=31536000
content-security-policy: ...
alt-svc: h3=":443"; ma=2592000

<compressed HTML body>
```

The Alt-Svc header tells the browser "next time, try HTTP/3 over UDP/443." HSTS locks the domain to HTTPS for a year.

### 14.7 The Browser Parses, Discovers More Resources, Renders

The HTML parser starts streaming. It encounters `<link rel="stylesheet">`, `<script>`, `<img>`. Each is a new request. The browser:
- Reuses the existing connection for `google.com` resources (HTTP/2 multiplexing).
- Opens new connections to other origins (`fonts.googleapis.com`, `apis.google.com`, etc.) — each needs its own DNS resolution, TCP/QUIC, TLS.
- Browsers limit per-origin connection count (still ~6 for HTTP/1.1; unlimited streams over one connection for HTTP/2).

Resources arrive; rendering proceeds. CSS blocks rendering; JS may block or be async/defer. The first paint can happen before all resources are loaded.

### 14.8 What You've Just Used

Walking that flow, you've touched:
- Layer 1: the physical link to your Wi-Fi router.
- Layer 2: Ethernet/Wi-Fi frames, ARP for the gateway MAC, possibly VXLAN inside Google's data center.
- Layer 3: IP (v4 or v6), routing across many ASes via BGP, possibly NAT at your home router and CGN at your ISP.
- Layer 4: TCP (or QUIC over UDP), congestion control, flow control.
- Layer 5–6: TLS 1.3 handshake, cert chain verification.
- Layer 7: HTTP/2 or HTTP/3 request/response, cookies, HSTS, CSP, browser cache.
- Plus: DNS for resolution, anycast for nearest server, possibly Happy Eyeballs for dual-stack, possibly a CDN at the edge.

If you can describe each of those steps and what could go wrong at each, you understand networking at a senior engineer's level.

---

## Mastery Checklist

You're solid on networking fundamentals when you can, without looking anything up:

- Read a `tcpdump` capture line and identify protocol, flags, sequence numbers.
- Subnet a network: convert `/19` to dotted-decimal, find the broadcast address, identify host range.
- Distinguish ARP from IP routing and explain when each runs.
- Trace the path a packet takes from your laptop to a remote server and name what changes at each hop.
- Explain why TCP `TIME_WAIT` exists and why piles of `CLOSE_WAIT` are a bug.
- Diagnose the difference between "connection refused" and "connection timeout" and explain what's happening at the network layer in each.
- Choose between L4 and L7 load balancing for a given workload.
- Pick HTTP/1.1, HTTP/2, or HTTP/3 for a given scenario and justify the choice.
- Explain DNS: recursive vs. authoritative, A vs. CNAME vs. AAAA, TTL trade-offs.
- Describe the TLS 1.3 handshake step by step and name what each byte is for.
- Use `dig`, `mtr`, `tcpdump`, `ss`, `curl -v`, `openssl s_client` and pick the right one for a given problem.
- Set up direct gigabit transfer between two Linux machines without consulting docs.
- Recognize a PMTUD black hole when you see one.
- Walk through what happens when a user types a URL and presses Enter, naming every layer.

---

## Recommended Reading Path

1. **[Computer Networks](https://www.pearson.com/store/p/computer-networks/P100002579376)** (Tanenbaum & Wetherall) — the canonical textbook. Read the chapters on link, network, and transport layers.
2. **[TCP/IP Illustrated, Volume 1](https://www.pearson.com/store/p/tcp-ip-illustrated-volume-1/P100002600620)** (Stevens, Fall) — packet-level depth. Old but the parts that matter haven't changed.
3. **[High Performance Browser Networking](https://hpbn.co/)** (Ilya Grigorik) — free online. The book on how browsers, networks, and protocols interact. Read end-to-end.
4. **[Beej's Guide to Network Programming](https://beej.us/guide/bgnet/)** — when you want to write socket code. Free.
5. **The relevant RFCs**: 1122 (Hosts), 791 (IPv4), 8200 (IPv6), 9293 (TCP), 768 (UDP), 1034/1035 (DNS), 8446 (TLS 1.3), 9110 (HTTP semantics), 9000 (QUIC), 9114 (HTTP/3). Read in roughly this order.
6. **[Cloudflare's blog](https://blog.cloudflare.com/)** — perpetually publishes the best real-world networking writing on the internet. Especially anything by Marek Majkowski.
7. **[Julia Evans' zines](https://wizardzines.com/)** — short, illustrated, deeply practical. *How DNS Works* and *Bite Size Networking* are especially good.

**Adjacent guides in this repo:** [Linux Networking](LINUX_NETWORKING_STUDY_GUIDE.md) (operating the stack these protocols ride on), [Advanced Linux](ADVANCED_LINUX_STUDY_GUIDE.md) (TCP tuning, nftables, BBR), [WebSockets](WEBSOCKETS_STUDY_GUIDE.md), [Caddy](CADDY_STUDY_GUIDE.md)/[Cloudflare](CLOUDFLARE_STUDY_GUIDE.md) (the proxies and edges), and [Cryptography Fundamentals](CRYPTO_FUNDAMENTALS.md) (inside the TLS handshake).

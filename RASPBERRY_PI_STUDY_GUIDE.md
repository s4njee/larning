# Embedded Linux on the Raspberry Pi Zero 2 W

A practical, board-on-your-desk guide to embedded Linux on the Raspberry Pi Zero 2 W. This is the companion to the [ESP32 guide](ESP32_STUDY_GUIDE.md): the ESP32 covers bare-metal microcontrollers (no OS, one program, microsecond GPIO); this guide covers the other half — running a full Linux kernel on constrained hardware, where you get filesystems, networking, multitasking, and a package manager, but trade away real-time guarantees and single-digit-milliamp sleep.

Primary references: [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/), [Device Tree Reference](https://www.raspberrypi.com/documentation/computers/configuration.html#device-trees-overlays-and-parameters), [libgpiod](https://git.kernel.org/pub/scm/libs/libgpiod/libgpiod.git/about/), [Raspberry Pi Pinout](https://pinout.xyz/)

---

## Table of Contents

1. [The Mental Model](#1-the-mental-model)
2. [The Hardware](#2-the-hardware)
3. [The Boot Process](#3-the-boot-process)
4. [OS Selection & Image Creation](#4-os-selection--image-creation)
5. [Headless Setup & Serial Console](#5-headless-setup--serial-console)
6. [Device Trees & Overlays](#6-device-trees--overlays)
7. [GPIO — General-Purpose I/O](#7-gpio--general-purpose-io)
8. [I2C — Inter-Integrated Circuit](#8-i2c--inter-integrated-circuit)
9. [SPI — Serial Peripheral Interface](#9-spi--serial-peripheral-interface)
10. [UART & Serial Communication](#10-uart--serial-communication)
11. [Camera (CSI)](#11-camera-csi)
12. [Power Management & Low-Power Operation](#12-power-management--low-power-operation)
13. [Systemd — Running Your Application](#13-systemd--running-your-application)
14. [Networking — WiFi, Bluetooth & USB Gadget](#14-networking--wifi-bluetooth--usb-gadget)
15. [Cross-Compilation & Remote Development](#15-cross-compilation--remote-development)
16. [Real-Time & Performance Tuning](#16-real-time--performance-tuning)
17. [Security for Deployed Devices](#17-security-for-deployed-devices)
18. [Practical Projects](#18-practical-projects)
19. [Pi Zero 2 W vs ESP32 — When to Use Which](#19-pi-zero-2-w-vs-esp32--when-to-use-which)
20. [Mastery Checklist](#20-mastery-checklist)

---

## 1. The Mental Model

### Microcontroller vs. Embedded Linux

The [ESP32 guide](ESP32_STUDY_GUIDE.md) teaches the microcontroller world: one program running on bare metal (or FreeRTOS), direct register access, microsecond-precision GPIO, deep sleep at 10 µA, and you cross-compile-and-flash every change. The Pi Zero 2 W is the opposite end of embedded:

| Dimension | ESP32 (Microcontroller) | Pi Zero 2 W (Embedded Linux) |
|---|---|---|
| **OS** | None, or FreeRTOS | Full Linux kernel + userspace |
| **Programming** | C/MicroPython, cross-compile+flash | Any language, edit on device or cross-compile |
| **Boot time** | ~200 ms | ~15–30 s (can be optimized to ~5 s) |
| **RAM** | 520 KB | 512 MB |
| **Storage** | 4 MB flash (typical) | microSD (8–128 GB) |
| **GPIO latency** | ~50 ns (register-level) | ~1–10 µs (kernel overhead) |
| **Power (active)** | ~80–240 mA | ~300–500 mA |
| **Power (sleep)** | ~10 µA (deep sleep) | ~40 mA (minimum, no deep sleep) |
| **Networking** | WiFi/BLE (raw sockets) | WiFi/BLE + full TCP/IP stack + SSH + HTTP |
| **Multitasking** | Cooperative/preemptive RTOS tasks | Full preemptive multitasking, processes, threads |
| **Filesystem** | SPIFFS/LittleFS (flat) | ext4, full POSIX, thousands of files |
| **Camera** | OV2640 (low-res JPEG) | CSI camera (12 MP, H.264 video) |
| **USB** | Device only (no host) | OTG (host and device) |
| **Cost** | ~$5–8 | ~$15 |

### When You Need Embedded Linux

Choose the Pi (or any embedded Linux board) when you need:

- **Complex processing** — computer vision, machine learning inference, audio/video processing, data analysis
- **Rich networking** — full TCP/IP, SSH, HTTP servers, MQTT clients, VPN, DNS
- **Filesystem** — logging gigabytes of data, databases, serving files
- **Multiple concurrent services** — a web dashboard AND a sensor logger AND an MQTT bridge
- **Rapid development** — write Python, install packages with apt, debug over SSH
- **USB host** — connect USB devices (webcams, storage, HID)
- **Camera** — anything beyond low-res snapshots

Choose the ESP32 when you need:

- **Battery life** — deep sleep at 10 µA for months on a coin cell
- **Real-time GPIO** — bit-banging protocols, precise timing
- **Instant-on** — boot in 200 ms
- **Cost at scale** — $5 per unit, not $15
- **Simplicity** — one program, no kernel, no filesystem corruption risk

### The Pi Zero 2 W Specifically

The Pi Zero 2 W occupies a sweet spot: **powerful enough for real work, small enough to embed.** It's the size of a stick of gum (65 × 30 mm), draws under 500 mA, costs $15, and runs the same Linux as the full-size Pi 4/5. It's the board you reach for when the ESP32 isn't enough but a Pi 4 is overkill.

Common deployments: wildlife camera traps, IoT gateways, home automation hubs, weather stations with dashboards, amateur radio nodes, kiosk displays, network monitoring probes, remote data loggers.

```quiz
Q: The Pi Zero 2 W and ESP32 are both "embedded," but at opposite ends. What's the defining difference?
- [ ] The Pi is just faster
- [x] The Pi runs a full Linux kernel and userspace (processes, threads, a filesystem, the full TCP/IP stack, SSH) — it's a small computer; the ESP32 runs one program on bare metal or FreeRTOS with no OS
- [ ] The ESP32 has more RAM
- [ ] They run the same software
> The mental model is microcontroller vs embedded Linux. The Pi gives you multitasking, an ext4 filesystem, apt, SSH, and any language — at the cost of a ~15–30s boot, no deep sleep (~40mA minimum), and microsecond-not-nanosecond GPIO. The ESP32 gives instant-on, 10µA deep sleep, and register-level GPIO timing, but no OS. Each strength is the other's weakness.

Q: For which task should you choose the ESP32 over the Pi Zero 2 W?
- [ ] Running a web dashboard plus a sensor logger plus an MQTT bridge
- [x] A battery device needing months of life via deep sleep and precise bit-banged GPIO timing — the Pi can't deep-sleep (~40mA floor) and has microsecond kernel GPIO latency
- [ ] Computer-vision inference on a camera feed
- [ ] Logging gigabytes to a database
> The ESP32 wins on battery life (10µA deep sleep vs the Pi's ~40mA minimum — months vs hours on a coin cell), real-time GPIO (~50ns register access vs the Pi's 1–10µs kernel overhead), instant boot, and per-unit cost. The Pi wins when you need complex processing, rich networking, a filesystem, multiple concurrent services, or USB host — anything that genuinely wants an operating system.

Q: Why does the Pi have ~1–10µs GPIO latency while the ESP32 has ~50ns?
- [ ] The Pi's pins are slower hardware
- [x] The Pi's GPIO access goes through the Linux kernel (scheduling, syscalls, no real-time guarantees), adding overhead; the ESP32 touches hardware registers directly with no OS in the way
- [ ] The ESP32 overclocks its pins
- [ ] The Pi uses a slower bus
> The same OS that gives the Pi multitasking and a filesystem also sits between your code and the pins: a GPIO toggle is a syscall subject to scheduling, so timing is non-deterministic at the microsecond scale. The ESP32's bare-metal model writes registers directly and deterministically. This is why precise bit-banged protocols and tight timing favor the microcontroller, even though the Pi is far more capable overall.
```

---

## 2. The Hardware

### Pi Zero 2 W Specifications

| Component | Specification |
|---|---|
| **SoC** | Broadcom BCM2710A1 |
| **CPU** | Quad-core ARM Cortex-A53 @ 1 GHz (64-bit ARMv8-A) |
| **RAM** | 512 MB LPDDR2 |
| **WiFi** | 802.11 b/g/n (2.4 GHz only) |
| **Bluetooth** | 4.2 + BLE |
| **Video out** | Mini HDMI |
| **USB** | 1× Micro USB (OTG — host and device) |
| **Power** | 1× Micro USB (5V, recommended 2.5A supply) |
| **Storage** | microSD slot |
| **GPIO** | 40-pin header (unpopulated — you solder the pins) |
| **Camera** | CSI-2 connector (22-pin, needs Pi Zero camera cable) |
| **Size** | 65 × 30 × 5 mm |
| **Weight** | 10 g |

### The 40-Pin GPIO Header

The GPIO header is your interface to the physical world. All 40 pins have a specific function:

```
                        Pi Zero 2 W — GPIO Header
                        (component side, USB ports at bottom)

    3V3  (1)  (2)  5V
  GPIO2  (3)  (4)  5V         ← I2C1 SDA
  GPIO3  (5)  (6)  GND        ← I2C1 SCL
  GPIO4  (7)  (8)  GPIO14     ← UART TX
    GND  (9)  (10) GPIO15     ← UART RX
 GPIO17 (11)  (12) GPIO18     ← PWM0 / PCM CLK / I2S
 GPIO27 (13)  (14) GND
 GPIO22 (15)  (16) GPIO23
    3V3 (17)  (18) GPIO24
 GPIO10 (19)  (20) GND        ← SPI0 MOSI
  GPIO9 (21)  (22) GPIO25     ← SPI0 MISO
 GPIO11 (23)  (24) GPIO8      ← SPI0 SCLK / SPI0 CE0
    GND (25)  (26) GPIO7      ← SPI0 CE1
  GPIO0 (27)  (28) GPIO1      ← I2C0 (EEPROM, reserved for HATs)
  GPIO5 (29)  (30) GND
  GPIO6 (31)  (32) GPIO12     ← PWM0
 GPIO13 (33)  (34) GND        ← PWM1
 GPIO19 (35)  (36) GPIO16     ← PWM1 / SPI1 CE2
 GPIO26 (37)  (38) GPIO20     ← SPI1 MOSI / PCM DIN
    GND (39)  (40) GPIO21     ← SPI1 SCLK / PCM DOUT
```

Key points:
- **3.3V logic levels only.** The GPIO pins are 3.3V and **not 5V tolerant.** Applying 5V to a GPIO pin will damage the SoC. Use a level shifter for 5V peripherals.
- Pins 3 & 5 have **built-in 1.8 kΩ pull-ups** (for I2C). All other GPIO pins have configurable internal pull-ups/pull-downs (~50 kΩ).
- PWM: hardware PWM on GPIO 12, 13, 18, 19 (two channels, two outputs each).
- There are only **two 5V pins and two 3.3V pins** for powering peripherals. Total 3.3V output current is ~50 mA (enough for a few sensors, not enough for an LED strip).

### What You Need on Your Desk

The minimum kit to get started:

1. **Pi Zero 2 W** — with GPIO header soldered (or solder it yourself)
2. **microSD card** — 16 GB minimum, Class 10 / A1
3. **USB power supply** — 5V, 2.5A minimum, micro USB
4. **USB OTG adapter** — micro USB male to USB-A female (for connecting keyboards, Ethernet adapters)
5. **microSD card reader** — to flash the OS image

For headless (no monitor) work — the recommended approach:
- A laptop with SSH (you already have this)
- A USB-to-serial adapter (3.3V TTL) for the serial console — **strongly recommended** for debugging boot issues

Optional but useful:
- Mini HDMI to HDMI adapter/cable (for initial debugging)
- Breadboard + jumper wires + a few LEDs and resistors (for GPIO)
- I2C sensor (BME280 or SHT31 — temperature/humidity/pressure)
- SPI display (SSD1306 OLED or ST7789 TFT)

---

## 3. The Boot Process

### Why the Boot Process Matters

On the ESP32, boot is invisible — power on, your code runs 200 ms later. On the Pi, the boot process is a multi-stage pipeline that takes 15–30 seconds and involves firmware, a bootloader, the Linux kernel, an init system, and your services. Understanding it is essential for debugging "my Pi won't boot" and for optimizing startup time.

### The Boot Pipeline

The Pi's boot is unusual — it starts on the **GPU**, not the CPU:

```
Power on
   ↓
┌───────────────────────────────────┐
│ Stage 1: On-chip ROM bootloader   │  Hardcoded in SoC silicon.
│ (VideoCore GPU)                   │  Reads bootcode.bin from SD card.
└─────────────┬─────────────────────┘
              ↓
┌───────────────────────────────────┐
│ Stage 2: bootcode.bin             │  GPU firmware from SD card.
│ (still on the GPU)               │  Initializes SDRAM.
│                                   │  Loads start.elf.
└─────────────┬─────────────────────┘
              ↓
┌───────────────────────────────────┐
│ Stage 3: start.elf               │  GPU firmware. Reads config.txt.
│ (GPU, reads config.txt)          │  Loads the Linux kernel + DTB.
│                                   │  Releases the ARM CPU from reset.
└─────────────┬─────────────────────┘
              ↓
┌───────────────────────────────────┐
│ Stage 4: Linux kernel             │  Runs on the ARM CPU.
│ (kernel8.img or kernel7l.img)    │  Mounts root filesystem.
│                                   │  Starts PID 1 (init/systemd).
└─────────────┬─────────────────────┘
              ↓
┌───────────────────────────────────┐
│ Stage 5: systemd                  │  Starts services in parallel.
│ (init system)                    │  Network, SSH, your application.
└───────────────────────────────────┘
```

On Pi 4/5 and Zero 2 W with updated firmware: `bootcode.bin` is replaced by an on-SoC bootloader in newer firmware, but the overall flow is the same.

### The Boot Partition (FAT32)

The microSD card has two partitions:

1. **Boot partition** (`/boot/firmware/` when mounted) — FAT32, ~512 MB. Contains:
   - `config.txt` — the Pi's BIOS equivalent (hardware configuration)
   - `cmdline.txt` — kernel command-line parameters
   - `kernel*.img` — the Linux kernel
   - `*.dtb` — device tree binaries
   - `overlays/` — device tree overlays
   - `start*.elf`, `fixup*.dat` — GPU firmware

2. **Root partition** — ext4. The Linux root filesystem (`/`).

The boot partition is FAT32 so it can be read on any OS (Windows, macOS, Linux) — this is how you configure WiFi and enable SSH before the first boot.

```quiz
Q: What's unusual about how the Raspberry Pi boots compared to a typical PC?
- [ ] It boots from the network first
- [x] It starts on the *GPU* (VideoCore), not the CPU — the on-chip ROM and GPU firmware (`bootcode.bin`/`start.elf`) initialize SDRAM, read config.txt, load the kernel and device tree, and only then release the ARM CPU from reset
- [ ] It has no bootloader
- [ ] The CPU runs first as usual
> The Pi's boot pipeline is GPU-led: the VideoCore GPU runs the first stages, sets up memory, parses config.txt, and loads the Linux kernel plus device tree blob before handing control to the ARM CPU, which then mounts the root filesystem and starts systemd. Knowing this multi-stage flow (firmware → kernel → init → services, ~15–30s) is what lets you debug "my Pi won't boot" rather than staring at a dead board.

Q: Why is the boot partition FAT32 while the root partition is ext4?
- [ ] FAT32 is faster
- [x] FAT32 is readable on any OS (Windows, macOS, Linux), so you can edit config.txt, enable SSH, and set Wi-Fi credentials on the card from your laptop *before* first boot; the root partition uses ext4 for the full POSIX Linux filesystem
- [ ] ext4 can't store a kernel
- [ ] The GPU only reads FAT32 by coincidence
> The two-partition layout serves two needs: the GPU firmware and config files live on a universally-readable FAT32 boot partition so you can configure a headless Pi by mounting the SD card on any computer, and the Linux system lives on ext4 for proper permissions, journaling, and thousands of files. This is exactly how headless setup works — drop config into the boot partition before the Pi ever powers on.

Q: What role does config.txt play in the Pi's boot?
- [ ] It's the systemd service list
- [x] It's the Pi's BIOS/UEFI equivalent — hardware configuration read by the GPU firmware before the kernel loads (CPU frequency, GPU memory split, enabling I2C/SPI/UART, device tree overlays)
- [ ] It stores the root password
- [ ] It's the kernel command line
> config.txt configures hardware *before* Linux starts, the job a PC's BIOS does: clock speeds, memory split, which buses are enabled (`dtparam=i2c_arm=on`), and which device tree overlays to apply. It's distinct from cmdline.txt (kernel parameters). Editing it on the FAT32 boot partition is how you turn on interfaces and tune the board, applied at the next boot.
```

### config.txt — The Hardware Configuration File

`config.txt` is where you configure hardware before the kernel loads. It replaces what a PC does in BIOS/UEFI. Key settings:

```ini
# --- CPU & Memory ---
arm_64bit=1                    # Boot in 64-bit mode (default on Zero 2 W)
arm_freq=1000                  # CPU frequency in MHz (default 1000)
over_voltage=0                 # Overvoltage for overclocking (0 = none)
gpu_mem=16                     # GPU memory split in MB (minimum for headless)

# --- Display ---
# For headless (no monitor), save power:
dtoverlay=vc4-kms-v3d          # Modern DRM/KMS video driver
#hdmi_blanking=1               # Blank HDMI when no display detected

# --- Enable interfaces ---
dtparam=i2c_arm=on             # Enable I2C1 on GPIO 2/3
dtparam=spi=on                 # Enable SPI0 on GPIO 7-11
enable_uart=1                  # Enable UART on GPIO 14/15

# --- Device tree overlays ---
dtoverlay=w1-gpio              # Enable 1-Wire on GPIO 4 (DS18B20 temp sensors)
dtoverlay=pwm-2chan             # Enable hardware PWM on GPIO 12/13
dtoverlay=i2c-rtc,ds3231       # Add DS3231 real-time clock on I2C

# --- Camera ---
#start_x=1                     # Enable camera (legacy stack)
# camera_auto_detect=1         # Auto-detect CSI camera (modern libcamera)

# --- Power saving ---
dtoverlay=disable-bt            # Disable Bluetooth (saves ~20 mA)
dtoverlay=disable-wifi          # Disable WiFi (saves ~40 mA, if using Ethernet)
```

Every hardware interface on the Pi is controlled here. If a peripheral doesn't work, `config.txt` is the first place to check.

### cmdline.txt — Kernel Command Line

A single line of kernel parameters. The default is fine for most cases:

```
console=serial0,115200 console=tty1 root=PARTUUID=xxxxx rootfstype=ext4 fsck.repair=yes rootwait
```

Key parameters:
- `console=serial0,115200` — enable kernel messages on the serial UART (essential for headless debugging)
- `root=PARTUUID=xxxxx` — which partition is the root filesystem
- `rootwait` — wait for the root device to appear (important for SD cards)
- `quiet` — suppress most boot messages (add for faster perceived boot)

---

## 4. OS Selection & Image Creation

### Raspberry Pi OS Lite (Recommended Starting Point)

**Raspberry Pi OS Lite** (formerly Raspbian Lite) is the official OS without a desktop environment. It's a Debian-based Linux with Pi-specific kernel patches and tools. This is the right choice for 90% of embedded projects.

```bash
# Download and flash with Raspberry Pi Imager (GUI)
# or use the CLI:
# On macOS:
brew install --cask raspberry-pi-imager

# Or manually with dd (find the SD card device first):
diskutil list                  # find the SD card (e.g., /dev/disk4)
diskutil unmountDisk /dev/disk4
sudo dd if=2024-raspios-bookworm-arm64-lite.img of=/dev/rdisk4 bs=4m status=progress
sync
```

The **Raspberry Pi Imager** is strongly recommended over `dd` because it:
- Downloads the latest image automatically
- Lets you pre-configure WiFi, SSH, hostname, and user credentials before first boot
- Writes the image and verifies it

### Alternative OS Choices

| OS | Use Case | Trade-off |
|---|---|---|
| **Raspberry Pi OS Lite** | General embedded projects | Easiest, best hardware support, largest community |
| **Raspberry Pi OS (64-bit)** | Need 64-bit userspace | Same as above but 64-bit. Default on Zero 2 W now |
| **DietPi** | Minimal footprint, optimized | Smaller base image, good for headless appliances |
| **Buildroot** | Custom minimal Linux | You choose exactly what's included. 8 MB root image possible. Steep learning curve |
| **Yocto / OpenEmbedded** | Production embedded products | Industry-standard build system. Very steep learning curve. Maximum control |
| **Ubuntu Server** | Familiar Ubuntu ecosystem | Heavier than RPi OS Lite, good Snap/Docker support |
| **Alpine Linux** | Security-focused, musl libc | Tiny footprint, but some packages unavailable |

### Buildroot — When You Need Minimal

Buildroot generates a complete, custom Linux image — kernel + root filesystem — with only what you specify. The result can be as small as 8 MB. It's the right tool when you're building an appliance (a device that runs one application, not a general-purpose computer).

```bash
git clone https://github.com/buildroot/buildroot.git
cd buildroot
make raspberrypi0_2w_defconfig    # Pi Zero 2 W default config
make menuconfig                    # customize packages, kernel, etc.
make -j$(nproc)                    # build (takes 15-60 minutes)
# Output: output/images/sdcard.img
```

Buildroot is conceptually simple: a Makefile that downloads, configures, cross-compiles, and packages everything. But it requires understanding Linux from the kernel up.

### Read-Only Root Filesystem

For deployed embedded devices, a **read-only root filesystem** prevents SD card corruption from power loss (the #1 reliability problem with Pi-based devices):

```bash
# Quick approach: add to cmdline.txt
rootfstype=ext4 ro              # mount root as read-only

# Create a tmpfs overlay for writable directories:
# /tmp, /var/log, /var/run need to be writable
# Use overlayfs or tmpfs mounts in /etc/fstab:
tmpfs /tmp     tmpfs defaults,noatime,nosuid,size=50m 0 0
tmpfs /var/log tmpfs defaults,noatime,nosuid,size=20m 0 0
tmpfs /var/tmp tmpfs defaults,noatime,nosuid,size=20m 0 0
```

The alternative: use `overlayroot` or `raspi-config` → Performance → Overlay FS, which makes the entire root filesystem an overlay — writes go to a tmpfs and are lost on reboot. The SD card is never written to.

---

## 5. Headless Setup & Serial Console

### Pre-Boot Configuration (Before First Boot)

After flashing the SD card, mount the boot partition on your laptop and create:

**1. Enable SSH:**
```bash
# Create an empty file named 'ssh' in the boot partition
touch /Volumes/bootfs/ssh
```

**2. Configure WiFi:**
```bash
# Using Raspberry Pi Imager: set WiFi during imaging (preferred)

# Or manually, create /boot/firmware/wpa_supplicant.conf:
# (Bookworm+ uses NetworkManager, but this still works for first boot)
cat > /Volumes/bootfs/wpa_supplicant.conf << 'EOF'
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="YourNetworkName"
    psk="YourPassword"
    key_mgmt=WPA-PSK
}
EOF
```

**3. Create a user** (required since Bookworm — no default `pi` user):
```bash
# Raspberry Pi Imager handles this. For manual setup:
# Create userconf.txt with username:encrypted-password
echo 'myuser:'$(echo 'mypassword' | openssl passwd -6 -stdin) > /Volumes/bootfs/userconf.txt
```

### First SSH Connection

```bash
# Boot the Pi, wait ~60 seconds, then:
ssh myuser@raspberrypi.local     # mDNS name (avahi)
# or find the IP with:
arp -a | grep -i "b8:27:eb\|dc:a6:32\|d8:3a:dd\|2c:cf:67"   # Pi MAC prefixes
nmap -sn 192.168.1.0/24          # scan your subnet
```

### The Serial Console — Your Lifeline

SSH requires a working network. When the network is misconfigured, the SD card won't boot, or the Pi kernel-panics, the **serial console** is your only window in. It works even when SSH doesn't.

**Hardware setup:**

```
USB-to-Serial Adapter         Pi Zero 2 W
(3.3V TTL, e.g. CP2102)      (GPIO header)

    GND  ──────────────────── Pin 6  (GND)
    TXD  ──────────────────── Pin 10 (GPIO15, RXD)
    RXD  ──────────────────── Pin 8  (GPIO14, TXD)
    
    Do NOT connect VCC/3.3V from the adapter to the Pi.
    Power the Pi from its own USB power port.
```

**Important: TX crosses to RX.** The adapter's TX goes to the Pi's RX, and vice versa.

**Software setup:**

```bash
# Ensure UART is enabled in config.txt:
enable_uart=1

# Connect from macOS/Linux:
ls /dev/tty.usbserial-*          # find the adapter device
screen /dev/tty.usbserial-0001 115200
# or:
minicom -D /dev/tty.usbserial-0001 -b 115200

# You'll see the full kernel boot log and a login prompt.
# To exit screen: Ctrl-A then K, then Y
```

The serial console shows every kernel message from power-on — including the boot errors that SSH can never show you. If you're doing embedded Pi work, **buy a USB-serial adapter.** The $3 CP2102 or CH340 adapters work fine.

### Bluetooth serial on the Zero 2 W

The Pi Zero 2 W's UART and Bluetooth share the same hardware UART. By default, Bluetooth gets the full UART (`ttyAMA0`) and the serial console gets the mini UART (`ttyS0`), which has limitations (baud rate tied to core clock). For a reliable serial console:

```ini
# In config.txt, disable Bluetooth to free the full UART:
dtoverlay=disable-bt

# Or swap the UARTs (Bluetooth gets mini UART, serial gets full UART):
dtoverlay=miniuart-bt
```

---

## 6. Device Trees & Overlays

### What the Device Tree Is

On a PC, the BIOS/UEFI probes the hardware and tells the OS what's present. ARM boards like the Pi have no such discovery mechanism — the hardware is soldered to the board and the kernel needs to be told exactly what's there. The **device tree** is that description: a data structure that says "there's an I2C controller at address 0x7E804000, an SPI controller at 0x7E204000, the WiFi chip is connected to SDIO," and so on.

The device tree is compiled from human-readable source (`.dts`) into a binary blob (`.dtb`) that the bootloader passes to the kernel at boot. You almost never write device tree source from scratch — you use **overlays** to modify the base tree.

### Device Tree Overlays

An **overlay** is a fragment that modifies the base device tree at boot time. This is how you enable, disable, or configure hardware without recompiling the kernel. Overlays are loaded via `config.txt`:

```ini
# Enable I2C
dtparam=i2c_arm=on

# Enable SPI
dtparam=spi=on

# Load a full overlay (from /boot/firmware/overlays/)
dtoverlay=w1-gpio,gpiopin=4        # 1-Wire on GPIO4
dtoverlay=i2c-rtc,ds3231           # DS3231 RTC on I2C
dtoverlay=spi0-1cs                 # SPI0 with one chip-select
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4   # Hardware PWM
dtoverlay=gpio-ir,gpio_pin=17      # Infrared receiver on GPIO17
```

**`dtparam`** modifies parameters in the base device tree (simple enable/disable).
**`dtoverlay`** loads an entire overlay file from `/boot/firmware/overlays/`.

### Listing Available Overlays

```bash
ls /boot/firmware/overlays/        # hundreds of .dtbo files
# Each has documentation:
cat /boot/firmware/overlays/README  # comprehensive docs for every overlay
# Or search for a specific one:
grep -A 20 "^Name:.*i2c-rtc" /boot/firmware/overlays/README
```

### Checking What's Active

```bash
# See the live device tree:
dtc -I fs /proc/device-tree/ 2>/dev/null | less

# Check specific nodes:
ls /proc/device-tree/              # top-level nodes
cat /proc/device-tree/model        # "Raspberry Pi Zero 2 W Rev 1.0"

# Verify an overlay loaded correctly:
vcdbg log msg 2>&1 | grep -i dtoverlay
dmesg | grep -i "i2c\|spi\|rtc"   # kernel messages about hardware init
```

```quiz
Q: Why does an ARM board like the Pi need a device tree when a PC doesn't?
- [ ] ARM kernels are smaller
- [x] A PC's BIOS/UEFI probes and enumerates hardware, but the Pi's peripherals are soldered with no discovery mechanism — the device tree is a data structure that tells the kernel exactly what hardware exists and at which addresses
- [ ] The device tree replaces the kernel
- [ ] ARM boards have no peripherals
> x86 has enumerable buses (PCI) and firmware that discovers devices; ARM SoCs generally don't, so the kernel can't find an I2C or SPI controller by probing. The device tree (compiled from `.dts` source to a `.dtb` blob the bootloader hands the kernel) is the static description of "this controller is at this address, this chip is wired here." Without it, the kernel wouldn't know the board's hardware exists.

Q: What's a device tree *overlay*, and why use one instead of editing the base tree?
- [ ] A theme for the desktop
- [x] A fragment that modifies the base device tree at boot (loaded via config.txt) to enable/disable/configure hardware *without recompiling the kernel* — e.g. `dtoverlay=i2c-rtc,ds3231` adds an RTC, `dtparam=spi=on` enables SPI
- [ ] A way to overclock the CPU
- [ ] A second kernel
> The base device tree describes the board; overlays patch it for the peripherals *you* attach. Because they're applied at boot from config.txt, you reconfigure hardware (turn on a bus, add a sensor, enable hardware PWM) by editing a text file and rebooting — no kernel rebuild. `dtparam` flips simple base-tree parameters; `dtoverlay` loads a whole `.dtbo` file from `/boot/firmware/overlays/`. It's the Pi's equivalent of plugging in a card and having the OS recognize it.
```

### Writing a Custom Overlay

For common peripherals, an overlay already exists. For custom hardware, you write one. The source is a `.dts` file:

```dts
// my-custom-overlay.dts — example: add a GPIO-connected LED
/dts-v1/;
/plugin/;

/ {
    compatible = "brcm,bcm2835";

    fragment@0 {
        target-path = "/";
        __overlay__ {
            my_led: my_led {
                compatible = "gpio-leds";
                status_led {
                    label = "status";
                    gpios = <&gpio 17 0>;    /* GPIO17, active high */
                    default-state = "off";
                };
            };
        };
    };
};
```

```bash
# Compile and install:
dtc -@ -I dts -O dtb -o my-custom-overlay.dtbo my-custom-overlay.dts
sudo cp my-custom-overlay.dtbo /boot/firmware/overlays/

# Enable in config.txt:
dtoverlay=my-custom-overlay

# Reboot and verify:
ls /sys/class/leds/status/         # the LED appears as a sysfs device
echo 1 | sudo tee /sys/class/leds/status/brightness   # turn on
```

---

## 7. GPIO — General-Purpose I/O

### The Modern Way: libgpiod

The Linux kernel's GPIO interface has evolved:

1. **sysfs** (`/sys/class/gpio/`) — deprecated since kernel 4.8. Still works but don't use it for new projects.
2. **chardev / libgpiod** — the modern interface. Faster, thread-safe, supports events (edge detection), and handles cleanup properly (pins are released when your process exits).

```bash
# Install libgpiod tools and Python bindings:
sudo apt install gpiod python3-libgpiod
```

### Command-Line GPIO with libgpiod

```bash
# List GPIO chips:
gpiodetect
# gpiochip0 [pinctrl-bcm2835] (54 lines)

# Show all GPIO lines and their current state:
gpioinfo gpiochip0
# line  17:     unnamed       unused  input  active-high
# line  18:     unnamed       unused  input  active-high
# ...

# Read a GPIO pin (input):
gpioget gpiochip0 17
# 0

# Set a GPIO pin (output):
gpioset gpiochip0 17=1          # set GPIO17 high
gpioset gpiochip0 17=0          # set GPIO17 low

# Blink an LED (set high, wait 1s, set low):
gpioset -m time -u 1000000 gpiochip0 17=1     # hold high for 1 second

# Monitor a pin for edges (button press):
gpiomon --falling-edge gpiochip0 17
# blocks until GPIO17 goes low, then prints a timestamp
```

### Python GPIO with libgpiod

```python
#!/usr/bin/env python3
"""Blink an LED on GPIO17 using the modern libgpiod interface."""

import gpiod
import time

CHIP = "/dev/gpiochip0"
LED_PIN = 17

# Request the line as output
request = gpiod.request_lines(
    CHIP,
    consumer="blink-example",
    config={LED_PIN: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)},
)

try:
    while True:
        request.set_value(LED_PIN, gpiod.line.Value.ACTIVE)
        time.sleep(0.5)
        request.set_value(LED_PIN, gpiod.line.Value.INACTIVE)
        time.sleep(0.5)
finally:
    request.release()
```

### Python GPIO with gpiozero (Higher-Level)

The `gpiozero` library wraps the low-level interface with hardware-aware classes:

```python
#!/usr/bin/env python3
"""gpiozero — the Pythonic way."""

from gpiozero import LED, Button
from signal import pause

led = LED(17)           # GPIO17 as output (LED)
button = Button(27)     # GPIO27 as input (button with internal pull-up)

# React to button presses:
button.when_pressed = led.on
button.when_released = led.off

# Or just blink:
# led.blink(on_time=0.5, off_time=0.5)

pause()    # keep the script running, waiting for events
```

`gpiozero` is the recommended Python library for beginners and for any project where you're not chasing microsecond performance. It handles pull-ups, debouncing, edge detection, PWM, and cleanup automatically.

### C GPIO with libgpiod

```c
/* blink.c — blink an LED using libgpiod v2 API */
#include <gpiod.h>
#include <stdio.h>
#include <unistd.h>

#define CHIP "/dev/gpiochip0"
#define LED_PIN 17

int main(void) {
    struct gpiod_chip *chip = gpiod_chip_open(CHIP);
    if (!chip) { perror("gpiod_chip_open"); return 1; }

    struct gpiod_line_settings *settings = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_OUTPUT);

    struct gpiod_line_config *config = gpiod_line_config_new();
    unsigned int offset = LED_PIN;
    gpiod_line_config_add_line_settings(config, &offset, 1, settings);

    struct gpiod_request_config *req_cfg = gpiod_request_config_new();
    gpiod_request_config_set_consumer(req_cfg, "blink");

    struct gpiod_line_request *request =
        gpiod_chip_request_lines(chip, req_cfg, config);

    for (int i = 0; i < 20; i++) {
        gpiod_line_request_set_value(request, LED_PIN,
            (i % 2) ? GPIOD_LINE_VALUE_ACTIVE : GPIOD_LINE_VALUE_INACTIVE);
        usleep(500000);
    }

    gpiod_line_request_release(request);
    gpiod_request_config_free(req_cfg);
    gpiod_line_config_free(config);
    gpiod_line_settings_free(settings);
    gpiod_chip_close(chip);
    return 0;
}
```

```bash
# Compile:
gcc -o blink blink.c $(pkg-config --cflags --libs libgpiod)
# Run:
sudo ./blink
```

### GPIO Performance: Pi vs. ESP32

| Method | Toggle Frequency | Notes |
|---|---|---|
| ESP32 register-level C | ~10–20 MHz | Direct hardware register, no OS overhead |
| Pi libgpiod C | ~1–5 MHz | Kernel chardev interface |
| Pi gpiozero Python | ~10–50 kHz | Python overhead |
| Pi sysfs (deprecated) | ~1–10 kHz | Filesystem overhead |

For most embedded applications (reading sensors, controlling relays, driving LEDs), even the slowest method is fast enough. If you need microsecond precision, use the ESP32 or a dedicated microcontroller connected to the Pi via UART/SPI/I2C.

---

## 8. I2C — Inter-Integrated Circuit

I2C is the protocol you reach for first when connecting sensors, and understanding how it works on the wire makes every command below — and every debugging session — make sense. The defining trait is in the name's pronunciation ("I-squared-C," inter-IC): I2C is a **two-wire, addressed, multi-drop bus**. Just *two* signal wires — `SDA` (data) and `SCL` (clock) — carry communication for *many* devices wired in parallel on the same pair, which is why you can hang a temperature sensor, a real-time clock, and a display off the same two GPIO pins. The trick that makes many devices share two wires is **addressing**: every I2C device has a 7-bit address (often configurable by a jumper), and a transaction begins with the Pi (the *controller*) broadcasting an address; only the device whose address matches responds, while the rest stay silent. This is exactly why `i2cdetect` works the way it does — it walks every possible address and notes which ones answer — and why two devices with the same fixed address can't share a bus without an address-translating workaround.

Two mechanical facts explain most I2C troubleshooting. First, because `SDA` is shared and any device might pull it low, the bus uses **open-drain signaling with pull-up resistors** — devices can only pull the line *down*, and resistors pull it back *up*, so no two devices fighting can damage each other; the Pi provides built-in pull-ups on the primary bus, which is why simple sensors often work with no extra components. Second, I2C is **clocked by the controller** (synchronous), so timing is forgiving — there's no agreed-upon speed both sides must match exactly, unlike UART below. The trade-offs to carry: I2C is wonderfully economical on pins and great for low-to-moderate-speed sensors, but it's slower than SPI (typically 100 kHz–400 kHz) and the shared bus means one misbehaving device can wedge the whole thing. Reach for it when you have several slow peripherals and few pins to spare; reach for SPI (next) when you need speed.

### Enabling I2C

```ini
# In config.txt:
dtparam=i2c_arm=on               # Enable I2C1 on GPIO 2 (SDA) / GPIO 3 (SCL)
```

```bash
# After reboot, verify:
ls /dev/i2c-*
# /dev/i2c-1

# Install tools:
sudo apt install i2c-tools python3-smbus2
```

### Scanning the Bus

```bash
# Detect all connected I2C devices:
i2cdetect -y 1
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:                         -- -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 70: -- -- -- -- -- -- -- 77                        
#                             ^^ BME280 at address 0x77
```

### Reading a Sensor (BME280 — Temperature/Humidity/Pressure)

```python
#!/usr/bin/env python3
"""Read BME280 sensor via I2C using the bme280 library."""

import smbus2
import bme280

# pip3 install RPi.bme280
port = 1          # I2C bus 1
address = 0x77    # BME280 default address (or 0x76)

bus = smbus2.SMBus(port)
calibration_params = bme280.load_calibration_params(bus, address)

data = bme280.sample(bus, address, calibration_params)

print(f"Temperature: {data.temperature:.1f} °C")
print(f"Humidity:    {data.humidity:.1f} %")
print(f"Pressure:    {data.pressure:.1f} hPa")
```

### Raw I2C with smbus2

```python
#!/usr/bin/env python3
"""Read a raw I2C register (example: WHO_AM_I from an accelerometer)."""

import smbus2

bus = smbus2.SMBus(1)
address = 0x68          # Example: MPU6050 accelerometer

# Read a single byte from register 0x75 (WHO_AM_I):
who_am_i = bus.read_byte_data(address, 0x75)
print(f"WHO_AM_I: 0x{who_am_i:02x}")  # Should print 0x68 for MPU6050

# Read a block of bytes (e.g., 6 bytes of accelerometer data):
data = bus.read_i2c_block_data(address, 0x3B, 6)
ax = (data[0] << 8 | data[1])  # raw X acceleration
ay = (data[2] << 8 | data[3])  # raw Y acceleration
az = (data[4] << 8 | data[5])  # raw Z acceleration

# Write a byte (e.g., configure the sensor):
bus.write_byte_data(address, 0x6B, 0x00)  # wake up MPU6050

bus.close()
```

### I2C Speed

The default I2C clock is 100 kHz (standard mode). For faster communication:

```ini
# In config.txt — set I2C to 400 kHz (fast mode):
dtparam=i2c_arm_baudrate=400000
```

Not all devices support fast mode. Check your sensor's datasheet.

### Multiple I2C Buses

The Pi Zero 2 W has one general-purpose I2C bus (I2C1). If you need more:

```ini
# Add a software-bitbanged I2C bus on any two GPIO pins:
dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=23,i2c_gpio_scl=24
# This creates /dev/i2c-3
```

---

## 9. SPI — Serial Peripheral Interface

SPI is the protocol for *speed* — displays, ADCs, fast sensors, SD cards — and it makes a different set of trade-offs than I2C, which is the whole reason both protocols exist. Where I2C economizes on wires, SPI economizes on nothing and gets performance in return: it uses **four wires** — `SCLK` (clock), `MOSI` (controller-out, peripheral-in), `MISO` (controller-in, peripheral-out), and a per-device `CS`/chip-select — and the two separate data lines (`MOSI` and `MISO`) are the key, because they make SPI **full-duplex**: data flows in both directions *simultaneously* on every clock tick, where I2C's single shared `SDA` can only go one way at a time. That, plus the absence of I2C's addressing overhead and open-drain pull-up timing, is why SPI runs at tens of megahertz versus I2C's hundreds of kilohertz.

The cost of that speed is wires and pins. SPI has no addressing scheme; instead, each peripheral gets its own dedicated **chip-select** line, and the controller talks to exactly one device at a time by pulling *that device's* `CS` low while the others stay high and ignore the bus. So three SPI devices need three CS pins (plus the three shared clock/data lines), whereas three I2C devices need only the same two wires — the pin budget grows with device count on SPI and stays flat on I2C, which is frequently the deciding factor on a pin-constrained board like the Pi Zero. The one configuration subtlety that bites everyone is **SPI mode** (`CPOL`/`CPHA`, modes 0–3): the controller and peripheral must agree on the clock's idle polarity and which clock edge samples the data, and a mismatch produces garbage rather than an error — so "I get nonsense from my SPI device" is almost always a mode mismatch, checked against the device datasheet. The rule of thumb: SPI for anything fast or one-to-one (a display, a high-rate ADC); I2C for several slow sensors sharing two pins.

### Enabling SPI

```ini
# In config.txt:
dtparam=spi=on
```

```bash
# After reboot:
ls /dev/spidev*
# /dev/spidev0.0   (SPI0, chip enable 0 — GPIO8)
# /dev/spidev0.1   (SPI0, chip enable 1 — GPIO7)
```

### SPI Pin Mapping (SPI0)

| Pin | GPIO | Function |
|---|---|---|
| 19 | GPIO10 | MOSI (Master Out, Slave In) |
| 21 | GPIO9 | MISO (Master In, Slave Out) |
| 23 | GPIO11 | SCLK (Clock) |
| 24 | GPIO8 | CE0 (Chip Enable 0) |
| 26 | GPIO7 | CE1 (Chip Enable 1) |

### SPI from Python

```python
#!/usr/bin/env python3
"""SPI example: read from an MCP3008 ADC (analog-to-digital converter)."""

import spidev

spi = spidev.SpiDev()
spi.open(0, 0)          # SPI bus 0, chip select 0
spi.max_speed_hz = 1350000
spi.mode = 0

def read_adc(channel):
    """Read a value from MCP3008 ADC channel (0-7)."""
    # MCP3008 SPI protocol: send [start, single-ended + channel, don't care]
    # Receive [don't care, 2 high bits, 8 low bits]
    cmd = [1, (8 + channel) << 4, 0]
    data = spi.xfer2(cmd)
    value = ((data[1] & 3) << 8) | data[2]
    return value    # 0-1023 (10-bit ADC)

# Read channel 0:
value = read_adc(0)
voltage = value * 3.3 / 1023
print(f"ADC Channel 0: {value} ({voltage:.2f}V)")

spi.close()
```

### SPI Displays

SPI is commonly used for small displays. The Linux framebuffer driver `fbtft` supports many SPI displays:

```ini
# In config.txt — example for SSD1306 128x64 OLED:
dtoverlay=ssd1306,width=128,height=64

# Or for an ST7789 TFT:
dtoverlay=spi0-1cs
# (then use a userspace driver like luma.oled or Pillow with fbdev)
```

```python
# Using luma.oled for SSD1306:
# pip3 install luma.oled
from luma.core.interface.serial import spi
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

serial = spi(device=0, port=0, gpio_DC=24, gpio_RST=25)
device = ssd1306(serial, width=128, height=64)

with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((10, 25), "Hello, Pi!", fill="white")
```

### SPI Speed

SPI can run much faster than I2C:

```python
spi.max_speed_hz = 1000000    # 1 MHz (safe default)
spi.max_speed_hz = 10000000   # 10 MHz (most peripherals handle this)
spi.max_speed_hz = 50000000   # 50 MHz (fast displays, check datasheet)
```

---

## 10. UART & Serial Communication

UART is the oldest and conceptually simplest of the three protocols, and it differs from both I2C and SPI in one fundamental way that drives everything about using it: **it has no clock wire.** Where I2C and SPI are *synchronous* — a clock line tells the receiver exactly when to sample each bit — UART is **asynchronous**, using just two wires (`TX` to transmit, `RX` to receive, cross-connected between the two devices) and *no* shared clock. This raises an obvious question: without a clock, how does the receiver know when each bit starts and ends? The answer is that **both sides agree on the speed in advance** — the *baud rate* (9600, 115200, …) — and the data is wrapped in a framing protocol: each byte is preceded by a *start bit* that signals "a byte is coming, sample now," followed by the 8 data bits at the agreed baud rate, an optional parity bit, and a *stop bit*. The receiver sees the start bit, then samples at the pre-agreed interval. This is why a **baud-rate mismatch produces garbage** (the classic UART bug): if the two sides disagree on speed, the receiver samples at the wrong moments and reads nonsense, with no clock to catch the error — the single most common UART problem, and always the first thing to check.

The consequences of being clock-free and point-to-point shape when UART fits. It is strictly **one-to-one** — two devices, `TX`-to-`RX` and `RX`-to-`TX` — with no addressing and no bus, so it can't multi-drop like I2C. Its asynchronous nature makes it slower and slightly less reliable at high speeds than the synchronous protocols, but its simplicity and ubiquity make it the universal choice for two specific jobs: a **serial console** for logging into the Pi over a wire when the network is down (the headless-debugging lifeline from section 5), and talking to modules that speak serial natively (GPS receivers, some cellular and LoRa modems, microcontrollers). The mental sorting across all three protocols: UART for a point-to-point console or a serial-native module, I2C for several slow sensors on two pins, SPI for one fast device.

### The Pi Zero 2 W's UART Situation

The BCM2710A1 has two UARTs:

| UART | Name | Type | Default Use |
|---|---|---|---|
| PL011 | `/dev/ttyAMA0` | Full UART (16550-compatible) | Bluetooth |
| Mini UART | `/dev/ttyS0` | Reduced-feature UART | Serial console (GPIO14/15) |

The mini UART's baud rate is linked to the core clock frequency, making it unreliable if the CPU frequency changes. For serious serial work:

```ini
# config.txt — disable Bluetooth, give the full UART to GPIO14/15:
dtoverlay=disable-bt

# Now /dev/ttyAMA0 is the serial console on GPIO14/15
# (and /dev/serial0 symlinks to it)
```

### Serial Communication from Python

```python
#!/usr/bin/env python3
"""Talk to a GPS module (or any serial device) on the UART."""

import serial

# Open the serial port:
ser = serial.Serial(
    port='/dev/serial0',    # symlink to the active UART
    baudrate=9600,
    timeout=1,
)

# Read lines (e.g., NMEA sentences from a GPS):
while True:
    line = ser.readline().decode('ascii', errors='replace').strip()
    if line:
        print(line)
        # $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,...

# Write to the serial device:
# ser.write(b'AT\r\n')          # send an AT command (e.g., to a modem)
```

### Connecting to an Arduino/ESP32

A common pattern: use the Pi for heavy processing (computer vision, web server, database) and an Arduino/ESP32 for real-time sensor/actuator work, connected via UART:

```
Pi Zero 2 W                    Arduino/ESP32
GPIO14 (TX) ──────────────── RX
GPIO15 (RX) ──────────────── TX
GND         ──────────────── GND

⚠️  If the Arduino is 5V, use a level shifter or voltage divider
    on the Arduino TX → Pi RX line. The Pi is 3.3V only.
```

---

## 11. Camera (CSI)

### Camera Support

The Pi Zero 2 W has a CSI-2 camera connector (smaller 22-pin, not the standard 15-pin — use the Pi Zero camera cable or adapter). Supported cameras:

- **Camera Module v2** (IMX219, 8 MP) — $25, the standard choice
- **Camera Module v3** (IMX708, 12 MP, autofocus) — $35
- **HQ Camera** (IMX477, 12.3 MP, C/CS-mount lens) — $50
- Third-party cameras (IR, wide-angle, autofocus variants)

### libcamera — The Modern Camera Stack

The legacy `raspistill`/`raspivid` commands are replaced by **libcamera**:

```bash
# Take a photo:
libcamera-still -o photo.jpg

# Take a photo with specific resolution and delay:
libcamera-still -o photo.jpg --width 2592 --height 1944 -t 2000

# Record video (H.264, 1080p, 10 seconds):
libcamera-vid -o video.h264 -t 10000 --width 1920 --height 1080

# Stream video over the network (RTSP-like, using TCP):
libcamera-vid -t 0 --inline -o - | nc -l -p 5000
# On the receiving end:  nc <pi-ip> 5000 | ffplay -

# Timelapse (one photo every 5 seconds for 1 hour):
libcamera-still -t 3600000 --timelapse 5000 -o 'timelapse_%04d.jpg'
```

### Python Camera Access

```python
#!/usr/bin/env python3
"""Capture an image using picamera2 (the Python libcamera interface)."""

from picamera2 import Picamera2
import time

picam2 = Picamera2()
config = picam2.create_still_configuration(
    main={"size": (2592, 1944)},     # full resolution
)
picam2.configure(config)
picam2.start()
time.sleep(2)    # let auto-exposure settle

picam2.capture_file("photo.jpg")
print("Captured photo.jpg")
picam2.stop()
```

For computer vision, `picamera2` integrates with OpenCV:

```python
from picamera2 import Picamera2
import cv2

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()

while True:
    frame = picam2.capture_array()
    # frame is a numpy array — use OpenCV as normal:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    # ... process edges, detect objects, etc.
```

---

## 12. Power Management & Low-Power Operation

### Power Consumption Baseline

The Pi Zero 2 W has no deep sleep mode — the SoC is always on. But you can significantly reduce draw:

| Configuration | Current Draw (~) |
|---|---|
| Idle, WiFi + HDMI + LED | ~300 mA |
| Idle, WiFi on, HDMI off, LED off | ~200 mA |
| Idle, WiFi off, HDMI off, LED off, BT off | ~100 mA |
| Under CPU load (all 4 cores) | ~400–500 mA |

Compare with the ESP32's deep sleep at ~10 µA. The Pi is not a battery device — it's a mains-powered (or large-battery/solar-powered) device.

```quiz
Q: Why is the Pi Zero 2 W "not a battery device" the way an ESP32 is?
- [ ] Its battery connector is too small
- [x] The SoC has no deep-sleep mode — it's always on, so even a stripped-down idle Pi draws ~100mA (vs the ESP32's ~10µA deep sleep); there's no microamp idle state to coast through, only "fully on"
- [ ] It can't run on DC power
- [ ] Linux forbids low-power modes
> The ESP32's battery strategy is "sleep 99% of the time at 10µA"; the Pi has no equivalent — its lowest idle (Wi-Fi/HDMI/BT/LED all off) is ~100mA, roughly 10,000× more. You can trim draw by disabling unused hardware, but you can't make it disappear. So the Pi is a mains, large-battery, or solar device, not a coin-cell one.

Q: For a battery Pi project that must last, what's the standard power strategy given the Pi can't deep-sleep?
- [ ] Lower the CPU frequency and hope
- [x] Duty-cycle the *whole Pi* with an external timer circuit (Witty Pi, TPL5110) or an ESP32 wake-controller that cuts the Pi's power between bursts — boot, do the job in seconds-to-minutes, then power off entirely to reach ~µA average
- [ ] Run the app as a systemd timer
- [ ] Disable two CPU cores permanently
> Since the Pi has no internal low-power state, you achieve low *average* draw by removing its power externally. A timer circuit (or a 10µA-sleeping ESP32 acting as a wake controller via a MOSFET) powers the Pi up, lets it boot and do its work, then cuts power — turning a ~200mA always-on device into mA-bursts at µA average. A systemd timer keeps the Pi on; it doesn't save power. This whole-device duty-cycling is the embedded-Linux answer to the ESP32's deep sleep.
```

### Reducing Power Draw

```ini
# config.txt — disable unused hardware:
dtoverlay=disable-bt              # Bluetooth off (~20 mA saved)
dtoverlay=disable-wifi            # WiFi off (~40 mA saved, only if using USB Ethernet)
gpu_mem=16                        # Minimum GPU memory for headless

# Disable HDMI (runtime):
# In a startup script or service:
/usr/bin/tvservice -o             # turn HDMI off (~25 mA saved)
# Or in config.txt for Pi 4/Zero 2 W with KMS driver:
# (no config.txt option — use tvservice or xrandr)
```

```bash
# Disable the activity LED:
echo none | sudo tee /sys/class/leds/ACT/trigger
echo 0 | sudo tee /sys/class/leds/ACT/brightness

# Disable USB hub (if no USB devices needed — Pi Zero 2 W only):
# The Zero 2 W's USB is OTG, so there's no separate hub to disable.

# Reduce CPU frequency:
echo 600000 | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Disable unused CPU cores:
echo 0 | sudo tee /sys/devices/system/cpu/cpu1/online
echo 0 | sudo tee /sys/devices/system/cpu/cpu2/online
echo 0 | sudo tee /sys/devices/system/cpu/cpu3/online
```

### Solar / Battery Power

For battery-powered Pi projects, the strategy is fundamentally different from the ESP32's "sleep 99% of the time" approach:

1. **Duty-cycle the whole Pi** — use an external timer circuit (e.g., Witty Pi, TPL5110, or a 555 timer) to power-cycle the Pi. The Pi boots, does its work (30–120 seconds), then the external circuit cuts power. This achieves ~µA average draw with mA-level active bursts.

2. **Large battery + solar panel** — a 10,000 mAh battery runs the Pi for ~15–20 hours at 200 mA. A 6W solar panel can maintain this indefinitely in good sun.

3. **Use the ESP32 as a wake controller** — the ESP32 sleeps at 10 µA, wakes on a sensor event or timer, boots the Pi via a MOSFET switch, communicates over UART/I2C, then cuts Pi power again.

### USB Gadget Mode

The Pi Zero 2 W's USB port supports **OTG (On-The-Go)** — it can act as either a USB host (connect devices to the Pi) or a USB device (the Pi appears as a device to a computer). Gadget mode makes the Pi appear as:

```ini
# config.txt — enable USB gadget:
dtoverlay=dwc2

# cmdline.txt — load the gadget module after rootwait:
# Add "modules-load=dwc2,g_ether" after "rootwait":
rootwait modules-load=dwc2,g_ether
```

Available gadget modes:

| Module | Pi Appears As |
|---|---|
| `g_ether` | USB Ethernet adapter — SSH over USB cable |
| `g_serial` | USB serial port |
| `g_mass_storage` | USB flash drive (serve a file/partition) |
| `g_hid` | USB keyboard/mouse |
| `g_multi` | Combination (Ethernet + serial + storage) |

**Ethernet gadget** is particularly useful: plug the Pi into your laptop with a single USB cable, and it gets power AND a network connection. SSH in via `ssh user@raspberrypi.local` or `ssh user@10.0.0.2` (the default gadget IP).

---

## 13. Systemd — Running Your Application

### The Service File

On an embedded device, your application needs to start at boot and restart if it crashes. Systemd handles this:

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Sensor Logger Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=myuser
WorkingDirectory=/home/myuser/myapp
ExecStart=/usr/bin/python3 /home/myuser/myapp/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits (good practice for embedded):
MemoryMax=100M
CPUQuota=50%

# Security hardening:
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start:
sudo systemctl daemon-reload
sudo systemctl enable myapp.service     # start at boot
sudo systemctl start myapp.service      # start now

# Check status and logs:
sudo systemctl status myapp.service
journalctl -u myapp.service -f          # follow logs in real time
journalctl -u myapp.service --since "1 hour ago"
```

### Watchdog Timer

The Pi has a hardware watchdog. If your application hangs and stops petting the watchdog, the Pi reboots:

```ini
# /etc/systemd/system.conf — enable hardware watchdog:
RuntimeWatchdogSec=15           # reboot if systemd doesn't pet within 15s
RebootWatchdogSec=10min         # reboot timeout during shutdown

# Or per-service in [Service]:
WatchdogSec=30                  # systemd expects sd_notify("WATCHDOG=1") every 30s
```

```python
# In your Python application — pet the watchdog:
import systemd.daemon
import time

while True:
    # ... do your work ...
    systemd.daemon.notify("WATCHDOG=1")   # I'm alive
    time.sleep(10)
```

### Timer Units (cron Replacement)

For periodic tasks, use systemd timers instead of cron:

```ini
# /etc/systemd/system/sensor-reading.timer
[Unit]
Description=Take sensor reading every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
AccuracySec=10s

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/sensor-reading.service
[Unit]
Description=Take one sensor reading

[Service]
Type=oneshot
ExecStart=/home/myuser/read_sensor.py
User=myuser
```

```bash
sudo systemctl enable --now sensor-reading.timer
systemctl list-timers          # verify it's scheduled
```

```quiz
Q: Why run an embedded Pi application as a systemd service rather than launching it from a login script or `rc.local`?
- [ ] Systemd makes the code run faster
- [x] Systemd starts it at boot, restarts it on crash (`Restart=always`), captures its output to the journal, can order it after the network is up, and can sandbox it with resource limits and hardening — the supervision an unattended device needs
- [ ] Login scripts can't run Python
- [ ] rc.local is encrypted
> An unattended device must survive crashes and reboots without a human, which is exactly what a service unit provides: automatic start, automatic restart with a delay, dependency ordering (`After=network-online.target`), journal logging for `journalctl`, and process sandboxing (`MemoryMax`, `ProtectSystem`, `NoNewPrivileges`). A login script or rc.local does none of that — your app would die silently on the first exception with nowhere to log it.

Q: For a task that should run every 5 minutes, why use a systemd timer + oneshot service instead of cron?
- [ ] cron is deprecated
- [x] A timer unit integrates with systemd's logging, dependency ordering, and resource controls, and pairs with a `Type=oneshot` service so each run is supervised and logged to the journal like any other unit — with options like `OnBootSec` and `AccuracySec` cron lacks
- [ ] Timers run with no overhead
- [ ] cron can't run every 5 minutes
> A systemd timer triggers an associated oneshot service, so the periodic job inherits everything services get: journal output (debuggable with `journalctl -u`), dependency ordering, resource limits, and consistent management via `systemctl`. It also expresses schedules cron can't — relative to boot (`OnBootSec`) or to the last activation (`OnUnitActiveSec`), with a tolerance window (`AccuracySec`) for power efficiency. On an embedded device where you already use systemd, keeping periodic work in the same system is cleaner than a separate cron daemon.
```

---

## 14. Networking — WiFi, Bluetooth & USB Gadget

### WiFi Configuration with NetworkManager

Raspberry Pi OS Bookworm and later use NetworkManager:

```bash
# Scan for networks:
nmcli device wifi list

# Connect to a network:
nmcli device wifi connect "MyNetwork" password "MyPassword"

# Show current connection:
nmcli connection show

# Set a static IP:
nmcli connection modify "MyNetwork" \
    ipv4.method manual \
    ipv4.addresses "192.168.1.100/24" \
    ipv4.gateway "192.168.1.1" \
    ipv4.dns "8.8.8.8"
nmcli connection up "MyNetwork"

# Create a WiFi access point (AP mode):
nmcli device wifi hotspot ssid "PiHotspot" password "secretpassword"
```

### Bluetooth

```bash
# Install BlueZ tools:
sudo apt install bluetooth bluez python3-bluez

# Scan for devices:
bluetoothctl
[bluetooth]# power on
[bluetooth]# scan on
# ... wait for devices to appear ...
[bluetooth]# pair XX:XX:XX:XX:XX:XX
[bluetooth]# connect XX:XX:XX:XX:XX:XX
[bluetooth]# quit
```

For BLE (Bluetooth Low Energy) — e.g., reading a BLE sensor:

```python
#!/usr/bin/env python3
"""Read a BLE thermometer using bleak (cross-platform BLE library)."""

import asyncio
from bleak import BleakScanner, BleakClient

SENSOR_NAME = "ThermoBeacon"

async def main():
    # Scan for the device:
    device = await BleakScanner.find_device_by_name(SENSOR_NAME, timeout=10)
    if not device:
        print("Device not found")
        return

    async with BleakClient(device) as client:
        # Read a characteristic (example UUID):
        data = await client.read_gatt_char("00002a6e-0000-1000-8000-00805f9b34fb")
        temp = int.from_bytes(data, 'little') / 100
        print(f"Temperature: {temp:.1f} °C")

asyncio.run(main())
```

### Setting Up a Captive Portal / AP+Station

A common embedded pattern: the Pi creates a WiFi access point for initial configuration, while also connecting to an existing network:

```bash
# This requires two WiFi interfaces or concurrent AP+STA mode.
# The Pi Zero 2 W's onboard WiFi supports concurrent AP+STA in some
# configurations, but a USB WiFi dongle is more reliable.

# Simpler approach: AP mode for config, then switch to station mode:
# 1. Boot into AP mode if no known network is available
# 2. User connects to AP, opens captive portal, enters WiFi credentials
# 3. Pi saves credentials and reboots into station mode
```

---

## 15. Cross-Compilation & Remote Development

### Why Cross-Compile

The Pi Zero 2 W's quad-core Cortex-A53 at 1 GHz is capable, but compiling large C/C++ projects (or the Linux kernel) on it takes hours. Cross-compilation runs the compiler on your fast laptop and produces ARM binaries.

### Cross-Compilation Toolchain

```bash
# On your host machine (x86_64 Linux or macOS):

# Install the cross-compiler:
# Ubuntu/Debian:
sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# macOS (via Homebrew):
brew install aarch64-elf-gcc
# or use a Docker container with the toolchain

# Cross-compile a C program:
aarch64-linux-gnu-gcc -o hello hello.c

# Copy to Pi and run:
scp hello myuser@raspberrypi.local:~/
ssh myuser@raspberrypi.local ./hello
```

### Remote Development with VS Code

The most productive workflow for Pi development:

1. Install the **Remote - SSH** extension in VS Code
2. Connect: `Ctrl+Shift+P` → "Remote-SSH: Connect to Host" → `myuser@raspberrypi.local`
3. VS Code runs on the Pi (server-side), your UI runs on your laptop
4. Edit files, run terminals, debug — all over SSH, with full IDE features

This gives you the development experience of a fast local machine with the execution environment of the Pi. For Python projects on the Pi Zero 2 W, this is the recommended workflow — no cross-compilation needed.

### Deploying with rsync

```bash
# Sync your project directory to the Pi:
rsync -avz --exclude='.git' --exclude='__pycache__' \
    ./myproject/ myuser@raspberrypi.local:~/myproject/

# One-liner: sync and restart the service:
rsync -avz ./myproject/ pi:~/myproject/ && ssh pi 'sudo systemctl restart myapp'
```

---

## 16. Real-Time & Performance Tuning

### The Real-Time Problem

Linux is not a real-time OS. The kernel preempts tasks, handles interrupts, runs garbage collection, and performs background I/O — all of which add unpredictable latency to your application. For most embedded tasks (reading a sensor every second, serving a web page), this doesn't matter. For time-critical tasks (motor control, audio processing, high-speed data acquisition), it does.

### Kernel Preemption Models

The standard Raspberry Pi OS kernel uses `PREEMPT_VOLUNTARY` — the kernel can preempt user tasks but not itself. The real-time kernel patch (`PREEMPT_RT`) makes the kernel fully preemptible:

```bash
# Check current preemption model:
uname -a
# ... PREEMPT ... (standard) or ... PREEMPT_RT ... (real-time)

# Install the RT kernel (if available for your Pi OS version):
sudo apt install linux-image-rt-arm64
# Reboot and select the RT kernel
```

With `PREEMPT_RT`:
- Worst-case GPIO latency drops from ~1 ms to ~50–100 µs
- Interrupt handlers run as preemptible threads
- Suitable for soft real-time applications (audio, motor control with encoders)

For hard real-time (sub-10 µs guarantees), use a dedicated microcontroller.

### CPU Isolation

Pin your real-time application to a dedicated CPU core that the kernel doesn't use for anything else:

```bash
# cmdline.txt — isolate CPU 3 from the scheduler:
isolcpus=3 nohz_full=3 rcu_nocbs=3

# In your application, set CPU affinity:
taskset -c 3 ./my_realtime_app

# Or in the systemd service:
# [Service]
# CPUAffinity=3
```

### Memory Tuning

```bash
# Disable swap (swap on SD card is slow and kills the card):
sudo dphys-swapfile swapoff
sudo systemctl disable dphys-swapfile

# Lock your application's memory (prevent page faults):
# In C:
# mlockall(MCL_CURRENT | MCL_FUTURE);
# In Python: not easily possible, but less critical
```

---

## 17. Security for Deployed Devices

### The Threat Model

A Pi deployed in the field (weather station, kiosk, remote logger) faces different threats than a server:

- **Physical access** — someone can steal the SD card and read your credentials
- **Network exposure** — if it has WiFi, it's on a network
- **Unattended operation** — you're not watching the logs

### Essential Hardening

```bash
# 1. Change the default password (done during setup, but verify):
passwd

# 2. Disable password authentication for SSH (use keys only):
ssh-keygen -t ed25519 -C "pi-zero"      # on your laptop
ssh-copy-id myuser@raspberrypi.local     # copy public key to Pi
# Then on the Pi, edit /etc/ssh/sshd_config:
# PasswordAuthentication no
# PermitRootLogin no
sudo systemctl restart ssh

# 3. Enable the firewall:
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable

# 4. Keep the system updated:
sudo apt update && sudo apt upgrade -y
# Or set up unattended upgrades:
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# 5. Remove unnecessary services:
sudo systemctl disable avahi-daemon    # if you don't need mDNS
sudo systemctl disable triggerhappy    # keyboard shortcut daemon
```

### Encrypted Storage

The SD card is trivially readable if physically removed. For sensitive data:

```bash
# Encrypt a data partition with LUKS:
sudo apt install cryptsetup
sudo cryptsetup luksFormat /dev/mmcblk0p3
sudo cryptsetup luksOpen /dev/mmcblk0p3 data
sudo mkfs.ext4 /dev/mapper/data
sudo mount /dev/mapper/data /mnt/data

# Store secrets (API keys, certificates) on the encrypted partition.
# The encryption key must be entered at boot (or stored in a TPM/HSM,
# which the Pi Zero 2 W doesn't have — a limitation of this platform).
```

### Watchdog + Health Monitoring

```bash
# The hardware watchdog reboots a hung Pi:
sudo apt install watchdog
# Configure /etc/watchdog.conf:
# watchdog-device = /dev/watchdog
# watchdog-timeout = 15
# max-load-1 = 24
# min-memory = 1
sudo systemctl enable watchdog
```

---

## 18. Practical Projects

### Project 1: Environmental Data Logger

A sensor station that reads temperature, humidity, and pressure every 5 minutes and serves a web dashboard.

**Hardware:** Pi Zero 2 W + BME280 (I2C) + microSD card
**Software:** Python + Flask + SQLite + systemd timer

```python
#!/usr/bin/env python3
"""sensor_logger.py — read BME280 and log to SQLite."""

import sqlite3
import time
import smbus2
import bme280

DB_PATH = "/home/myuser/sensors.db"
I2C_PORT = 1
BME280_ADDR = 0x77

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            timestamp TEXT DEFAULT (datetime('now')),
            temperature REAL,
            humidity REAL,
            pressure REAL
        )
    """)
    conn.commit()
    return conn

def read_sensor():
    bus = smbus2.SMBus(I2C_PORT)
    cal = bme280.load_calibration_params(bus, BME280_ADDR)
    data = bme280.sample(bus, BME280_ADDR, cal)
    bus.close()
    return data.temperature, data.humidity, data.pressure

def main():
    conn = init_db()
    temp, hum, pres = read_sensor()
    conn.execute(
        "INSERT INTO readings (temperature, humidity, pressure) VALUES (?, ?, ?)",
        (round(temp, 2), round(hum, 2), round(pres, 2)),
    )
    conn.commit()
    conn.close()
    print(f"Logged: {temp:.1f}°C, {hum:.1f}%, {pres:.1f} hPa")

if __name__ == "__main__":
    main()
```

```python
#!/usr/bin/env python3
"""dashboard.py — serve sensor data as a simple web dashboard."""

from flask import Flask, jsonify, render_template_string
import sqlite3

app = Flask(__name__)
DB_PATH = "/home/myuser/sensors.db"

TEMPLATE = """
<!DOCTYPE html>
<html><head><title>Sensor Dashboard</title>
<meta http-equiv="refresh" content="60">
<style>
  body { font-family: system-ui; background: #1a1a2e; color: #e0e0e0;
         display: flex; flex-direction: column; align-items: center; padding: 2em; }
  .card { background: #16213e; border-radius: 12px; padding: 1.5em 2em;
          margin: 0.5em; min-width: 200px; text-align: center; }
  .value { font-size: 2.5em; font-weight: bold; color: #4ade80; }
  .label { color: #9aa0ad; font-size: 0.9em; margin-top: 0.3em; }
  .grid { display: flex; gap: 1em; flex-wrap: wrap; justify-content: center; }
</style></head>
<body>
<h1>🌡️ Sensor Dashboard</h1>
<div class="grid">
  <div class="card"><div class="value">{{ t }}°C</div><div class="label">Temperature</div></div>
  <div class="card"><div class="value">{{ h }}%</div><div class="label">Humidity</div></div>
  <div class="card"><div class="value">{{ p }} hPa</div><div class="label">Pressure</div></div>
</div>
<p style="color:#6b7180; margin-top:2em;">Last reading: {{ ts }}</p>
</body></html>
"""

@app.route("/")
def index():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT timestamp, temperature, humidity, pressure "
        "FROM readings ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return render_template_string(TEMPLATE,
            ts=row[0], t=f"{row[1]:.1f}", h=f"{row[2]:.1f}", p=f"{row[3]:.0f}")
    return "No data yet"

@app.route("/api/readings")
def api_readings():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT timestamp, temperature, humidity, pressure "
        "FROM readings ORDER BY rowid DESC LIMIT 288"     # last 24h at 5min intervals
    ).fetchall()
    conn.close()
    return jsonify([
        {"ts": r[0], "temp": r[1], "hum": r[2], "pres": r[3]} for r in rows
    ])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

### Project 2: Wildlife Camera Trap

**Hardware:** Pi Zero 2 W + Camera Module v3 + PIR motion sensor (GPIO) + battery pack
**Concept:** PIR sensor wakes the Pi (via external power controller), Pi boots, takes a burst of photos, saves to SD, powers off.

```python
#!/usr/bin/env python3
"""camera_trap.py — capture images on motion detection."""

from gpiozero import MotionSensor
from picamera2 import Picamera2
from datetime import datetime
import os
import subprocess

PIR_PIN = 4
OUTPUT_DIR = "/home/myuser/captures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

pir = MotionSensor(PIR_PIN)
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (4056, 3040)})
picam2.configure(config)
picam2.start()

print("Camera trap active. Waiting for motion...")
while True:
    pir.wait_for_motion()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Burst: 3 photos in rapid succession
    for i in range(3):
        filename = f"{OUTPUT_DIR}/capture_{timestamp}_{i}.jpg"
        picam2.capture_file(filename)
        print(f"Captured: {filename}")
    
    pir.wait_for_no_motion()
```

### Project 3: IoT Gateway

**Concept:** Pi collects data from BLE sensors and ESP32 nodes, aggregates it, and publishes to an MQTT broker or cloud service.

```python
#!/usr/bin/env python3
"""iot_gateway.py — collect sensor data via MQTT and forward to cloud."""

import paho.mqtt.client as mqtt
import json
import sqlite3
import requests

LOCAL_BROKER = "localhost"       # Mosquitto running on the Pi
CLOUD_ENDPOINT = "https://api.example.com/data"

db = sqlite3.connect("/home/myuser/gateway.db")
db.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        timestamp TEXT DEFAULT (datetime('now')),
        device_id TEXT,
        payload TEXT
    )
""")
db.commit()

def on_message(client, userdata, msg):
    """Handle incoming sensor data from local MQTT topics."""
    try:
        data = json.loads(msg.payload)
        device_id = msg.topic.split("/")[-1]
        
        # Store locally:
        db.execute(
            "INSERT INTO sensor_data (device_id, payload) VALUES (?, ?)",
            (device_id, msg.payload.decode())
        )
        db.commit()
        
        # Forward to cloud (with retry):
        try:
            requests.post(CLOUD_ENDPOINT, json={
                "device": device_id, "data": data
            }, timeout=5)
        except requests.RequestException:
            pass    # local data is preserved; cloud sync will catch up
        
        print(f"[{device_id}] {data}")
    except Exception as e:
        print(f"Error: {e}")

client = mqtt.Client()
client.on_message = on_message
client.connect(LOCAL_BROKER, 1883)
client.subscribe("sensors/#")      # all sensor topics
client.loop_forever()
```

---

## 19. Pi Zero 2 W vs ESP32 — When to Use Which

### Decision Matrix

| Requirement | Choose |
|---|---|
| Battery-powered, needs to last months | **ESP32** — deep sleep at 10 µA |
| Camera with video / computer vision | **Pi** — CSI camera, OpenCV, ML inference |
| Web server with dashboard | **Pi** — Flask/Node, proper HTTP stack |
| Read a sensor and send to MQTT | **Either** — ESP32 is cheaper and simpler |
| Real-time motor control (µs precision) | **ESP32** — bare-metal GPIO |
| Machine learning inference | **Pi** — TensorFlow Lite, 512 MB RAM |
| Costs matters at 1000+ units | **ESP32** — $5 vs $15 |
| USB host (webcam, keyboard, storage) | **Pi** — USB OTG |
| BLE beacon / simple BLE peripheral | **ESP32** — lighter stack |
| Full TCP/IP + SSH + remote management | **Pi** — full Linux networking |
| Needs to boot in under 1 second | **ESP32** — 200 ms boot |
| Runs multiple concurrent services | **Pi** — Linux process model |
| Deployment in harsh/remote environment | **ESP32** — simpler, fewer failure modes |
| Prototype to production quickly | **Pi** for prototype → custom Linux board or ESP32 for production |

### The Hybrid Pattern

The most robust architecture for complex embedded products: **ESP32 for the real-time front end, Pi for the smart back end.**

```
Sensors ──→ ESP32 ──UART/I2C──→ Pi Zero 2 W ──WiFi──→ Cloud
  (analog,       (real-time       (processing,           (dashboard,
   digital,       sampling,        storage,               alerts,
   timing-        motor control,   web server,            analytics)
   critical)      deep sleep)      ML inference)
```

The ESP32 handles the physical world with microsecond precision and milliamp power. The Pi handles the computational world with gigabytes of storage and a full networking stack. They communicate over a simple serial or I2C link. Each does what it's best at.

---

## 20. Mastery Checklist

### Getting Started
- [ ] Flash Raspberry Pi OS Lite to an SD card with pre-configured WiFi and SSH
- [ ] Boot headless and SSH in successfully
- [ ] Set up a serial console with a USB-to-serial adapter
- [ ] Understand the boot partition layout (`config.txt`, `cmdline.txt`, kernel, overlays)

### Hardware Interfaces
- [ ] Blink an LED on GPIO using `libgpiod` (command line and Python)
- [ ] Read a button with edge detection using `gpiozero`
- [ ] Connect and read an I2C sensor (BME280 or similar) with `i2cdetect` and Python
- [ ] Drive an SPI display (OLED or TFT)
- [ ] Communicate over UART with another device (Arduino, GPS module)
- [ ] Enable and use the CSI camera with `libcamera` and `picamera2`

### System Administration
- [ ] Write a systemd service that starts your application at boot and restarts on failure
- [ ] Set up a systemd timer for periodic tasks
- [ ] Configure WiFi with NetworkManager (`nmcli`)
- [ ] Set up USB gadget mode (Ethernet over USB)
- [ ] Enable and configure the hardware watchdog

### Device Trees
- [ ] Enable I2C, SPI, and UART via `config.txt` dtparams
- [ ] Load a device tree overlay for a specific peripheral
- [ ] Read `/boot/firmware/overlays/README` to find the right overlay for your hardware

### Production & Deployment
- [ ] Set up a read-only root filesystem
- [ ] Harden SSH (key-only auth, disable root login, firewall)
- [ ] Cross-compile a C program and deploy to the Pi
- [ ] Use VS Code Remote-SSH for development
- [ ] Build a complete project: sensor + logger + web dashboard + systemd service
- [ ] Understand when to use a Pi vs. an ESP32 vs. a hybrid

---

## Where to Go Next

- **Keep the official [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/) open while you build** — the hardware, `config.txt`, and camera sections are accurate and current in a way most blog tutorials are not, and the [gpiozero docs](https://gpiozero.readthedocs.io/) have wiring recipes for nearly every component in this guide.
- **Read the datasheets when a peripheral misbehaves** — the [BCM2711/RP1 peripherals documentation](https://www.raspberrypi.com/documentation/computers/processors.html) explains the level of the machine that `raspi-config` hides, and a sensor's datasheet beats any forum thread.
- **Build the capstone project end to end:** a sensor logging to SQLite, exposed by a small web dashboard, supervised by systemd, surviving a reboot and an SD-card backup. It exercises every part of this guide and leaves you with a template for everything after.
- **Branch to microcontrollers when latency or power demands it** — the [ESP32 guide](ESP32_STUDY_GUIDE.md) covers the other half of the hobby-hardware world, and the Pi-as-brain + microcontroller-as-nerves hybrid is the architecture most serious projects converge on.
- **Adjacent guides in this repo:** [Linux Fundamentals](LINUX_FUNDAMENTALS_STUDY_GUIDE.md) and [Advanced Linux](ADVANCED_LINUX_STUDY_GUIDE.md) (a Pi is the perfect machine to break and rebuild), [Linux Networking](LINUX_NETWORKING_STUDY_GUIDE.md), and [Docker](DOCKER_STUDY_GUIDE.md) (containerized deploys to the Pi).

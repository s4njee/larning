# ESP32 Study Guide

A depth-first guide to the ESP32 — the Wi-Fi/Bluetooth microcontroller that dominates hobbyist and commercial IoT — for engineers who can write software but have never programmed a microcontroller, or have used an Arduino and want to understand what's actually happening underneath. It assumes you can read C and a little Python and are comfortable on a command line, but **not** that you know what a GPIO register is, why `delay()` is a sin, or how a chip with 520 KB of RAM runs a TCP/IP stack.

The throughline is a mental-model shift that this guide returns to constantly: **a microcontroller is not a small Linux computer.** If your reference point is the Raspberry Pi (the subject of an upcoming companion guide and the [Linux Fundamentals guide](LINUX_FUNDAMENTALS_STUDY_GUIDE.md)), almost everything is different — there is usually no operating system in the Linux sense, no filesystem you `cd` around, no processes, no `apt`. Your code *is* the firmware; it boots directly onto the metal, owns the whole chip, and never exits. Internalize that one difference and the rest of the ESP32 — its peripherals, its FreeRTOS tasks, its deep-sleep power model — falls into place. Get it wrong and you'll spend days confused about why there's no shell.

The back third of this guide is **worked sample projects**, because microcontrollers are learned by building. Each project is complete and buildable, escalating from "blink an LED" to a battery-powered sensor that sleeps for years to a Wi-Fi device you control from your phone.

Primary references: the [ESP-IDF Programming Guide](https://docs.espressif.com/projects/esp-idf/en/latest/) (Espressif's official C framework — the authoritative source), the [Arduino-ESP32 docs](https://docs.espressif.com/projects/arduino-esp32/en/latest/), the [MicroPython ESP32 docs](https://docs.micropython.org/en/latest/esp32/quickref.html), and Random Nerd Tutorials ([randomnerdtutorials.com](https://randomnerdtutorials.com/)) for project-oriented walkthroughs. Adjacent guides in this repo: [Linux Fundamentals](LINUX_FUNDAMENTALS_STUDY_GUIDE.md) (the contrast), [Networking Fundamentals](NETWORKING_FUNDAMENTALS.md) (TCP/IP, Wi-Fi), [Cryptography Fundamentals](CRYPTO_FUNDAMENTALS.md) (TLS, secure boot), [MQTT/WebSockets](WEBSOCKETS_STUDY_GUIDE.md) (real-time messaging), and the [Advanced C-adjacent concurrency](PYTHON_CONCURRENCY.md) ideas that reappear as FreeRTOS tasks.

---

## Table of Contents

1. [Part 1 — The Microcontroller Mindset](#part-1--the-microcontroller-mindset)
2. [Part 2 — The Chip & the Boards](#part-2--the-chip--the-boards)
3. [Part 3 — The Toolchain](#part-3--the-toolchain)
4. [Part 4 — GPIO & the Digital World](#part-4--gpio--the-digital-world)
5. [Part 5 — Analog, PWM & Buses (ADC, I2C, SPI, UART)](#part-5--analog-pwm--buses-adc-i2c-spi-uart)
6. [Part 6 — FreeRTOS, Tasks & Dual-Core](#part-6--freertos-tasks--dual-core)
7. [Part 7 — Wi-Fi, Bluetooth & Networking](#part-7--wi-fi-bluetooth--networking)
8. [Part 8 — Power Management & Deep Sleep](#part-8--power-management--deep-sleep)
9. [Part 9 — Sample Projects](#part-9--sample-projects)
10. [Part 10 — Production & Going Further](#part-10--production--going-further)

---

## Part 1 — The Microcontroller Mindset

Before any wiring, get the model right — because the ESP32 violates almost every assumption you carry from application or even systems programming, and naming those violations up front prevents most beginner confusion.

### Microcontroller vs. Microprocessor (vs. the Pi)

The single most clarifying distinction in embedded:

- A **microprocessor** (the chip in your laptop, or the Raspberry Pi's Broadcom SoC) is a CPU that needs *external* RAM, *external* storage, and an operating system to be useful. The Pi boots Linux off an SD card, runs processes, has a filesystem and a shell. It's a *small computer*.
- A **microcontroller** (MCU) — the ESP32 — is a *complete computer on one chip*: CPU, RAM, flash storage, and a pile of hardware peripherals (Wi-Fi radio, ADCs, timers, bus controllers) all integrated. It typically runs **one program, directly, forever**, with no OS in the Linux sense. It's not a small computer; it's a *programmable circuit*.

The practical consequences, each of which trips up newcomers from the software world:

- **No operating system, no shell, no filesystem to browse.** Your compiled code is the firmware; it's flashed to the chip and runs on boot. There's no `ssh` in, no `ls`, no package manager. (There *are* small flash filesystems for storing data — Part 4 — but you don't live in them.)
- **Your program never returns.** There's no "exit." Embedded programs are an infinite loop (Arduino's `loop()`) or a set of never-ending tasks (FreeRTOS, Part 6). When `main` would return, there's nowhere to return *to*.
- **You own everything.** No OS is scheduling around you, virtualizing memory, or protecting other processes — there are no other processes. A tight loop doesn't "hog the CPU" from anything; it *is* the CPU's job. (Except: the ESP32 secretly runs FreeRTOS and a second core handling Wi-Fi — Part 6 — which is the one place the "you own everything" model leaks.)
- **Resources are tiny and fixed.** A typical ESP32 has **520 KB of SRAM** and **4 MB of flash** — versus the Pi's gigabytes. There is no swap, no virtual memory, no "just add RAM." Run out and the chip crashes (a reboot, not an `OOMKilled` event). Memory discipline isn't an optimization; it's survival.
- **Time is real and physical.** Your code directly toggles voltages on physical pins, reads real sensors, and must meet real timing. A 10ms delay is 10ms of the world, not a scheduler hint.

### "Bare Metal," and the ESP32's Twist

Classic microcontroller programming is **bare metal**: your code is the only thing running, talking directly to hardware registers. The ESP32 *can* be used that way, but in practice it almost always runs **FreeRTOS**, a tiny real-time operating system baked into the framework. This is the ESP32's defining twist versus simpler MCUs (like an 8-bit Arduino Uno): it's a **dual-core, FreeRTOS-based, Wi-Fi-connected** MCU, which makes it vastly more capable but means "you own everything" is really "you own everything except the bits keeping the radio alive on the other core." We'll make peace with that in Part 6; for now, just know FreeRTOS is there even when you don't call it directly.

### The Development Loop

Because there's no OS to run your code *on the chip*, the workflow is **cross-compilation + flashing**, and it's worth seeing the whole cycle once:

```text
[ Your computer ]                          [ The ESP32 ]
  write C/Python  ─compile─►  firmware.bin
                                  │
                                  └──flash over USB──►  written to flash memory
                                                              │
                                                         chip reboots
                                                              │
                                                         runs your firmware
  serial monitor  ◄────────USB serial (115200 baud)──────────┘  (printf debugging)
```

You write code on your "big" computer, **cross-compile** it for the ESP32's architecture (Xtensa or RISC-V — Part 2), **flash** the resulting binary over USB to the chip's flash memory, the chip reboots and runs it, and you watch `printf`-style output stream back over the same USB cable as a **serial monitor**. That serial console is your primary debugging tool — embedded's equivalent of `console.log`, and for a long time the *only* window into what the chip is doing. (Real JTAG debugging exists — Part 10 — but serial `printf` is where everyone lives day to day.)

If you remember one thing from Part 1: **the ESP32 is a complete computer on a chip that runs one program forever with no OS, no shell, and tiny fixed memory — you cross-compile on your big machine, flash the binary over USB, and debug by reading serial output. It is a programmable circuit, not a small Linux box, and every other difference flows from that.**

```quiz
Q: What's the fundamental difference between a microcontroller (ESP32) and a microprocessor (Raspberry Pi's SoC)?
- [ ] The ESP32 is just slower
- [x] A microcontroller integrates CPU, RAM, flash, and peripherals on one chip and runs one program directly forever with no OS — it's a programmable circuit; a microprocessor needs external RAM/storage and an OS, making it a small computer
- [ ] They're the same; "ESP32" is a brand
- [ ] The Pi has no CPU
> The Pi boots Linux off an SD card, runs processes, and has a shell and filesystem — a small computer. The ESP32 is a complete computer on a single chip that you flash with firmware that runs on boot: no OS, no shell, no ls, no package manager. Every other difference (your program never returns, you own everything, resources are tiny and fixed) flows from this single distinction.

Q: On an ESP32, what happens when you run out of the ~520KB of SRAM?
- [ ] The OS kills the offending process
- [x] The chip crashes and reboots — there's no swap, no virtual memory, no OOMKilled event; memory discipline is survival, not optimization
- [ ] It swaps to flash automatically
- [ ] It allocates more RAM
> With no operating system, there's nothing to virtualize memory, swap to disk, or kill a runaway process — the resources are tiny and fixed. Exhausting RAM simply crashes the chip into a reboot. This is why embedded memory management is a survival concern: you account for every allocation because there's no safety net catching you when you overrun.

Q: Why is the development loop "cross-compile + flash" rather than running code directly on the chip?
- [ ] The ESP32 can't compile but can interpret
- [x] There's no OS or toolchain on the chip to build or launch programs, so you compile on your big machine to a firmware binary, flash it over USB, the chip reboots and runs it, and you debug by reading serial output
- [ ] Flashing is faster than running
- [ ] It's a licensing requirement
> The ESP32 has no shell, compiler, or process model — it just runs whatever firmware is in its flash on boot. So you build the binary on your computer (where the toolchain lives), transfer it over USB to the chip's flash, and the chip restarts into it. With no debugger console on-device, `printf`-over-serial (115200 baud to a serial monitor) is the primary debugging channel.
```

---

## Part 2 — The Chip & the Boards

"ESP32" names a *family*, not one chip, and buying or coding for the wrong variant is a classic first stumble. This part is the map: what's inside, how the variants differ, and what board to actually buy.

### What's Inside an ESP32

The original ESP32 (2016, still ubiquitous) integrates, on one die:

- **CPU:** dual-core **Xtensa LX6**, up to 240 MHz. Two cores is unusual for an MCU and central to its design (Part 6).
- **RAM:** **520 KB SRAM** (on-chip, shared between your code and the system). Some boards add external **PSRAM** (2–8 MB) for memory-hungry work like camera framebuffers.
- **Flash:** typically **4 MB** external flash (on the module) storing your firmware and a filesystem.
- **Wireless:** **Wi-Fi** (802.11 b/g/n, 2.4 GHz) and **Bluetooth** (Classic + BLE) — the headline feature, integrated radios with antennas on the module.
- **Peripherals:** ~34 GPIO pins, multiple **ADC** channels, two **DAC** channels, **I2C/SPI/UART** controllers, **PWM** (LEDC), hardware timers, a **touch** sensor, a **Hall** sensor, and a low-power **ULP** coprocessor.

That last list — the peripherals — is where most of your real work happens (Parts 4–5). The CPU is almost incidental; the value of an MCU is the hardware blocks wired to its pins.

### The Variant Family (Which One Do I Want?)

Espressif has released many variants; you'll meet a handful. The key split is **architecture** (the older Xtensa vs. the newer open RISC-V) and **feature tier**:

| Variant | Cores / Arch | Wireless | Niche |
|---|---|---|---|
| **ESP32** (original) | 2× Xtensa LX6 | Wi-Fi + BT Classic + BLE | The default workhorse; most tutorials target it |
| **ESP32-S2** | 1× Xtensa LX7 | Wi-Fi only (no BT) | Native USB; cheap; no Bluetooth |
| **ESP32-S3** | 2× Xtensa LX7 | Wi-Fi + BLE | **AI/ML acceleration**, native USB, more RAM — the modern high-end pick |
| **ESP32-C3** | 1× **RISC-V** | Wi-Fi + BLE | Cheap, low-power, open RISC-V core — the modern *budget* pick |
| **ESP32-C6** | 1× RISC-V | Wi-Fi 6 + BLE + **802.15.4** | Thread/Zigbee + **Matter**; the future-facing IoT pick |
| **ESP32-H2** | 1× RISC-V | BLE + 802.15.4 (no Wi-Fi) | Thread/Zigbee/Matter only |

Practical guidance for 2026: **start with a plain ESP32 or an ESP32-S3** (best documentation and tutorial coverage; the S3 if you want USB and more headroom), reach for a **C3** when cost and power matter, and look at the **C6** if you're targeting **Matter** (the cross-vendor smart-home standard built on Thread). Don't agonize — the programming model is nearly identical across them; the framework abstracts most differences.

### ESP32 vs. ESP8266 — The Predecessor, and Why You Want the ESP32

Before the ESP32 there was the **ESP8266** (2014), the chip that made Espressif famous — a sub-$2 Wi-Fi microcontroller that, at the time, was revolutionary. It's still widely sold (you'll see it as the **NodeMCU** and **Wemos/LOLIN D1 Mini** boards), still cheap, and still fine for the simplest jobs, so it's worth knowing exactly how it differs — because almost everyone arriving at the ESP32 has heard of, or owns, an ESP8266, and the question "do I really need the ESP32?" comes up immediately.

The ESP32 is the ESP8266's successor, and it's an upgrade on nearly every axis:

| | **ESP8266** | **ESP32** |
|---|---|---|
| **CPU** | 1× Xtensa, 80 MHz (160 OC) | **2× Xtensa, 240 MHz** |
| **RAM** | ~80 KB usable | **520 KB** |
| **GPIO** | ~11 usable, **quirky** | ~34 |
| **ADC** | **1 channel, 0–1.0V**, 10-bit | multiple channels, 0–3.3V, 12-bit |
| **Wireless** | Wi-Fi only | **Wi-Fi + Bluetooth Classic + BLE** |
| **Touch / DAC / Hall / CAN** | none | touch ×10, DAC ×2, Hall, CAN |
| **Hardware crypto / Secure Boot / Flash Encryption** | no | **yes** |
| **Deep-sleep current** | ~20 µA | ~10 µA (and far more capable wake sources) |
| **Price** | ~$1–3 | ~$2–6 |

### The Practical Advantages of Choosing the ESP32

Read past the spec table — here is what those differences *buy you* in real projects, which is what actually matters:

- **Bluetooth/BLE at all.** The ESP8266 has none. If you want a device a phone talks to directly, a BLE beacon, or anything Bluetooth, the ESP8266 simply can't — this alone decides many projects.
- **Enough RAM and CPU to do real work.** The ESP8266's ~80 KB is *tight* — TLS, a JSON parser, and a Wi-Fi stack together can exhaust it, and "out of memory" crashes are a constant ESP8266 frustration. The ESP32's 520 KB and dual 240 MHz cores run TLS, larger libraries, a web server, and your logic comfortably. The headroom is the difference between fighting the chip and forgetting about it.
- **Two cores, so Wi-Fi doesn't fight your code.** On the ESP8266 the single core is shared between your program and the Wi-Fi stack, so heavy code can starve the radio (and vice versa) — you must yield to it carefully. The ESP32 runs the radio on Core 0 and your code on Core 1 (Part 6), so the two don't compete; concurrency is dramatically easier.
- **Sane GPIO and analog.** The ESP8266's pins are notoriously quirky (several have boot-time constraints, some behave oddly, the count is low) and its single ADC reads only **0–1.0V at 10-bit** — awkward for most sensors. The ESP32 has ~34 pins, multiple 12-bit 0–3.3V ADC channels, plus DAC, touch, and Hall peripherals the 8266 lacks entirely.
- **Production-grade security.** The ESP32's hardware crypto acceleration, **Secure Boot**, and **Flash Encryption** (Parts 7, 10) make it a defensible product; the ESP8266 has none of this, which rules it out for anything where firmware theft or tampering matters.
- **A real future.** New Espressif investment, the variant family (S3 for ML, C6 for Matter — above), and the bulk of current tutorials and libraries all target the ESP32 line. The ESP8266 is in maintenance, not development.

**When the ESP8266 still makes sense:** a single-purpose Wi-Fi gadget where every cent counts and you need none of the above — a simple sensor that posts one reading, a smart plug, a hobby blinker. It's a fine *appliance* chip. But the price gap is now small (often a dollar or two), and the ESP32 removes so many ceilings that **for almost any new project — and certainly for learning — the ESP32 is the right default.** The extra capability you don't use today is capability you won't have to migrate to tomorrow. Treat the ESP8266 as the chip you reach for only when you've deliberately decided you need *less*.

### Boards vs. Modules vs. Chips

Three things people conflate:

- The **chip** (e.g., `ESP32-D0WD`) is the bare silicon — you won't handle this directly.
- The **module** (e.g., `ESP32-WROOM-32`, `ESP32-WROVER` with PSRAM) is the chip + flash + antenna + RF shielding on a small PCB, FCC-certified. This is what product designers solder onto their own boards.
- The **development board** (e.g., **DevKitC**, **NodeMCU-32S**, or boards from SparkFun/Adafruit/Seeed) is a module on a breakout PCB with a USB port, a USB-to-serial chip, a voltage regulator, and pin headers. **This is what you buy to learn** — plug it into USB and go.

Two buying notes that save real pain: get a board with a **USB-C** connector and a modern USB-serial chip (CP2102 or CH340 — you may need a driver), and beware that **pin numbering is by GPIO number, not physical position** — the silkscreen labels (`GPIO4`, `D2`, etc.) are what your code references, and they're scattered around the board, not sequential.

### The GPIO Pin Caveats (Read Before You Wire)

Not all pins are equal — and this catches everyone:

- **Input-only pins:** GPIO 34–39 can *only* read, never drive output (no internal pull-ups either).
- **Strapping pins** (GPIO 0, 2, 5, 12, 15) are read at boot to decide boot mode; pulling them the wrong way at power-on prevents booting. Avoid them for inputs that might be driven at reset.
- **Flash pins** (GPIO 6–11) are wired to the on-board flash chip — **using them bricks the running firmware.** Treat them as off-limits.
- **ADC2 conflicts with Wi-Fi:** the ADC2 pins can't do analog reads while Wi-Fi is active. Use ADC1 pins (GPIO 32–39) for analog if you also need Wi-Fi.

Keep a pinout diagram for your specific board open while wiring; "why doesn't this pin work?" is, nine times out of ten, one of the above.

If you remember one thing from Part 2: **"ESP32" is a family — pick a plain ESP32 or S3 to learn on, a C3 for cost/power, a C6 for Matter — and buy a *dev board* (module + USB + regulator). Prefer it over the older ESP8266 for nearly everything (Bluetooth, ~6× the RAM, two cores, real ADC, hardware security). Then respect the pin caveats: 34–39 are input-only, 6–11 are off-limits (flash), and the strapping pins must be left alone at boot.**

---

## Part 3 — The Toolchain

*Docs: [ESP-IDF get-started](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)*

There are several ways to program an ESP32, and the choice shapes your whole experience. This part lays them out honestly so you pick the right one for your goal rather than the first one a tutorial happened to use.

### The Three Ecosystems

**1. Arduino (the C++ framework).** The `Arduino-ESP32` core brings the familiar `setup()` / `loop()` model and the vast Arduino library ecosystem to the chip. It's the **easiest on-ramp** — `digitalWrite(2, HIGH)` just works, and there's a library for nearly every sensor. The cost is abstraction: you're insulated from how the chip actually works, performance is "good enough" rather than optimal, and you'll eventually hit its ceiling. **Best for: learning, prototyping, and most hobby projects.**

```cpp
// Arduino: the canonical structure. setup() runs once; loop() runs forever.
void setup() {
  Serial.begin(115200);
  pinMode(2, OUTPUT);
}
void loop() {
  digitalWrite(2, HIGH);
  delay(500);                 // (Part 6 explains why delay() is a beginner trap)
  digitalWrite(2, LOW);
  delay(500);
}
```

**2. ESP-IDF (Espressif's official C framework).** The "real" SDK — a CMake-based C framework exposing the full chip: FreeRTOS directly, fine-grained peripheral control, power management, secure boot, OTA. It's what commercial products ship on. Steeper learning curve, more boilerplate, but **no ceiling**. **Best for: production firmware, anything performance- or power-critical, and understanding the chip deeply.**

```c
// ESP-IDF: app_main is your entry point; you typically spawn FreeRTOS tasks from it.
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"

void app_main(void) {
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    while (1) {
        gpio_set_level(GPIO_NUM_2, 1);
        vTaskDelay(pdMS_TO_TICKS(500));   // FreeRTOS delay — yields the CPU (Part 6)
        gpio_set_level(GPIO_NUM_2, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
```

**3. MicroPython (and CircuitPython).** A full Python interpreter that runs *on the chip*. You get a **REPL over serial** — type Python live and watch the hardware respond — and a dramatically faster edit/test loop (no compile/flash cycle; just send the file). The trade-offs: it's slower than compiled C, uses more RAM, and isn't suited to hard real-time or power-critical work. But for learning, glue logic, and rapid prototyping it's delightful. **Best for: fast iteration, scripting, and Python-native developers.**

```python
# MicroPython: this runs ON the ESP32, interactively or from main.py
from machine import Pin
import time

led = Pin(2, Pin.OUT)
while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
```

### How to Choose

| If you want… | Use |
|---|---|
| The gentlest start, the most tutorials, the most libraries | **Arduino** |
| To ship a product, squeeze power/performance, or learn the chip fully | **ESP-IDF** |
| The fastest iteration and a live REPL, and you love Python | **MicroPython** |

A common and healthy path: **learn on Arduino or MicroPython, graduate to ESP-IDF** when you hit a wall (you need precise power control, a feature only IDF exposes, or you're going to production). They're not mutually exclusive across projects — pick per project.

### PlatformIO: The Tooling Layer

Whichever framework you choose (except MicroPython), **[PlatformIO](https://platformio.org/)** is the recommended way to manage it — a VS Code extension and CLI that handles toolchain installation, library dependencies, board configs, building, and flashing, all from a single `platformio.ini` file. It's a vastly better experience than the old Arduino IDE: real autocomplete, version-pinned dependencies, multi-environment builds, and CI-friendliness (it pairs naturally with the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md) for automated firmware builds).

```ini
; platformio.ini — declarative project config; `pio run -t upload` builds and flashes
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino          ; or "espidf"
monitor_speed = 115200
lib_deps =                   ; dependencies, version-pinned, auto-installed
    adafruit/DHT sensor library@^1.4.4
    bblanchon/ArduinoJson@^7.0.0
```

The flashing itself is done by **`esptool.py`** (Espressif's flash utility) under the hood — worth knowing the name, because when a flash fails you'll see it in the logs, and you can call it directly to read/erase flash or dump the chip.

If you remember one thing from Part 3: **three ecosystems — Arduino (easiest, learn here), ESP-IDF (production, full power), MicroPython (live REPL, fastest iteration) — and PlatformIO is the tooling layer that makes Arduino/IDF pleasant. Start easy, graduate to IDF when you hit a wall, and let the framework abstract the chip until you need to look under it.**

## Part 4 — GPIO & the Digital World

*Docs: [GPIO driver](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html)*

GPIO — General Purpose Input/Output — is the bedrock. Every LED, button, relay, and many sensors come down to reading or driving a voltage on a pin. This is where software meets the physical world, and the concepts here recur in every project.

### Digital Output: Driving a Pin

A pin configured as output is driven to one of two voltages: **HIGH** (3.3V on the ESP32 — *not* 5V, a critical fact below) or **LOW** (0V). That's the entire vocabulary of digital output, and it's enough to control an enormous amount:

```cpp
pinMode(2, OUTPUT);
digitalWrite(2, HIGH);   // pin 2 → 3.3V  (LED on, relay closed, etc.)
digitalWrite(2, LOW);    // pin 2 → 0V
```

The chip can source/sink only a small current per pin (~12–40 mA, with a total budget across all pins). That's enough for an LED (with a resistor) but **not** for a motor, a relay coil, or a strip of LEDs — those need a transistor, a driver IC, or a relay module to switch the real load while the pin just controls the switch. Trying to drive a big load directly from a pin is a fast way to kill the chip.

### Digital Input: Reading a Pin, and the Pull-Resistor Trap

A pin configured as input reads HIGH or LOW based on the voltage applied. The trap that catches every beginner: **a disconnected input pin doesn't read LOW — it reads garbage.** It "floats," picking up electrical noise and flipping randomly. A button connects the pin to either 3.3V or GND *when pressed*, but what voltage does the pin see when the button is *not* pressed? Nothing — unless you provide a **pull resistor**:

- A **pull-up** resistor weakly ties the pin to 3.3V, so it reads HIGH when idle; the button connects it to GND, reading LOW when pressed.
- A **pull-down** does the opposite.

The ESP32 has *internal* pull-ups/downs you enable in software — use them and you need no external resistor:

```cpp
pinMode(4, INPUT_PULLUP);          // idle = HIGH; button to GND makes it LOW when pressed
void loop() {
  if (digitalRead(4) == LOW) {     // LOW = pressed (because of the pull-up)
    // ...
  }
}
```

(Recall from Part 2: input-only pins 34–39 have *no* internal pull resistors, so a button on those needs an external one. Another reason to keep the pinout handy.)

### Debouncing: The Physical World Is Messy

Press a button and the metal contacts physically *bounce* for a few milliseconds, making/breaking contact several times. To the fast ESP32, one human press looks like 5–20 rapid presses. **Debouncing** filters this — the simplest approach is to ignore further changes for a short window after a transition:

```cpp
unsigned long lastPress = 0;
void loop() {
  if (digitalRead(4) == LOW && millis() - lastPress > 50) {   // 50ms debounce window
    lastPress = millis();
    handlePress();                                            // fires once per real press
  }
}
```

Debouncing is a microcosm of the whole embedded mindset: the physical world is noisy and analog, and your clean digital logic has to defend against it. Real sensors, real signals, real timing — all need this kind of defensive handling.

### Interrupts: Don't Poll When You Can Be Told

The loop above *polls* — it checks the pin millions of times a second, wasting CPU and possibly missing a fast event between checks. The better pattern for time-critical or rare events is an **interrupt**: register a function (an ISR — Interrupt Service Routine) that the hardware calls *the instant* a pin changes, regardless of what the main code is doing:

```cpp
volatile bool pressed = false;                       // 'volatile': changed outside normal flow

void IRAM_ATTR onButtonPress() {                     // IRAM_ATTR: keep the ISR in fast RAM
  pressed = true;                                    // do the MINIMUM here — just flag it
}

void setup() {
  pinMode(4, INPUT_PULLUP);
  attachInterrupt(4, onButtonPress, FALLING);        // fire on HIGH→LOW transition
}
void loop() {
  if (pressed) { pressed = false; handlePress(); }   // do the real work back in loop()
}
```

Two rules every ISR must follow, and both bite hard if ignored: **keep it tiny and fast** (an ISR blocks everything else while it runs — set a flag, don't do real work), and **mark shared variables `volatile`** so the compiler doesn't optimize away reads of a value it thinks "can't change." The pattern — ISR sets a flag, main loop does the work — is the safe, standard shape.

```quiz
Q: A button wired to an input pin reads randomly HIGH and LOW when untouched. Why, and what's the fix?
- [ ] The pin is broken
- [x] A disconnected input *floats* — it picks up electrical noise instead of a defined level; a pull resistor (internal `INPUT_PULLUP` ties it to 3.3V so it reads HIGH idle, the button pulls it to GND) gives it a stable default
- [ ] The button needs debouncing
- [ ] The pin needs more current
> An input pin has no inherent voltage; with nothing driving it, it floats and flips on ambient noise. A pull-up weakly ties it to 3.3V (reads HIGH idle, LOW when the button connects it to ground), or a pull-down does the reverse. The ESP32's internal pulls (`INPUT_PULLUP`) cover most cases — except input-only pins 34–39, which have none and need an external resistor.

Q: Why does a single human button press sometimes register as 5–20 presses, and how is it fixed?
- [ ] The CPU is too fast to read buttons
- [x] The metal contacts physically *bounce* for a few milliseconds, making/breaking contact repeatedly; debouncing ignores further changes for a short window (e.g. 50ms) after a transition so one press fires once
- [ ] The pull resistor is wrong
- [ ] An interrupt is required
> Mechanical contacts don't switch cleanly — they chatter as they settle, and the fast ESP32 sees each bounce as a separate edge. Debouncing filters this in software (suppress changes within ~50ms of the last) or hardware (an RC filter). It's a microcosm of embedded work: clean digital logic must defend against a noisy analog physical world.

Q: An interrupt service routine (ISR) must "do the minimum and set a flag." Why those two rules — tiny/fast and `volatile`?
- [ ] ISRs can't call functions
- [x] An ISR blocks everything else while it runs, so doing real work there stalls the system — set a flag and handle it in the main loop; and shared variables need `volatile` so the compiler doesn't optimize away re-reads of a value it assumes can't change
- [ ] volatile makes the ISR faster
- [ ] ISRs run on the other core
> An interrupt preempts all other code, so a long ISR freezes the device — the standard pattern is ISR-sets-flag, loop-does-work. And because the ISR changes a variable "outside normal flow," `volatile` tells the compiler the value really can change between reads, preventing it from caching a stale value. Skipping either rule produces hangs or phantom missed events that are maddening to debug.
```

### A Note on Persistent Storage

There's no filesystem you browse, but you *can* persist data across reboots. Two mechanisms:

- **NVS (Non-Volatile Storage)** / the Arduino `Preferences` library — a small key-value store in flash for settings (Wi-Fi credentials, a counter, calibration values). The right tool for "remember this small thing."
- **SPIFFS / LittleFS** — actual small filesystems in flash for files (a config JSON, a web page to serve, logged data). LittleFS is preferred (more robust to power loss).

A caveat from the hardware: **flash has limited write endurance** (~10,000–100,000 erase cycles per sector). Don't write a counter to flash every second — you'll wear it out in weeks. Buffer in RAM and persist occasionally, or use the RTC memory that survives deep sleep (Part 8).

If you remember one thing from Part 4: **digital I/O is just HIGH (3.3V) / LOW (0V), but the physical world demands defenses — pull resistors so inputs don't float, debouncing so one press isn't five, interrupts (tiny, `volatile`, flag-only) instead of polling for fast events — and the chip drives only milliamps, so real loads need a transistor or relay.**

---

## Part 5 — Analog, PWM & Buses (ADC, I2C, SPI, UART)

*Docs: [peripherals API reference](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/index.html)*

Digital is two values; the real world is continuous, and most interesting peripherals speak a protocol rather than a single voltage. This part covers reading analog signals, *faking* analog output with PWM, and the three serial buses that connect the vast majority of sensors and displays.

### ADC: Reading Analog Voltages

An **ADC (Analog-to-Digital Converter)** turns a continuous voltage into a number. A potentiometer, a light sensor (LDR), a temperature sensor, a battery-voltage divider — all produce a voltage you read with the ADC. The ESP32's ADC is **12-bit**, so it maps 0–3.3V to an integer 0–4095:

```cpp
int raw = analogRead(34);                  // 0..4095 for 0..3.3V (GPIO34 is ADC1)
float voltage = raw * 3.3 / 4095.0;        // convert back to volts
```

Two honest caveats: the ESP32's ADC is **noisy and non-linear** (don't trust it for precision measurement without calibration and averaging), and — from Part 2 — **ADC2 doesn't work while Wi-Fi is on**, so use ADC1 pins (32–39) in any networked project. For analog *output*, the ESP32 has two true **DAC** channels (GPIO 25/26), but you'll more often use PWM (below).

### PWM: Faking Analog Output

The chip can't output an arbitrary voltage on most pins, but it can switch a pin HIGH/LOW *very fast* and vary the **duty cycle** — the fraction of time it's HIGH. Average that over time and you get an effective analog level: 25% duty ≈ 25% brightness on an LED, or a specific position on a servo, or a motor speed. This is **PWM (Pulse-Width Modulation)**, and on the ESP32 it's provided by the **LEDC** peripheral:

```cpp
// Arduino-ESP32 v3: configure a PWM channel and write a duty cycle.
ledcAttach(5, 5000, 8);        // pin 5, 5 kHz frequency, 8-bit resolution (0..255)
ledcWrite(5, 128);             // 50% duty → LED at half brightness / motor at half speed
```

PWM is how you dim LEDs, drive servos, control motor speed, and generate tones — anywhere you need a *proportional* output from a digital pin. Frequency and resolution are a tradeoff (higher resolution caps the max frequency); the defaults above suit LEDs and motors.

### The Three Buses: How Sensors Actually Connect

Most sensors and modules don't give you a raw voltage — they're little digital devices that speak a **bus protocol**. Three dominate, and knowing when each applies saves enormous confusion:

**I2C — the workhorse for sensors.** Two wires (`SDA` data, `SCL` clock) shared by *many* devices, each with a unique address. Slow-ish but wire-efficient — perfect for sensors (temperature, pressure, accelerometers) and small OLED displays. You can hang a dozen sensors off the same two pins.

```cpp
#include <Wire.h>
void setup() {
  Wire.begin(21, 22);              // SDA=GPIO21, SCL=GPIO22 (ESP32 defaults)
  Wire.beginTransmission(0x76);    // talk to the device at address 0x76 (e.g., BME280)
  Wire.write(0xD0);                // ask for its chip-ID register
  Wire.endTransmission();
  Wire.requestFrom(0x76, 1);       // read 1 byte back
  byte id = Wire.read();
}
```

**SPI — when you need speed.** Four wires (`MOSI`, `MISO`, `SCK`, plus a chip-select per device), much faster than I2C. Used for displays, SD cards, and high-data-rate sensors. More pins, more speed.

**UART — point-to-point serial.** Two wires (`TX`/`RX`), the same protocol as your USB serial console. Used for GPS modules, some sensors, and talking to other microcontrollers or a computer. The ESP32 has three UARTs; UART0 is the one tied to USB for your debug console.

| Bus | Wires | Speed | Devices | Typical use |
|---|---|---|---|---|
| **I2C** | 2 (SDA, SCL) | ~100k–400k Hz | many (addressed) | sensors, small OLEDs — the default |
| **SPI** | 4 (+CS each) | tens of MHz | several (per CS) | displays, SD cards, fast sensors |
| **UART** | 2 (TX, RX) | configurable | 1 (point-to-point) | GPS, modules, MCU-to-MCU |

The good news: you rarely speak these protocols by hand. A sensor comes with a **library** (`Adafruit_BME280`, `TinyGPS++`, an OLED driver) that wraps the bus details, so your code is `bme.readTemperature()`, not raw register pokes. Knowing *which bus* a part uses tells you how to wire it and which library to grab.

```quiz
Q: In a networked ESP32 project, why must you read analog sensors on ADC1 pins (32–39) specifically?
- [ ] ADC1 is more accurate
- [x] ADC2 doesn't work while Wi-Fi is on (the radio uses it), so any sensor read on an ADC2 pin fails in a connected project — ADC1 pins keep working alongside Wi-Fi
- [ ] ADC2 pins are output-only
- [ ] ADC1 is faster to sample
> The Wi-Fi radio shares the ADC2 hardware, so attempts to read ADC2 channels return errors (or junk) whenever Wi-Fi is active. Since most ESP32 projects are networked, you route analog sensors to ADC1 pins. Two further honest caveats: the ADC is noisy and non-linear (average and calibrate for precision), and it's 12-bit (0–4095 maps 0–3.3V).

Q: The ESP32 can't output an arbitrary voltage on most pins, yet you can dim an LED smoothly. How?
- [ ] It uses the DAC on every pin
- [x] PWM — it switches the pin HIGH/LOW very fast and varies the *duty cycle* (fraction of time HIGH); averaged over time, 25% duty ≈ 25% brightness, and the same trick drives servos and motor speed
- [ ] It lowers the supply voltage
- [ ] It can't — LEDs are only on/off
> Pulse-Width Modulation fakes a proportional output from a purely digital pin: the LED (or motor, or servo) responds to the *average* of a fast on/off square wave, set by the duty cycle. On the ESP32 the LEDC peripheral generates this. Two true DAC channels exist (GPIO 25/26) for real analog output, but PWM is the workhorse for dimming, speed control, and tone generation.

Q: How do you decide which of I2C, SPI, or UART a sensor uses, and why does it usually not matter to your code?
- [ ] You configure the bus protocol by hand each time
- [x] The part's datasheet tells you (I2C = 2 shared addressed wires and the sensor default, SPI = faster with a chip-select per device, UART = point-to-point) — but a library wraps the bus so your code is `bme.readTemperature()`, not raw register pokes; you mainly need to know which bus to wire
- [ ] All sensors use I2C
- [ ] The ESP32 auto-detects the protocol
> Knowing the bus tells you how to wire the part (two wires vs four-plus-CS) and which library to grab, but you rarely speak the protocol directly — `Adafruit_BME280`, `TinyGPS++`, and OLED drivers handle the transactions. I2C suits many slow addressed sensors on shared wires, SPI suits fast devices like displays and SD cards, UART suits point-to-point modules like GPS. Pick by the datasheet, then let the library abstract it.
```

If you remember one thing from Part 5: **the ADC reads voltages (0–4095 for 0–3.3V, noisy, ADC1 only with Wi-Fi), PWM fakes analog output by varying duty cycle (LEDs, servos, motors), and most sensors connect over one of three buses — I2C (two shared wires, the sensor default), SPI (fast, more wires), or UART (point-to-point) — almost always behind a library so you call `readTemperature()`, not the bus directly.**

---

## Part 6 — FreeRTOS, Tasks & Dual-Core

*Docs: [FreeRTOS (IDF)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos_idf.html)*

Here's where the ESP32 stops being a simple Arduino and becomes a real concurrent system. Underneath even the friendly `setup()`/`loop()` model runs **FreeRTOS**, a real-time operating system, on **two CPU cores**. Understanding it is what lets you do more than one thing at once — and it explains the most common beginner bug, the frozen device.

### `delay()` Is a Lie (The Cardinal Beginner Trap)

Start with the bug, because it teaches the whole lesson. The Part 1 blink used `delay(500)`. It works for blinking, but consider:

```cpp
void loop() {
  digitalWrite(2, HIGH);
  delay(1000);                 // ← for this entire second, NOTHING else can happen
  digitalWrite(2, LOW);
  delay(1000);                 // ← can't read a button, handle Wi-Fi, update a display
}
```

`delay()` **blocks** — for those two seconds, your device is frozen to everything else. A button press is missed; an incoming network packet waits. This is the embedded version of "never block the event loop" from the [Python Concurrency](PYTHON_CONCURRENCY.md) and Node guides — the *exact same lesson*, on bare metal. Two ways out: the cooperative `millis()` pattern, or real concurrency with FreeRTOS tasks.

**The `millis()` pattern** (non-blocking, single loop): instead of *waiting*, check whether enough time has *passed*, and do other work in between:

```cpp
unsigned long lastBlink = 0;
bool ledOn = false;
void loop() {
  if (millis() - lastBlink >= 1000) {    // has a second elapsed? (don't wait — check)
    lastBlink = millis();
    ledOn = !ledOn;
    digitalWrite(2, ledOn);
  }
  checkButton();                          // these run continuously, never blocked
  handleNetwork();
}
```

This is the bread-and-butter pattern for doing several things "at once" in one loop. But it gets unwieldy with many timed activities — which is what tasks are for.

### FreeRTOS Tasks: Real Concurrency

FreeRTOS lets you split your program into independent **tasks**, each its own infinite loop with its own stack, scheduled preemptively by the RTOS. (`loop()` is itself just a task FreeRTOS created for you.) Now "blink the LED *and* read the sensor *and* serve Wi-Fi" becomes three tasks that genuinely run concurrently:

```cpp
void blinkTask(void *param) {
  pinMode(2, OUTPUT);
  while (1) {                                  // each task is its own infinite loop
    digitalWrite(2, HIGH);
    vTaskDelay(pdMS_TO_TICKS(500));            // ← yields the CPU to other tasks (NOT delay!)
    digitalWrite(2, LOW);
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}
void sensorTask(void *param) {
  while (1) {
    readAndPublishSensor();
    vTaskDelay(pdMS_TO_TICKS(60000));          // every 60s; sleeps without blocking others
  }
}

void setup() {
  // xTaskCreate(function, name, stack_bytes, param, priority, handle)
  xTaskCreate(blinkTask,  "blink",  2048, NULL, 1, NULL);
  xTaskCreate(sensorTask, "sensor", 4096, NULL, 1, NULL);
}
void loop() {}                                 // can be left empty — tasks do the work
```

The crucial distinction: **`vTaskDelay()` yields** — while one task "sleeps," the scheduler runs others — whereas **`delay()` blocks** (well, in Arduino-ESP32 `delay()` actually calls `vTaskDelay` so it yields too, but the *mental model* you want is "vTaskDelay = cooperative sleep"). Tasks have **priorities** (higher preempts lower) and each gets a fixed **stack** you size at creation — too small and the task overflows and crashes (a common bug; size generously, ~2–4KB, and watch for stack-overflow resets).

### Talking Between Tasks Safely

Tasks share memory, so — exactly as in the [Python Concurrency guide](PYTHON_CONCURRENCY.md)'s threading section — **shared mutable state is a hazard** and needs synchronization. FreeRTOS gives you the primitives:

- **Queues** — the *preferred* way to pass data between tasks (e.g., a sensor task pushes readings, a network task consumes them). Thread-safe by construction; prefer them over shared variables.
- **Mutexes / semaphores** — guard a shared resource (a bus, a global) so two tasks don't corrupt it.

```cpp
QueueHandle_t readingQueue;
void setup() {
  readingQueue = xQueueCreate(10, sizeof(float));   // holds up to 10 floats
}
void sensorTask(void *p) {
  while (1) {
    float t = readTemp();
    xQueueSend(readingQueue, &t, 0);                // producer
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}
void networkTask(void *p) {
  float t;
  while (1) {
    if (xQueueReceive(readingQueue, &t, portMAX_DELAY))   // consumer; blocks until data
      publish(t);
  }
}
```

This is the producer/consumer pattern from the concurrency guide, on a microcontroller. The ideas transfer directly — only the API names change.

### Two Cores, and Who Uses Them

The ESP32 has **two cores**: **Core 0** ("PRO_CPU") and **Core 1** ("APP_CPU"). By default, the **Wi-Fi/Bluetooth stack runs on Core 0** and your Arduino `loop()` runs on **Core 1**. This is the one place Part 1's "you own everything" breaks: the radio genuinely needs CPU time, and if your code hogs the core the network stack lives on, Wi-Fi stutters or drops. You can **pin a task to a specific core** with `xTaskCreatePinnedToCore(...)` — useful to keep a timing-critical task off the Wi-Fi core, or to deliberately parallelize heavy computation across both. For most projects the defaults are fine; reach for pinning when Wi-Fi and a busy task are fighting.

If you remember one thing from Part 6: **the ESP32 secretly runs FreeRTOS on two cores — `delay()` blocking everything is the cardinal beginner bug, fixed with the non-blocking `millis()` pattern or real FreeRTOS tasks (use `vTaskDelay` to yield, size stacks generously, pass data via queues not shared variables), and Core 0 runs the Wi-Fi stack, so don't starve it.**

```quiz
Q: Why does `delay(1000)` in `loop()` freeze the device, and what's the non-blocking fix?
- [ ] delay() is too imprecise
- [x] `delay()` blocks — for that whole second nothing else runs (button presses missed, packets wait), the embedded version of "never block the event loop"; the `millis()` pattern checks whether enough time has *passed* instead of waiting, letting other work run in between
- [ ] delay() consumes too much power
- [ ] The fix is a longer delay
> Blocking for a second means the single loop can't read inputs, service Wi-Fi, or update a display during that time. The cooperative `millis()` pattern flips waiting into checking: `if (millis() - last >= interval)` does the timed work and falls through to run everything else continuously. It's the same don't-block-the-loop lesson from the Python/Node async guides, applied on bare metal.

Q: What's the practical difference between `vTaskDelay()` and `delay()` in a FreeRTOS task?
- [ ] vTaskDelay is more accurate
- [x] `vTaskDelay()` *yields* the CPU so the scheduler runs other tasks while this one "sleeps," whereas the mental model for `delay()` is a busy block; the cooperative-sleep model is what lets multiple tasks run concurrently
- [ ] vTaskDelay never returns
- [ ] They can't be used together
> In a multi-task design, a task that needs to wait should yield the core so others make progress — that's `vTaskDelay`. Picturing it as "cooperative sleep" (vs `delay` as "block") is the right model, even though Arduino-ESP32's `delay()` actually calls `vTaskDelay` under the hood. Tasks also each get a fixed stack sized at creation — too small overflows and crashes, so size generously (~2–4KB).

Q: The Wi-Fi stack runs on Core 0 by default while your `loop()` runs on Core 1. Why does that matter?
- [ ] Core 0 is faster
- [x] It's the one place "you own everything" breaks — the radio genuinely needs CPU time, so a task hogging the Wi-Fi core makes the network stutter or drop; pin a busy/timing-critical task to the other core with `xTaskCreatePinnedToCore` when they fight
- [ ] You must never use Core 0
- [ ] Bluetooth disables Core 1
> The networking stack isn't free — it needs scheduler time on Core 0, and starving it causes dropped connections. Most projects are fine on defaults, but when a CPU-heavy or tightly-timed task competes with Wi-Fi, pinning it to Core 1 (or deliberately parallelizing across both) resolves the contention. It's the practical exception to the bare-metal "nothing else is running" assumption.
```

---

## Part 7 — Wi-Fi, Bluetooth & Networking

*Docs: [Wi-Fi driver](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi.html)*

The radios are the ESP32's reason to exist — a $5 chip that puts a sensor on your Wi-Fi or talks BLE to your phone. This part covers connecting, the two roles Wi-Fi can play, the messaging protocols that make IoT work, and the security you must not skip.

### Connecting to Wi-Fi (Station Mode)

The common case: the ESP32 joins your existing network as a **station** (a client, like your laptop):

```cpp
#include <WiFi.h>
void setup() {
  Serial.begin(115200);
  WiFi.begin("MySSID", "password");
  while (WiFi.status() != WL_CONNECTED) {    // connecting takes a few seconds
    delay(500); Serial.print(".");
  }
  Serial.println(WiFi.localIP());            // now it has a DHCP-assigned IP
}
```

Once connected it has an IP and the full TCP/IP stack (the [Networking Fundamentals guide](NETWORKING_FUNDAMENTALS.md) applies — DHCP, DNS, TCP all work). Two realities to design for: connecting takes **seconds** (and costs power — Part 8), and Wi-Fi **drops** (handle reconnection; don't assume a connection stays up forever — the failure-handling instincts from the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) apply even here).

### Access Point Mode & the Provisioning Problem

The ESP32 can also *be* a Wi-Fi network — **Access Point (AP) mode** — that your phone connects to directly. This solves a real chicken-and-egg problem: **how do you tell a headless device your Wi-Fi password?** It has no keyboard. The standard answer, **captive-portal provisioning**: the device boots as an AP, you connect your phone to it, a web page pops up where you enter your home Wi-Fi credentials, the device saves them to NVS (Part 4) and reboots into station mode. Libraries like **WiFiManager** do this in a few lines, and it's how most commercial smart devices are set up.

### Talking to the World: HTTP, MQTT, WebSockets

Once networked, the ESP32 can be a client or a server. The protocol you choose matters:

- **HTTP** — the ESP32 as a client `POST`ing readings to an API, or as a tiny *server* hosting a control page. Simple, universal, but heavyweight for frequent small messages (a full request/response per reading).
- **MQTT — the IoT default, and the one to learn.** A lightweight **publish/subscribe** protocol designed for exactly this: many small, intermittent messages from constrained devices. The device *publishes* readings to a **topic** on a **broker** (Mosquitto, HiveMQ, or a cloud IoT service); other clients *subscribe*. It's efficient, handles intermittent connectivity gracefully, and decouples devices from consumers — the same pub/sub and broker concepts as the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md)'s messaging chapter, sized for microcontrollers.

```cpp
#include <PubSubClient.h>           // MQTT client
// ... connect Wi-Fi, then:
client.setServer("broker.local", 1883);
client.connect("esp32-sensor-01");
client.publish("home/livingroom/temp", "21.5");      // publish a reading
client.subscribe("home/livingroom/setpoint");         // listen for commands
```

- **WebSockets** — when you need a persistent, low-latency, bidirectional channel (a live dashboard, a remote-control UI). The [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) covers the protocol; on the ESP32 you'd use it to push live data to a browser without polling.

The decision in one line: **MQTT for device telemetry and commands** (the IoT norm), **HTTP for occasional posts or a simple config page**, **WebSockets for live bidirectional UIs**.

### Bluetooth & BLE

The ESP32 also speaks **Bluetooth Low Energy (BLE)** — ideal for short-range, low-power, phone-to-device interaction where there's no Wi-Fi: a fitness sensor, a configuration app, a beacon. BLE's model is **GATT** (services and characteristics — structured values a phone reads/writes/subscribes to). It's more complex than Wi-Fi but uses far less power and needs no network infrastructure. (Note: the C3/C6/H2 variants do BLE; the original ESP32 also does classic Bluetooth; the S2 has no Bluetooth at all — Part 2.) Reach for BLE when the consumer is a nearby phone and power or the absence of Wi-Fi rules out the network.

### Security You Cannot Skip

A networked device is an attack surface, and IoT's security reputation is poor for good reason. The non-negotiables, all building on the [Cryptography](CRYPTO_FUNDAMENTALS.md) and [Auth](AUTH_STUDY_GUIDE.md) guides:

- **Use TLS.** The ESP32 has hardware crypto acceleration and can do `https://` and `mqtts://`. Plain HTTP/MQTT sends your data — and any credentials — in the clear over the air. Validate the server's certificate (ship the CA cert in firmware).
- **Never hardcode secrets in firmware you distribute.** Firmware can be read off the flash. Use per-device credentials, provisioned at setup, stored in NVS.
- **Enable Secure Boot and Flash Encryption** for production (Part 10) — they stop an attacker who has physical access from reading your firmware or running modified code.
- **Authenticate commands.** If your device acts on incoming MQTT messages, make sure they're from an authorized source — an unauthenticated "unlock the door" topic is a real vulnerability.

If you remember one thing from Part 7: **the ESP32 joins Wi-Fi as a station (handle the multi-second connect and inevitable drops) or hosts an AP for credential provisioning; MQTT pub/sub is the IoT messaging default (HTTP for occasional posts, WebSockets for live UIs, BLE for nearby phones); and TLS plus per-device secrets are not optional — a networked device is an attack surface.**

---

## Part 8 — Power Management & Deep Sleep

*Docs: [sleep modes](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/sleep_modes.html)*

This is the part that makes battery-powered IoT actually possible, and it's where the microcontroller most dramatically beats the Pi: an ESP32 can run for *years* on a battery by being asleep ~99.9% of the time. If your device plugs into the wall, you can skim this; if it runs on a battery or solar, this part *is* the project.

### The Power Problem

A running ESP32 with Wi-Fi active draws **~150–260 mA** — that flattens a small battery in a day. But most sensor jobs are bursty: wake up, read a sensor, send the reading, then *do nothing for 10 minutes*. The entire game of low-power design is **minimizing the time spent awake** and making the idle time draw as close to zero as possible. The chip provides power modes spanning six orders of magnitude of current:

| Mode | Current (approx.) | What's on | Wake source |
|---|---|---|---|
| **Active** (Wi-Fi) | 150–260 mA | everything + radio | — |
| **Modem-sleep** | ~20–40 mA | CPU on, radio off between beacons | automatic |
| **Light-sleep** | ~0.8 mA | CPU paused, RAM retained, fast wake | timer, GPIO, etc. |
| **Deep-sleep** | **~10 µA** | almost everything off; RTC + RAM survive | timer, GPIO, touch, ULP |
| **Hibernation** | ~5 µA | only RTC timer | timer |

The leap that matters is **Active → Deep-sleep: ~200 mA down to ~10 µA, a 20,000× reduction.** That's the difference between a day and a decade on the same battery.

### Deep Sleep: The Workhorse Pattern

Deep sleep is the key technique, and it requires a mental adjustment: **waking from deep sleep is essentially a reboot.** The CPU restarts, your code runs from the top — RAM is wiped, variables reset. So the pattern isn't "loop with a long sleep"; it's **"do one job, then sleep, and on wake do the job again from scratch":**

```cpp
RTC_DATA_ATTR int bootCount = 0;        // RTC_DATA_ATTR: survives deep sleep (RTC memory)

void setup() {
  Serial.begin(115200);
  bootCount++;                          // persisted across sleeps via RTC memory
  Serial.printf("Wake #%d\n", bootCount);

  float temp = readSensor();            // 1. do the one job: read
  connectWiFiAndPublish(temp);          // 2. send it (the expensive, awake part)

  esp_sleep_enable_timer_wakeup(600ULL * 1000000ULL);  // 3. arm a 600-second (10 min) timer
  esp_deep_sleep_start();               // 4. sleep at ~10µA — code below never runs
}
void loop() {}                          // never reached — setup() sleeps before returning
```

`RTC_DATA_ATTR` is how you keep a little state across the "reboot" — the RTC memory (~8KB) survives deep sleep when SRAM doesn't, so counters, calibration, and "what state was I in" go there. Wake sources are flexible: a **timer** (every N minutes), a **GPIO** (a door sensor or button — wake only when something happens), the **touch** peripheral, or the **ULP coprocessor** (below).

### Wringing Out the Last Microamps

Getting from "works" to "lasts years" is a series of refinements, and they're where real battery projects live:

- **Minimize awake time.** Wi-Fi connection is the power hog (seconds at ~200mA). Connect fast: store a **static IP** and the AP's channel/BSSID in RTC memory to skip DHCP and scanning, which can cut wake time from ~5s to <1s — often the single biggest win.
- **Batch before you transmit.** If you can tolerate latency, take readings into RTC memory across several wakes and transmit a batch once — amortizing the expensive Wi-Fi connection over many readings.
- **The ULP coprocessor** can run a tiny program while the main CPUs are in deep sleep — e.g., poll a sensor and only wake the big cores when a threshold is crossed. This is how you monitor continuously at microamp power.
- **Mind the board, not just the chip.** A dev board's USB-serial chip, power LED, and voltage regulator can draw *more* in sleep than the ESP32 itself. For real battery products you design a custom board (or pick a low-power one like an Adafruit Feather) — the ~10µA figure is the *chip*, not a typical dev board with its always-on LED burning 5mA.

### The Battery Math

The payoff calculation, worth doing for any battery project: with a 2000 mAh battery, a device that wakes for 3 seconds every 10 minutes — drawing ~150mA awake and ~10µA asleep — averages roughly *0.085 mA*, which is **on the order of two years** on that battery. The same device using `delay()` instead of deep sleep (staying awake at ~150mA) lasts about **half a day**. That ~1000× difference is entirely the sleep strategy — which is why this part exists and why deep sleep is the defining skill of battery IoT.

```quiz
Q: Why is deep sleep the "workhorse" for battery IoT, and what mental adjustment does it require?
- [ ] It overclocks the CPU
- [x] It drops draw from ~200mA to ~10µA (a 20,000× cut), and waking is essentially a *reboot* — code runs from the top with RAM wiped — so you design "do one job, sleep, repeat from scratch," persisting any needed state in RTC memory (`RTC_DATA_ATTR`)
- [ ] It keeps Wi-Fi connected while idle
- [ ] It pauses the program in place and resumes
> Most sensor jobs are bursty (read, send, idle for minutes), so the win is making the idle draw near-zero. Deep sleep does that, but it's not a pause — the CPU restarts and `setup()` runs again, SRAM cleared. Hence the pattern: each wake reads the sensor, transmits, arms a timer, and sleeps before returning. A small amount of state (counters, calibration, last AP channel) survives in the ~8KB RTC memory via `RTC_DATA_ATTR`.

Q: For a deep-sleep sensor, why is "connect to Wi-Fi fast" often the single biggest battery win?
- [ ] Wi-Fi uses no power once connected
- [x] The radio is the power hog — connecting takes seconds at ~200mA, dominating each wake's energy; caching a static IP and the AP's channel/BSSID in RTC memory skips DHCP and scanning, cutting wake time from ~5s to under 1s
- [ ] Faster connection improves signal strength
- [ ] DHCP drains the battery directly
> Energy per cycle is roughly current × awake-time, and the awake time is dominated by the Wi-Fi handshake (scan, DHCP, association) at full radio power. Shrinking that window — by remembering the network details so the chip can rejoin immediately — slashes the most expensive part of every wake. Since the device sleeps cheaply either way, minimizing awake time is the whole game, and Wi-Fi connect is the biggest chunk of it.

Q: The chip sleeps at ~10µA, yet a dev board may last far less than the battery math predicts. Why?
- [ ] The battery math is wrong
- [x] The ~10µA figure is the *chip alone* — a dev board's always-on power LED, USB-serial chip, and voltage regulator can each draw milliamps in sleep, dwarfing the ESP32; real battery products use a custom or low-power board
- [ ] Deep sleep doesn't work on dev boards
- [ ] The USB cable drains current
> Low-power figures describe the bare ESP32, but a typical dev board surrounds it with components that ignore your sleep code: a power LED burning ~5mA continuously alone destroys the budget. "Mind the board, not just the chip" — for years-long battery life you remove or avoid those parasitic draws with a custom PCB or a board designed for low standby (e.g. an Adafruit Feather), so the system, not just the chip, sleeps at microamps.
```

If you remember one thing from Part 8: **battery life is almost entirely about minimizing awake time — deep sleep drops draw from ~200mA to ~10µA (a 20,000× cut), waking is effectively a reboot (persist state in `RTC_DATA_ATTR` memory), and the biggest practical win is connecting to Wi-Fi fast (static IP + cached channel) because the radio is the power hog. Done right, the same battery lasts years instead of a day.**

## Part 9 — Sample Projects

Microcontrollers are learned by building, so here are five complete, escalating projects. Each one introduces a new capability and reinforces the concepts from the parts above; together they cover the techniques behind most real ESP32 work. They're written in Arduino-ESP32 for approachability (Part 3) — port to ESP-IDF or MicroPython as you grow.

### Project 1 — Blink (Hello, Hardware)

The "hello world" of embedded — and not a throwaway: it proves your toolchain, board, and flashing all work, which is the real hurdle on day one. Wire an LED (with a ~330Ω resistor, anode to GPIO, cathode to GND) or use the onboard LED.

```cpp
#define LED 2                          // most dev boards: onboard LED on GPIO2
void setup() { pinMode(LED, OUTPUT); }
void loop() {
  digitalWrite(LED, HIGH); delay(500);
  digitalWrite(LED, LOW);  delay(500);
}
```

**What it teaches:** the edit → compile → flash → observe loop (Part 1), `setup`/`loop` (Part 3), digital output (Part 4). **Level up:** rewrite it with the `millis()` non-blocking pattern (Part 6) so the LED blinks *while* you also read a button — the first real lesson that `delay()` doesn't scale.

### Project 2 — Button-Controlled LED with Debounce & Interrupt

Input meets output. A button toggles an LED on each *press* (not while held) — which forces you to confront floating pins, bounce, and edge-detection.

```cpp
#define BTN 4
#define LED 2
volatile bool toggleReq = false;
unsigned long lastISR = 0;

void IRAM_ATTR onPress() {
  if (millis() - lastISR > 50) {       // debounce inside the ISR (Part 4)
    toggleReq = true;
    lastISR = millis();
  }
}
void setup() {
  pinMode(LED, OUTPUT);
  pinMode(BTN, INPUT_PULLUP);          // pull-up: idle HIGH, pressed LOW (Part 4)
  attachInterrupt(BTN, onPress, FALLING);
}
void loop() {
  if (toggleReq) {
    toggleReq = false;
    digitalWrite(LED, !digitalRead(LED));   // toggle
  }
}
```

**What it teaches:** digital input with pull-ups, debouncing, and the interrupt → flag → handle-in-loop pattern (all Part 4). **Level up:** add PWM (Part 5) so the button cycles through brightness levels instead of just on/off.

### Project 3 — Wi-Fi Weather Station (Sensor → MQTT)

The quintessential IoT project and the one that ties the most together: read a real sensor over a bus, connect to Wi-Fi, and publish readings over MQTT for a dashboard or home-automation system to consume. Uses a **BME280** (temperature/humidity/pressure) over I2C.

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_BME280.h>           // library hides the I2C register details (Part 5)

Adafruit_BME280 bme;                    // I2C sensor at 0x76
WiFiClient net;
PubSubClient mqtt(net);

void connectWiFi() {
  WiFi.begin("MySSID", "password");
  while (WiFi.status() != WL_CONNECTED) delay(300);
}
void connectMQTT() {
  mqtt.setServer("192.168.1.10", 1883);
  while (!mqtt.connected()) mqtt.connect("esp32-weather-01");
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);                   // I2C pins (Part 5)
  bme.begin(0x76);
  connectWiFi();
  connectMQTT();
}
void loop() {
  if (!mqtt.connected()) connectMQTT(); // Wi-Fi/MQTT drop — reconnect (Part 7)
  mqtt.loop();

  char buf[16];
  dtostrf(bme.readTemperature(), 4, 1, buf);
  mqtt.publish("home/weather/temp", buf);
  dtostrf(bme.readHumidity(), 4, 1, buf);
  mqtt.publish("home/weather/humidity", buf);

  delay(30000);                         // every 30s (see Project 4 for the battery version)
}
```

**What it teaches:** I2C sensors via a library (Part 5), Wi-Fi station mode and reconnection (Part 7), and MQTT pub/sub (Part 7) — the backbone of nearly all telemetry IoT. Run **Mosquitto** as the broker and you can watch readings with `mosquitto_sub -t 'home/weather/#'`, or feed them straight into **Home Assistant**. **Level up:** add a small OLED (I2C, same two wires) to show the readings locally.

### Project 4 — Battery-Powered Sensor (Deep Sleep)

Project 3 plugged into the wall and stayed awake — fine for a demo, fatal for a battery. This is the *same* job re-architected for years of battery life: wake, read, publish, sleep. It's Project 3 turned inside out by Part 8's deep-sleep pattern, and the contrast is the whole lesson.

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_BME280.h>

RTC_DATA_ATTR int bootCount = 0;        // survives deep sleep (Part 8)
#define SLEEP_SECONDS 600               // wake every 10 minutes

Adafruit_BME280 bme;
WiFiClient net;
PubSubClient mqtt(net);

void setup() {
  bootCount++;
  Wire.begin(21, 22);
  bme.begin(0x76);
  float temp = bme.readTemperature();   // 1. read FIRST (cheap, do it before the radio)
  float hum  = bme.readHumidity();

  // 2. connect fast — static IP skips DHCP, the biggest awake-time win (Part 8)
  WiFi.config(IPAddress(192,168,1,50), IPAddress(192,168,1,1), IPAddress(255,255,255,0));
  WiFi.begin("MySSID", "password");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) delay(50);

  if (WiFi.status() == WL_CONNECTED) {  // 3. publish (only if connected — don't hang awake)
    mqtt.setServer("192.168.1.10", 1883);
    if (mqtt.connect("esp32-batt-01")) {
      char buf[16];
      dtostrf(temp, 4, 1, buf); mqtt.publish("home/garden/temp", buf);
      dtostrf(hum, 4, 1, buf);  mqtt.publish("home/garden/humidity", buf);
      mqtt.loop(); delay(100);          // let the publish flush before sleeping
    }
  }

  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_SECONDS * 1000000ULL);   // 4. arm timer
  esp_deep_sleep_start();               // 5. ~10µA until the timer fires; setup() restarts on wake
}
void loop() {}                          // never reached
```

**What it teaches:** the deep-sleep architecture (Part 8) — wake-is-a-reboot, `RTC_DATA_ATTR` for persisted state, static IP for fast connect, and the discipline of doing the cheap work before powering the radio and bounding the awake time so a failed connect doesn't drain the battery. **This single restructuring is the difference between a half-day and ~two years on a battery.** **Level up:** wake on a GPIO (a reed switch on a door/window) instead of a timer, so it reports only when something *happens* — near-zero average power.

### Project 5 — Web-Controlled Device (ESP32 as Server)

Flip the direction: instead of the ESP32 pushing data out, it *hosts* a web interface you open from any phone on the network to control it — an LED, a relay, a motor. This is how a huge amount of "smart home" DIY works, and it introduces the ESP32 as an HTTP server with a live channel.

```cpp
#include <WiFi.h>
#include <WebServer.h>
#define RELAY 2

WebServer server(80);

void handleRoot() {
  bool on = digitalRead(RELAY);
  server.send(200, "text/html",
    "<h1>Device Control</h1>"
    "<p>State: " + String(on ? "ON" : "OFF") + "</p>"
    "<a href='/toggle'><button>Toggle</button></a>");
}
void handleToggle() {
  digitalWrite(RELAY, !digitalRead(RELAY));
  server.sendHeader("Location", "/");        // redirect back to the page
  server.send(303);
}

void setup() {
  pinMode(RELAY, OUTPUT);
  WiFi.begin("MySSID", "password");
  while (WiFi.status() != WL_CONNECTED) delay(300);
  Serial.println(WiFi.localIP());             // open this IP in a browser

  server.on("/", handleRoot);
  server.on("/toggle", handleToggle);
  server.begin();
}
void loop() {
  server.handleClient();                      // non-blocking; serve requests as they arrive
}
```

**What it teaches:** the ESP32 as an HTTP *server* (Part 7), serving HTML and handling routes, the inverse of Projects 3–4. Open the printed IP on your phone and you have a control panel. **Level up:** replace HTTP polling with **WebSockets** (the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md)) for a live-updating UI, add the captive-portal **WiFiManager** (Part 7) so credentials aren't hardcoded, and put it behind **TLS** (Part 7) before exposing anything that matters.

### Where to Go From These

These five — output, input, telemetry-out, battery/sleep, control-in — are the primitives almost every ESP32 project recombines. Natural next builds that mix them: a **plant monitor** (Project 4 + a soil-moisture ADC read, Part 5), a **BLE beacon or fitness sensor** (Part 7's BLE instead of Wi-Fi), an **e-paper dashboard** (Project 3's data onto an SPI e-ink display), a **camera** project on an **ESP32-CAM** board (the S3's ML acceleration shines here), or a **Matter** smart-home device on a **C6** (Part 2) that pairs with Apple/Google/Amazon ecosystems natively.

If you remember one thing from Part 9: **build these in order — each adds one capability (digital out → digital in → sensor+Wi-Fi+MQTT → deep-sleep battery → web server) and together they're the vocabulary of real ESP32 work. The jump from Project 3 to Project 4 (the same sensor, re-architected for deep sleep) is the most important lesson: the *same job* becomes a multi-year battery device purely through power discipline.**

---

## Part 10 — Production & Going Further

The gap between "it works on my desk" and "I shipped a thousand of these" is real, and it's where embedded gets serious. This closing part covers what changes when an ESP32 project becomes a product, plus the debugging and learning paths to take you there.

### Debugging Beyond `printf`

Serial `printf` (Part 1) carries you a long way, but production debugging needs more:

- **Read the crash, don't guess.** When the ESP32 panics it prints a **backtrace** of hex addresses and reboots. Feed that through `addr2line` (or PlatformIO's monitor filter / `idf.py monitor`) to turn the addresses into file/line numbers — this turns "it just reboots" into "null deref at sensor.cpp:42."
- **Know the reset reasons.** `esp_reset_reason()` tells you *why* the chip rebooted — a panic, a **brownout** (voltage dipped — often an underpowered USB port or a Wi-Fi current spike a weak supply can't deliver, a top real-world gotcha), a **watchdog** timeout (a task hogged the CPU and the watchdog killed it — Part 6), or a clean deep-sleep wake.
- **Watch the heap.** `ESP.getFreeHeap()` over time catches the slow memory leak that crashes the device after three days of uptime — the same leak-hunting discipline as the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md), with far less margin.
- **Real JTAG debugging** (breakpoints, single-stepping, variable inspection) exists via the built-in JTAG on S3/C3 over USB, with GDB and the IDF — worth setting up once you outgrow `printf`.

### Over-the-Air Updates (OTA)

A device on a shelf (or a thousand in the field) can't be reflashed over USB. **OTA updates** let firmware update itself over Wi-Fi — the ESP32 has dual app partitions, downloads the new firmware to the inactive one, verifies it, and reboots into it (with rollback if the new image fails to boot). This is **non-negotiable for any real product**: it's how you ship bug fixes and — critically — **security patches** (Part 7). Design for OTA from day one; retrofitting it is painful. The deployment thinking parallels the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md)'s staged-rollout discussion — roll new firmware to a few devices, watch for boot failures, then ramp.

### Security Hardening for Production

Beyond Part 7's TLS-and-secrets baseline, shipping a product adds two hardware features:

- **Secure Boot** — the chip cryptographically verifies the firmware signature at boot, so it won't run firmware you didn't sign. Stops an attacker from flashing malicious code.
- **Flash Encryption** — the firmware and data in flash are encrypted with a key fused into the chip, so an attacker who desolders the flash and reads it gets ciphertext. Stops firmware/IP theft and secret extraction.

Together they're what separate a hobby gadget from a defensible product. They're irreversible (one-time fuses) and easy to brick yourself with — read the docs carefully and test on a sacrificial board first.

### Manufacturing & Cost Realities

Two things that surprise software people scaling to hardware: **per-device provisioning** (each unit needs unique credentials/certs flashed at the factory — you don't ship a thousand devices with the same key, per Part 7), and the move **from dev board to custom PCB** (the $10 DevKitC is for prototyping; a product uses the bare WROOM/WROVER *module*, ~$2–4, on your own board with only the components you need — which is also how you finally hit Part 8's true low-power numbers by dropping the always-on dev-board LED and USB chip).

### Where the ESP32 Fits, Honestly

A closing perspective, since the guide opened by contrast with the Pi. Choose the **ESP32** when you need **cheap, low-power, real-time, single-purpose** hardware control with wireless — a sensor, a controller, a connected gadget; it's $2–10, sleeps for years, boots instantly, and talks directly to pins. Choose a **Raspberry Pi** (or other Linux SBC) when you need an **operating system, heavy computation, a real filesystem, a display/GUI, cameras with vision processing, or to run existing Linux software** — it's a computer. The two are complements, not competitors, and many real systems use both: ESP32 nodes as the cheap sleeping sensors at the edges, a Pi (or a cloud backend) as the always-on hub that collects from them over MQTT. Knowing which is which — the very first lesson of Part 1 — is the most valuable thing this guide can leave you with.

### Going Further

- **Graduate to ESP-IDF** (Part 3) for the full chip — power, security, performance.
- **Explore the variants** (Part 2): S3 for camera/ML, C6 for Matter, C3 for cost.
- **Build the "level up" extensions** in Part 9 — they're where the real learning compounds.
- **Read the [ESP-IDF docs](https://docs.espressif.com/projects/esp-idf/en/latest/)** cover to cover for any peripheral you use seriously; they're excellent.
- **Pair it with the rest of the repo:** [Networking](NETWORKING_FUNDAMENTALS.md) for the TCP/IP your device speaks, [Cryptography](CRYPTO_FUNDAMENTALS.md) and [Auth](AUTH_STUDY_GUIDE.md) for securing it, [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) for live UIs, [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) for the fleet behind it, and the upcoming Raspberry Pi guide for its always-on counterpart.

If you remember one thing from Part 10: **shipping a product means OTA updates (for security patches — design them in from day one), Secure Boot + Flash Encryption, per-device provisioning, and moving from dev board to a custom PCB with the bare module — and the ESP32's place is cheap, low-power, real-time wireless hardware control, complementing rather than competing with a Linux SBC like the Pi.**

---

That's the guide. From here the highest-leverage next step is the one that's true of all hardware: **buy a $6 board and build Project 1 tonight.** The toolchain hurdle is the real barrier, and it falls the moment your first LED blinks; everything after that is recombination. Then build Projects 2 through 5 in order — by the battery-sensor project you'll understand why a microcontroller is a fundamentally different machine than the computer you wrote this on, and why that difference is exactly what makes a sensor that lives for years on a coin cell possible. The chip is cheap, the radios are free, and the physical world is waiting to be measured and controlled — which is the particular joy of embedded that no amount of cloud software replicates.

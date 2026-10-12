# Isolated P105 power, storage and USB components

These are concrete Linux-C source components for review and offline testing.
The normal Cascadia build does not descend into this directory, source these
Kconfig fragments, create their DT nodes or install their callbacks. They have
no supplied hardware backend or enabled configuration. No working physical
charging, USB host or writable NAND result is claimed.

| Component | Implemented | Deliberately still required |
|---|---|---|
| `p105-current` | Actual regmap/platform/IRQ-domain/power_supply driver; checked current masks and readback; epoch-bound producer contract; fault latch; inhibit on removal/sleep | Coherent source/gauge producer, exclusive MFD event ownership, analog retention/CV/termination/protection evidence and physical tests |
| `p105-ppn` | Single SLC-page program/block erase orchestration; checked complete non-AES CDMA descriptor plans; per-controller sequencer preparation; owned DMA leases and cancellation; no blind replay | Actual MMIO/CDMA/sequencer binding, exclusive SLC blocks/geometry/BBT, completion and power-cut guarantees; no MTD writer exists |
| `p105-usb-client` | Checked two-phase removable-port clock/PHY membership lifecycle; active/standby/off; detach epochs and retained fault ownership | Real shared-PHY/clock provider, completed EHCI-port transition/quiesce, accessory identity/mux and verified external power |
| `p105-usb-registers` | Checked shared clock-mask aggregation and real regmap tuning/reset primitives; bounded polls; retained errors and owner epochs | Complete actual platform clock graph, real shared power lease/controller quiesce, accessory mux/VBUS and physical validation |
| `p105-usb-role` | Actual USB 51/53 setup decoder, exact lengths/endian/masks, default-denied policy callbacks | Real gadget function/completion and authorized accessory policy; the known original userspace producer is CarPlay, not a Camera Adapter proof |

The transport-only PPN return explicitly keeps `durability_unknown=true` even
when the original successful register/DMA sequence matches. Do not translate it
to successful MTD write/fsync/UBI commit. Its failed DMA cancellation retains
the relevant leases/buffers; no reset, erase-all or EF3380 acknowledgement is
supplied. Synthetic geometry and owned ranges are test inputs, not discovered
target hardware facts.

The USB-client callback contract is idempotent membership of **one owned
client**, not blind generic PHY power references. External Port1 uses the
original EHCI/OHCI route; its standby state retains host membership. A scheduled
transition is not a completed controller result. An old attach epoch cannot be
silently replaced to release another device's resources.

The current-only driver preserves unknown analog bytes. It supplies no CV,
termination, OTP or watchdog initialization, and refuses probe without its
explicit experiment assertions and a real producer. The epoch/freshness checks
are software invariants, not proof of physical battery safety.

## Verification

`python3 scripts/test-offline.py` includes actual-C component tests. Hosted C
builds use fake callbacks only, with UBSan where applicable. Golden fixtures
record semantic outputs of separately executed, hash-pinned original ARM code
with synthetic provider/MMIO responses. They contain no firmware instructions
or device dumps. Normal kernel source/config is not modified by these tests.

ARMv7 object compilation against the actual patched Linux 6.12 generated
headers passed for the current driver/core, PPN engine, CDMA/sequencer planners and all three USB components.
An object compile checks APIs and target code generation; it does not execute
the Linux driver framework or establish a hardware binding.

The PPN successful trace can be regenerated from the user's own exact official
12H321 extraction using `tools/nand/emulate-ppn-program.py --kernelcache FILE
--output NEW_JSON`. This runs only in Unicorn, with bounded original code and
strict synthetic MMIO/DMA/helper hooks. Both source input and output are regular
files. It creates no device transport and performs no real NAND operation.

See each component's `EVIDENCE.md` for the source addresses, checked boundaries,
and original staging provenance. Legacy staging paths identify local research
inputs; the portable tests at `tests/test-experimental-*.py` are the exported
reproduction entry points. Do not copy a staged component into the runtime
kernel merely because its offline tests pass.

# Concrete P105 solution paths after the deeper firmware comparison

2026-10-12. Official 8.4.1/12H321 remains the build firmware. Official
9.3.5/13G36 is an additional offline research input, not a replacement iBEC or
boot recipe. All findings here are source/emulator/build evidence. No iPad
access, NAND operation or host service/network modification occurred.

## Charging

There is now an actual isolated Linux-C current controller in
[`experiments/p105-current`](../../experiments/p105-current/). It uses regmap,
a central 72-event IRQ domain and power_supply, checks masked writes/readback,
preserves inherited current ceilings, and latches failures. Suspend and removal
inhibit without silently restoring the old permission on resume. No DT node or
default build hook enables it.

The physical CV mapping was narrowed rather than guessed: actual 12H321
source+0x9c→+0xa0→PMU+0x380 ends in AppleDialogPMU's `debug` dictionary handler.
Absent `debug`, that forwarding performs no PMU bus operation. Thus the owner's
`ChargeLimitVoltage` property is a software cutoff, not a demonstrated physical
CV setter. The freshly derived 13G36 backend adds an optional
`AppleForceResetEndOfCharge` path using the known input-control masks; it still
does not establish a voltage-programming API.

Both official ADTs bind PMU IRQ to GPIO pin19, Apple flags1. Original GPIO-IC
initialization translates it to mode3, matching Linux level-low; the GPIO
controller's parent is AIC119. The current normal MFD has no central PMU IRQ
owner. Reading all event banks outside an exclusive owner can consume events,
so the experimental charger cannot coexist with another independent event reader.

The normal HDQ word reader is corrected to high–low–high, with bounded retry,
transport errors and valid signed `0xffff` handling. The actual Apple reader
and [TI-authored Linux HDQ driver](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/power/supply/bq27xxx_battery_hdq.c)
support this coherence mechanism. A new consumer snapshot/lifetime API remains
separate research. A power_supply reference alone does not pin its driver's
devm context through removal; managed links must target the actual producer.

A charger still needs completed USB/accessory configuration combined with
fresh bounded gauge measurements. A successfully completed standard USB
configuration grants the advertised descriptor budget; an unsupported current
control callback is a separate missing hardware hook. The current cdc2 gadget
advertises0mA, and no such protocol observation replaces analog validation. `vbus_draw` or gadget state alone is insufficient
to establish a completed configuration. The generic S5L PHY does not supply the
legacy DWC2 current-grant path. No positive permission is synthesized from an uncompleted
request, stale reading or failed request. Analog retention across the exact
boot handoff and physical protection remain unverified.

The prototype's1000mA enable threshold is a conservative experiment restriction,
not a proven physical charging minimum. The original consumer compares an
accumulated owner value; it does not establish that500mA cannot trickle-charge.

## Linux-owned NAND

The concrete path is exclusive PPN SLC blocks → writable MTD → UBI → UBIFS,
not a writable reconstruction of Apple's FTL. The new
[`p105-ppn` component](../../experiments/p105-ppn/) executes the reconstructed
single-page/block protocol through unbound callbacks, bounds physical addresses,
holds unique DMA leases and propagates completion/cancel errors. A frozen clock
cannot leave its polling loop unbounded. Original firmware's conditional DMA
timeout success is intentionally not copied.

Single-page success matches the independently emulated original IOP register
and DMA sequence on both buses. EF3380's transport and original conditional
callers are traced, but its device acknowledgement/idempotency effect remains
unestablished. The engine snapshots error lists after DMA quiescence and does
not send that unknown acknowledgement or replay a partially completed program.
It reports transport completion with unknown durability and exposes no MTD writer.

Two additional C components now prepare real non-AES CDMA chains and per-controller
sequencer upload plans. Complete single batches match96 original DMA traces;
25 fresh sequencer cases match original arithmetic. No Apple microcode is
included. The original clock field is hclk/1000 in kHz; synthetic fixture
clocks are arithmetic stress inputs. These preparers do not submit DMA or
claim durable flash completion.

The filesystem layer is already concrete: an Alpine UBIFS/UBI pair has been
generated and checked locally. See [the offline SLC rootfs builder](p105-linux-owned-rootfs.md).
The profile's 16KiB I/O, 128-page/2MiB SLC block and 64-LEB reservation are
explicit synthetic assumptions. Actual chip capacity/mode/exclusivity, controller
binding/BBT and crash guarantees must precede writable installation. Keeping
iOS requires its global FTL; giving it up requires an independent Pico/BootROM
boot path, which this user's present setup lacks.

## External USB host and power

The README's old claim of absent EHCI external ports was directly contradicted
by **both** official ADTs. Each declares external EHCIport1/type2/mask0x30002 and
OHCI0port1/type2/mask0x30006, separately from WLAN's HSIC Port3. The exact trees
can be checked with `scripts/check-external-usb-ports.py`. A DWC2 forced-host
build remains an isolated experiment and does not identify the Lightning route.

[`p105-usb-client`](../../experiments/p105-usb-client/) implements the actual
two-phase port-client lifetime in C, including standby retention, owned-error
state and detach epochs. It requires the completed controller transition and
an idempotent shared PHY/clock backend; it does not reset the WLAN block or
pretend a generic power-off proves resource release.

Apple's [powered Camera Adapter support](https://support.apple.com/en-us/111811)
documents an external Lightning power input supplying the iOS device and USB
peripheral. Its [mini1 compatibility filter](https://www.apple.com/shop/ipad/accessories/chargers-adapters/ipad-mini-1st-generation-usb-3)
lists this adapter, with iOS9.3+ required. This provides a manufacturer-backed
power topology for eventual testing without inventing an internal iPad5V boost.
It does not prove Linux enumeration, PMU charging or a particular hub's isolation.

The 13G36 vendor51/53 transport is now implemented as a separate default-denied
[`p105-usb-role` parser](../../experiments/p105-usb-role/). However, the actual
`iaptransportd` caller uses `isCarPlayAllowed`, setting value-mask0/1 and
index-mask0. It is a positive CarPlay/Stark finding, not a Camera Adapter
handshake. Actual iOS gadget registration also includes vendor HID descriptors.
The camera path must not be reduced to this one vendor hook.

The direct exported `IOAccessoryManagerEnableUSBHostMode` API chooses mode2,
which maps through the actual 13G36 mode table to USBd control0x25; vendor51
chooses mode3/control5. Original USBd flag0x20 changes the software cable's
`USBDeviceNeedsAuthentication` classification, retaining `USBDevice` instead.
That is not proof of physical authentication or power permission. Mode, ID,
data mux, clock/PHY and electrical supply are separate verified boundaries.

## Review and physical limits

The components are compiled against actual Linux6.12 ARM headers and tested
against original-code semantic fixtures with synthetic providers. They are
reviewable source foundations, not enabled features or hardware-safe boot
artifacts. The normal kernel keeps NAND read-only, gadget peripheral mode and
the existing WLAN setup. Any device validation still requires explicit user
approval; these local changes grant none.

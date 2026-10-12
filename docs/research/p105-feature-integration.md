# Concrete implementation and integration order

The research branch supplies code for the requested features and fixes actual
runtime errors. Charging, writable NAND and the external host connector have
not been activated or hardware-tested. Every new experiment remains outside
normal patch/DT activation. This document identifies the implementation path
and the remaining evidence needed to join its components.

| Feature | Implemented software | Next integration evidence |
| --- | --- | --- |
| Charging from configured USB2 | Checked current core, owned completed-EP0/HDQ producer, drained invalidation notifications, opt-in bounded100/500mA plans, optional CDC declaration | Final analog/protection state after boot; calibrated source/battery readings; physical detach/suspend/fault cutoff |
| Charging from a wall charger | Original source/current policy and boot PMU helpers investigated | Actual owned DCP/Apple-divider source detector and removal/fault lifecycle; a USB configuration descriptor alone cannot detect a brick |
| Linux-owned NAND | PPN engine, CDMA/sequencer plans, completion/lease model, BBT transactions/codec, offline UBIFS/UBI files | Exclusive boot/IOP/CDMA handoff, real stop/drain witnesses, geometry/SLC qualification, writable backend and power-cut durability |
| External USB host | Native parent clock broker, port memberships, checked PHY power/tuning/reset, controller mux/reset, source-backed external Port1 route | Join all writers/owners, preserve WLAN Port3, authenticate/route the actual adapter and verify protected VBUS |

## Charging path

Stock CDC2 declares0mA; its completed configuration therefore still yields a
zero allowance in the owned source reader. The isolated gadget candidate accepts
only0/100/500mA, defaults to0 and validates before registering/binding. Its actual
libcomposite/EP0 tests establish encoded descriptor bytes0/50/250 and matching
completed USB2 budgets. Positive profiles reject non-USB2 UDC capability.
This patch is deliberately unsourced in the normal build.

The current candidate independently defaults off. With its further USB2 opt-in,
the current plan is bounded by the declared input and floors charge codes to
40mA: nominal100/500mA plans can request at most80/480mA. The real register
ceiling can reduce them further; the retained zero thermal slots remain zero.
These numbers are software current codes, not measurements or promised net
battery charge. Device consumption shares the available input power.

The software chain is descriptor → successful configuration/status cookie →
owned source/gauge tuple → checked current transaction. Pending/failed EP0,
disconnect, suspend, stale epochs and faulty status cannot grant a plan.
Source notifications invalidate and queue work; they do not establish an
electrical response deadline or autonomous battery protection.

The boot chain itself contains PMU initialization and unchecked helper errors.
An earlier iOS charging state cannot simply be assumed retained. Final CV,
termination, autonomous fault/temperature protection and safe calibration must
be independently established after all boot stages. A wall charger additionally
needs its own actual source detector; it may never complete a USB configuration.

Reproduction: `tests/test-experimental-gadget-maxpower.py`,
`test-experimental-source-provider.py`, `test-experimental-source-notify.py`,
`test-experimental-current-small.py` and the retained current tests. These are
host-only tests with explicit mocks, not activation commands.

## NAND path

The intended architecture gives Linux exclusive flash ownership and uses a
qualified SLC MTD aperture with UBI/UBIFS. It does not extend the read-only iOS
FTL reconstruction into a writable coexistence scheme. Erasing iOS would also
remove the existing kDFU entry; an independently demonstrated Pico/BootROM boot
and recovery path must precede that destructive option. This unit has no Pico
and no approved NAND operation.

The engine binds each data/OOB DMA lease to controller, epoch, transfer and
channel identity. Successful transport actions advance to a separate fence;
unknown errors retain ownership. BBT body/manifest publication additionally
requires external durable and quiesced receipts and identity-bound blank
witnesses. Its serializer never manufactures those receipts.

Actual IOP sleep replies precede callbacks/CPU sleep. The native stop helper
ignores provider errors, and its software running flag is not a hardware check.
IOP gate107c, CDMA gate1078 and reset1058 are separate resources. The actual
native graph can release IOP while CDMA remains active. The next backend must
independently halt/adopt prior owners and stop/drain each owned DMA generation,
including late interrupts, before leasing or freeing its buffers.

After that source-backed backend exists, geometry/SLC mode, address-bound final
PPN status and power-loss behavior still require approved hardware validation.
The existing local UBIFS/UBI images use explicit synthetic geometry; this
device's capacity and usable eraseblock map have not been qualified.

Reproduction: `tests/test-experimental-ppn*.py` and
`tests/test-ubifs-image.py`. See the [completion contract](../../experiments/p105-ppn/COMPLETION.md)
and [actual IOP handoff](p105-iop-handoff.md).

## External USB path

The source-backed external route is EHCI removable Port1, with OHCI0 companion
for direct low/full-speed devices. The existing Linux EHCI instance also owns
WLAN HSIC Port3. Forcing DWC2 host alone does not reproduce this route. A first
qualified high-speed device or high-speed hub with TT avoids requiring the
direct-FS companion, but has not been tested on this iPad.

The actual clock graph and true clkG bridge now have executable source proofs.
The broker retains protected foreign/global references and uses ordered
clock/gate transitions. All global owners and bypassing writers must join its
sleepable owner lock: the normal PHY's direct PMGR writes currently prevent
that claim. A permanently pinned-parent design must still exclude such writers;
reading an enabled bit cannot recover old counts or establish lifetime ownership.

The clock broker, port membership, PHY power/tune/reset and controller mux/reset
must be joined under one epoch/owner lifecycle, with UDC and every shared EHCI/
WLAN client quiesced at disruptive transitions. Partial errors retain their
pending disposition and prohibit blind retries. The normal WLAN setup has not
been replaced by these isolated components.

Accessory LDO5, Tristar VBUS sensing, mux selection and EHCI PORT_POWER each
have different source evidence. None alone identifies a protected5V source.
The actual adapter identity, rail/conversion path, current limit, reverse-feed
isolation and detach/fault handling remain required before supplying the bus.
An externally powered adapter is a topology to qualify, not a demonstrated
Linux workaround. Native5V output is not established by this research.

Reproduction: `tests/test-experimental-native-clock.py`,
`tests/test-pmgr-clkg.py`, the USB power/reset/controller tests and
`tests/test-experimental-usb-provider-loss.py`.

No hardware permission, normal feature activation or publication follows from
these source tests. The local PR package makes the changes reviewable before
any separate device-validation decision.

## Newly implemented transport boundaries

[Wall classification](../../experiments/p105-wall-source/EVIDENCE.md) and [checked ADC6 conversion](../../experiments/p105-adc6/EVIDENCE.md) now provide actual Linux-C source building blocks. Their callers must implement one exclusive Tristar/all-ADC owner with checked restoration and coherent attachment epoch; the wall measurement receives raw conversion results and never grants a current budget itself. UNKNOWN ADC state quarantines users even after a successful zero-stop readback. Charger CV/termination/protection qualification remains separate.

[CDMA cancellation](../../experiments/p105-ppn/CANCELLATION.md) now supplies bounded checked transport. Its successful result remains WAIT_FENCE; only a separately qualified backend can prove no future memory accesses and drained native/Linux IRQ callbacks before any memory release. Masking an IRQ does not erase a callback already captured by the original dispatcher.

[Checked bank0 transport](../../experiments/p105-bank0/EVIDENCE.md) now selects page0 only after an exclusive ALL-PMU lease, binds the cache to that owner generation, and quarantines uncertain selector/data transfers. A real parent must own every GPIO/RTC/ADC/charger/event consumer and invalidate on ownership gaps before any child can use this primitive. It is not a drop-in regmap replacement and does not prove analog protection.

[Remote-signature exchange](../../experiments/p105-authcp-aid/AUTHENTICATION.md) now produces bounded version2/3 nonce packets, checks actual response semantics, retains failed pending transactions and exposes only unverified bytes. Real IDbus transport, fresh nonce generation, matching certificate policy/public verification and accessory identity precede any role or electrical grant. No host-private signing operation is needed in this audited exchange/verification path; other iAP modes are outside that conclusion.

[Actual selected kDFU sleep](p105-kdfu-sleep-boundary.md) and [FMI client retirement](p105-fmi-client-retirement.md) close concrete software edges, including final-client release before power acknowledgment. They still do not establish inherited IOP/CDMA no-future-access or IRQ drain; no MTD writer is enabled.

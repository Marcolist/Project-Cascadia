# Research notes

Working notes from the bring-up, kept verbatim rather than tidied — the failed
attempts are the useful part.

Several of these originate from **teutekeune/iBSSloader** and were extended
during Cascadia work (notably `p105-smp-bringup.md`, which carries the lab
results of ~20 failed attempts at waking cpu1). Both projects are GPL-2.0.

## P105 power, storage and USB research

The following additional notes record offline work on iPad2,5 / p105ap. They separate driver
fixes, experimental build profiles and firmware evidence. Nothing here is
evidence of a successful physical charging, external USB-host or writable NAND
test. The normal boot procedure remains [QUICKSTART](../QUICKSTART.md).

| Area | Implemented and tested offline | Still unresolved |
| --- | --- | --- |
| Battery/PMU | Atomic HDQ cache, valid percentage range, break failure handling, discharge status, GPIO errors, removal of event-consuming probe dump | Complete charger initialization, battery/fault protection, voltage/termination policy and hardware verification |
| NAND | Read progress/ECC errors, explicit read-only MEMREAD backend with exact sysfs/device identity, strict metadata/cache checks, reduced mapper memory, NBD bounds/setup/worker cleanup, pidfd control and generation-bound System readiness | Actual process/sysfs hardware integration, target capacity/performance, writable PPN/FTL and Linux-owned storage |
| USB | Host-only build/link, bounded ADT parser, PHY power-error handling, two-bit GPIO selector masks, isolated HID/storage profile | Partial-power-off/core-count resume recovery, complete connector routing, external 5 V VBUS/protection, role transitions and real peripherals |

Charging evidence:

- [Battery percentage validation](p105-battery-validation.md)
- [D1946 current and battery policy](p105-charging.md)
- [PMU Wake/Sleep/Quiesce](p105-pmu-lifecycle.md)
- [Source-event notifications](p105-source-events.md)
- [Input-current backoff, stored cap and deadline](p105-source-backoff.md)
- [Actual zero-input apply and communication-failure boundaries](p105-zero-input.md)
- [Actual source-budget construction and charger dispatch](p105-input-dispatch.md)
- [Actual voltage/clamp owners and permanently blocked charging contract](p105-charger-evidence-contract.md)
- [Charging status and blocked recovery paths](p105-charge-status.md)
- [Concrete charger guard-field owners](p105-charge-guard-ownership.md)
- [System watchdog and charger protection distinction](p105-pmu-watchdog.md)
- [ADC identities and scaling with acquisition blocked](p105-d1946-adc.md)
- [ADC completion, IRQ and quiesce with fake I/O](p105-d1946-adc-lifecycle.md)
- [ARM clock interval conversion with fake frequency and time](p105-clock-intervals.md)
- [USB gadget budget integration gap](p105-usb-charge-budget.md)
- [Host current-offset request receiver](p105-usb-current-request.md)

Storage and USB evidence:

- [Read-only Linux storage and NBD limits](p105-linux-storage.md)
- [MLC media type and strict read-only compatibility](p105-mtd-media-type.md)
- [PPN error-list fields and unresolved AP/IOP ownership](p105-ppn-error-list-evidence.md)
- [Strict synthetic error-list decoder and independent oracle](p105-ppn-synthetic-decoder.md)
- [Existing NAND architecture](p105-nand.md)
- [USB host/PHY evidence](p105-usb-host.md)
- [DWC2 versus Apple EHCI/OHCI controller boundaries](p105-usb-controller-boundaries.md)
- [Lightning accessory-side voltage conversion and missing wiring](lightning-accessory-conversion.md)
- [PHY error-path assumptions](p105-usb-phy-errors.md)
- [Reproduced partial-off/Core-count gap and shared lifecycle](p105-usb-shared-lifecycle.md)
- [Temporary compensation policy and actual USB consumer limits](p105-usb-poweroff-policy.md)
- [Actual Apple shared-PHY client arbitration and controller ownership](p105-usb-phy-ownership.md)
- [EHCI/OHCI controller and port power](p105-usb-ehci.md)
- [THS7383 accessory routing and orientation](p105-tristar-routing.md)
- [Accessory rail callbacks and ID-derived voltage](p105-accessory-power.md)
- [Accessory switch GPIO descriptor and simulated provider](p105-accessory-gpio.md)
- [SoC GPIO mux-mask comparison and remaining policy differences](p105-soc-gpio-masks.md)
- [VBUS presence sensing and the missing 5 V provider](p105-vbus-presence.md)

Run `python3 scripts/test-offline.py` from the repository root. It runs all
`tests/test*.py` entry points, including names with hyphens. C fixtures use a
native compiler and sanitizers; relevant integration fixtures also need the
pinned local Linux v6.12 source. Firmware experiments require Unicorn and a
separately obtained official p105 12H321 kernelcache. Each experiment validates
its SHA-256 before using fixed addresses. Missing prerequisites are explicit
skips, and skips do not establish correctness.

Instruction tests execute selected original code against fake RAM, PMU I/O or
provider callbacks. Their reports name the mocks; a software budget, routing
byte or PORTSC power bit does not prove an electrical voltage/current. The
firmware under study is iOS 8.4.1, and fixed addresses must not be transferred
to another iOS build. No firmware binaries, keys or real device dumps belong
in the source repository.

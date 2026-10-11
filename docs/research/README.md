# P105 power, storage and USB research

This directory records offline work on iPad2,5 / p105ap. It separates driver
fixes, experimental build profiles and firmware evidence. Nothing here is
evidence of a successful physical charging, external USB-host or writable NAND
test. The normal boot procedure remains [QUICKSTART](../QUICKSTART.md).

| Area | Implemented and tested offline | Still unresolved |
| --- | --- | --- |
| Battery/PMU | Atomic HDQ cache, break failure handling, discharge status, GPIO errors, removal of event-consuming probe dump | Complete charger initialization, battery/fault protection, voltage/termination policy and hardware verification |
| NAND | Read progress/ECC errors, explicit read-only MEMREAD backend, strict metadata/cache checks, reduced mapper memory, NBD bounds/setup/worker cleanup | Actual target capacity/performance, shell PID control, writable PPN/FTL and Linux-owned storage |
| USB | Host-only build/link, bounded ADT parser, PHY power-error handling, isolated HID/storage profile | Complete connector routing, external 5 V VBUS/protection, role transitions and real peripherals |

Charging evidence:

- [D1946 current and battery policy](p105-charging.md)
- [PMU Wake/Sleep/Quiesce](p105-pmu-lifecycle.md)
- [Source-event notifications](p105-source-events.md)
- [USB gadget budget integration gap](p105-usb-charge-budget.md)
- [Host current-offset request receiver](p105-usb-current-request.md)

Storage and USB evidence:

- [Read-only Linux storage and NBD limits](p105-linux-storage.md)
- [Existing NAND architecture](p105-nand.md)
- [USB host/PHY evidence](p105-usb-host.md)
- [PHY error-path assumptions](p105-usb-phy-errors.md)
- [EHCI/OHCI controller and port power](p105-usb-ehci.md)
- [THS7383 accessory routing and orientation](p105-tristar-routing.md)
- [Accessory rail callbacks and ID-derived voltage](p105-accessory-power.md)

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

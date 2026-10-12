# Isolated Linux source/gauge provider candidate

This group supplies actual Linux C APIs for the missing USB-budget and bounded
battery-sample producer. It is not installed, registered, wired to DT, or enabled
in the normal build. Both new Kconfig options default to `n`. No module was
loaded; no USB transfer, PMU access, gauge transaction, or hardware operation was
performed. The C tests replace transport and kernel infrastructure with explicit
fakes and run on the host.

This is a concrete producer component, not a working or physically validated
charger. `p105-combined-provider.c` implements the existing
`d1946_current_provider` callbacks using owned DWC2 and HDQ reader handles.
The remaining consumer integration is described below.

## USB protocol budget is distinct from physical charging

Primary source is Linux 6.12 commit
`adc218676eef25575469234709c2d87185ca223a`, plus the reviewed Cascadia working
patches. `source-provenance.json` records the exact original working source and
candidate hashes.

* [libcomposite set_config and descriptor encoding](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/usb/gadget/composite.c):
  `set_config()` requests the descriptor's nominal current and clips USB2 to
  500 mA. Its successful result and matching EP0 status completion establish a
  completed USB configuration. The early `gadget->state=CONFIGURED` assignment
  alone is insufficient; `set_alt()` can fail afterward or delay status.
* [UDC core draw callback and gadget unbind](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/usb/gadget/udc/core.c):
  `usb_gadget_vbus_draw()` updates `gadget->mA` only when its callback succeeds.
  That hardware callback's error does not undo a successfully completed USB
  configuration or its protocol allowance.
* [DWC2 gadget controller](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/usb/dwc2/gadget.c):
  the existing `vbus_draw` callback forwards through legacy `uphy`. S5L's generic
  PHY leaves that pointer absent, so the hardware-current hook returns
  `-ENOTSUPP`. The observer captures the request before this unchanged return.

The source reader supports only a fixed-peripheral controller with the actual
builtin `composite_setup` function, connected/full-speed or high-speed, awake,
and a completed configuration with an observed draw request. It checks these
fields under the controller lock and copies the controller-owned observation.
It never consults or dereferences a freed composite device/configuration.

It reports `min(completed_draw_request_ma, 500) * 1000` microamps as a **USB2
protocol allowance**. This is not measured consumption, a VBUS voltage reading,
a charger handshake, or full charging permission. No Apple accessory budget is
invented. An external supply/accessory producer remains a separate API.

Cascadia's current CDC2 configuration is self-powered with `MaxPower=0`; a
completed configuration therefore returns an online source with **0 microamps**
allowance. The tests' 100/500 mA configurations are explicit alternate descriptor
fixtures exercised through actual `set_config()`. This group never changes the
shipped descriptor. It cannot draw 500 mA merely because the cable is present.

The p105 ADT value `min-charge-capable-current=1000` is also not a universal
minimum input-current requirement. Actual 12H321 charger function `0x804c40ac`
and accumulator `0x804c4168` compare it against sums of client metadata and set
policy flags, with a separate 300-unit comparison. The private actual-instruction
fixtures in `../min-current-scope` show a 500-unit total setting those flags, not
a PMU disable or a universal ban on trickle charging. The current-only experiment's
1000 mA activation restriction is conservative prototype policy; the producer
correctly reports an available USB2 allowance up to 500 mA independently of that
restriction. Full charging eligibility still needs its own verified policy.

## Lifetime and invalidation

`p105_dwc2_source_open()` is a consumer-probe API. It adds a managed device link
to the **actual DWC2 platform device**, checks the supplier/link state before
reading driver data, compares the actual platform driver address, and owns device
and module references. It does not borrow a class-device context or manually
remove a managed link. Validation is nonblocking: controller and observer locks
use trylock; contention denies validity.

The separately reviewed HDQ-v3 implementation is copied byte-for-byte as
`apple-hdq-battery.c` (SHA256 `c2177dda1c9b877c7660468679e207f05c39588b66f5ce089b507e67c998995c`).
Its opaque reader owns a managed link to the actual gauge platform supplier,
module/device/supply references, and a bounded atomic cache publication. Its
sample is a sequential read interval, not simultaneous measurements. A successful
burst is not independent proof of battery presence or physical calibration.
No gauge register write command is introduced.

The combined constructor owns both readers and its callback-code module. During
snapshot it captures the source before and after the actual gauge snapshot,
rejects an intervening source epoch/configuration/budget change, validates both
reader tokens, and publishes one combined serial. Expiry is the earlier of the
250 ms source lease and 1 s gauge deadline. Age starts at the gauge burst's start,
not its final completion. Any failed refresh invalidates the previously published
tuple and leaves the caller's output unchanged. Validation checks the entire
published tuple, both live producer tokens and the serial again after validating
those tokens. Old serials cannot be made valid by a later successful refresh.

Reset, disconnect, suspend, explicit role change and remove invalidate the actual
controller observation. Source capture additionally rejects a stopped/unbound,
host/dual-role, suspended, low-level-disabled or unknown-speed controller. It does
not assert instantaneous detection of a physical cable transition before the
controller reports it. Resume does not re-create an earlier configuration fact.

The actual UDC unbind path calls `usb_gadget_disconnect_locked()` and disables
async callbacks, then synchronizes the gadget IRQ before calling gadget `unbind()`;
DWC2 disconnect invalidates the observer. It subsequently calls
`dwc2_hsotg_udc_stop()`, which clears `hsotg->driver` and speed under
`hsotg->lock`. Source capture holds that same lock when reading the gadget driver
function pointer. It does not follow composite private data, freed in `unbind()`.
The gadget driver's unregister caller must retain its driver structure until the
synchronous unregister path returns; this existing UDC contract is not replaced.

Consumer removal/probe-error paths must stop and drain **all** snapshot/validation
users before closing either handle, close before returning to the driver core,
and never call a reader after close. Managed links preserve supplier ownership
until consumer teardown completes; device references alone do not preserve a
supplier's devm context. The tests verify rejection after link/supplier/consumer
unbind is visible, but do not claim a general lock-free teardown proof.

## Tests and real ARM compilation

Run `python3 test-combined-private.py -v` here. The file uses local candidate C,
the local byte-identical HDQ-v3 copy, and the actual original libcomposite
`set_config()` body. `CASCADIA_TEST_LINUX` can select the original Linux tree;
`CASCADIA_TEST_HDQ_READER` can select the exported HDQ-v3 source. Missing source or
GCC explicitly skips. There are no Apple firmware bytes or firmware prerequisites.

Five test groups PASS under GCC `-Wall -Wextra -Werror` with ASan/UBSan:

1. Actual set_config/observer/source-reader path: missing status completion,
   successful 500 mA, current zero-descriptor configuration, 2100-request USB2
   clipping, delayed status, and failed set_alt.
2. Reset/disconnect/suspend/role/remove epochs; awake/role/speed/driver state;
   source and controller lock contention; unbind fence; exact lease expiry.
3. Actual combined/source/gauge constructors: failure at each allocation or
   managed-link acquisition, wrong owner, reference unwind and drained close.
4. Actual high-low-high byte assembly, gauge burst/cache/snapshot, source-before
   and source-after, software units, combined serial replacement, age and busy
   validator failures. Positive source allowance never comes from a fake source
   API; the only transport fake returns explicitly enumerated gauge bytes.
5. Immediate UART errno, partial-burst publication rejection, source disconnect
   during the actual gauge burst, untouched output on failure and gauge suspend.

`arm-source-combined-complete.log` records actual ARMv7 object builds against
real 6.12 headers in the separate complete `../observer-arm-linux` copy:
`platform.o`, `p105-udc-observer.o`, `p105-dwc2-source.o`, and
`p105-combined-provider.o` all PASS with `W=1`, no compiler warnings. The container
emits its existing `whoami` UID-name diagnostic. The earlier full modified DWC2
`gadget/core_intr/core/platform/drd` translation-unit checks are in
`../p105-udc-observer-stage`; the only warning there is independently reproduced
on unmodified `core_intr.c`. No new module was linked/loaded or hardware tested.
Normal `.config` and the relevant normal DWC2 source hashes remain unchanged.

## Remaining concrete integration

The source reader needs builtin DWC2 and builtin libcomposite so matching the
non-exported `composite_setup` address cannot introduce a module symbol problem.
The combined provider also requires `BATTERY_APPLE_HDQ`; its v3 implementation
must replace the old API before linking a consumer. Standalone object compilation
does not prove modpost or complete module dependency integration.

There is deliberately no automatic platform probe, DT addition, input-current
power_supply registration, or charger callback installation. A consumer must own
the source platform-device and battery-supply references, construct this provider
in probe, install its ops while retaining the provider handle, and drain users
before close. The existing current-only frontend still requires an input supply;
ordinary supply publication or an explicit owned-source frontend adapter is the
remaining attachment step. This group provides the actual validated producer
callbacks instead of fabricating that supply's positive current permission.

Before runtime charging, CV/termination retention, complete hardware-fault/event
ownership and fail-safe analog shutdown must still be evidenced independently.
Neither a completed USB configuration nor valid HDQ telemetry supplies those
analog guarantees. Existing default-disabled current-only code and its safety
restrictions are unchanged by this private group.

Public reproduction: `python3 tests/test-experimental-source-provider.py`.
All files here are isolated, including the complete HDQ API candidate copy.
Neither DWC2 patch is applied by the normal build. The constructor supplies
callbacks only; automatic input-supply, probe, DT and charger binding are absent.
Apply-order for a future disposable source review is observer hooks, then source
reader hooks, first placing the supplied observer-base C/H in the disposable
DWC2 tree. The resulting observer C/H must equal the supplied updated versions; this is not a boot recipe.

Owned source invalidation now reaches the frontend through registered and
synchronously drained atomic notifiers; see [the concrete path and limits](NOTIFICATIONS.md).
No PMU I/O occurs in callbacks; physical shutdown deadlines remain unverified.

# Isolated current frontend v6: actual owned source/gauge integration

This is an offline Linux C candidate. It is not installed, enabled, loaded, or
wired to a DT node. The Kconfig default and all four experiment parameters are
false. No device transaction or normal kernel build/configuration was changed.
It is not a physically validated charger and supplies no guessed CV, termination,
OTP, watchdog, temperature-threshold or analog-fault initialization.

The production current register core is byte-identical to v2. Its checked
transactions, current/profile readback interpretation, inherited limits,
exclusive read-clear event ownership, error latch and bounded shutdown attempts
are retained. The new code connects an actual producer and fixes lifetime races;
the further default-false USB2 selection policy below changes nominal plans
without adding analog/protection register settings.

## Actual producer attachment

`owned_usb2_source` is a read-only, default-false module parameter. When explicitly
selected in an independently reviewed experiment, `d_providers_acquire()` owns:

* the real battery supply reference from `apple,battery-supply`;
* the actual USB platform-device reference returned by `of_find_device_by_node()`
  for `apple,usb-source-controller` (with the OF-node reference put immediately);
* the actual combined provider handle from
  `p105_combined_provider_open(current_device, source_device, battery_supply)`.

The combined reader implementation lives in `../p105-source`.
It creates managed links to the actual controller and gauge platform suppliers,
pins their module/device/supply lifetimes, observes actual completed USB2
configuration budget and obtains an atomic bounded gauge sample. The frontend
owns the factory handle until after its work and IRQ users are drained.

The owned route has **no input power_supply lookup or dummy supply**. Worker
callbacks still pass its null input argument, and the actual combined producer
uses its owned DWC2 reader as the authoritative source. A source/descriptor
fixture cannot be substituted by platform-data permission in this route. The
legacy external-platform-data branch remains separate; its caller must supply
and own its existing provider contract.

Acquisition happens before any PMU read, with work/IRQs inactive. Every partial
acquisition is released by the same `d_release()` path. Failure to find a node,
platform device, battery, compiled provider or healthy reader produces an error;
there is no fallback to a fabricated current cap. The provider factory functions
are used only under `IS_REACHABLE(CONFIG_P105_COMBINED_CURRENT_PROVIDER)`.

No DT node/property was added to the normal system. The property names above are
candidate integration inputs, not assertions that the normal DT contains them.
The two original allow/retention assertions still deny probe by default. A
property write before `ready=true` now returns `-EAGAIN`, preventing the brief
power_supply-registration window from activating IRQs while probe is unfinished.

Neither route registers an `external_power_changed` callback into a foreign
supplier's workqueue. The owned route also registers a drained atomic USB-source notification; both
retain polling and their existing raw PMU source events. Cancellation of this supply's own changed_work
cannot drain an unrelated supplier's callback that already holds a class-device
reference; that reference also does not preserve this frontend's devm context.
The unsafe callback is removed, not merely guarded after entering freed context.
The same actual descriptor constructor is tested with both route selectors.

The owned observer now propagates USB suspend/reset/disconnect/configuration
invalidation directly to the frontend epoch and urgent work queue. Stop fences
queueing and drains this registered notifier before IRQ/work/handle teardown.
See [notifications](../p105-source/NOTIFICATIONS.md). This does **not** prove
immediate physical UDC-to-PMU shutdown or a USB electrical timing deadline. Validation rejects
observed source invalidation before/after every enable attempt; the existing
100 ms poll is not instantaneous physical cutoff. Removing the legacy callback
can change notification latency, which is explicit rather than called equivalent.

## Stop, IRQ and handle ownership

v2 had a concrete queue race: an invalidate/worker path could read `ready` and
`stopping`, pause, then call `mod_delayed_work()` after stop had completed
`cancel_delayed_work_sync()`. A device-link reference would not prevent that
late work from touching closed producer handles or freed consumer context.

v4's `d_queue()` holds `queue_lock` over both permission checks and scheduling.
All scheduling routes use this helper. `d_stop()` takes the same lock, marks
stopping, clears ready and advances the epoch. Thus scheduling finishes before
the stop fence or observes the fence and does not occur. The lock is released
before waiting for work or IRQ threads; stop never waits while holding it.

The actual release ordering is:

1. Serialize against property activation with `lifecycle_lock`; publish the
   queue/epoch fence under `queue_lock`.
2. Drain the owned combined-provider notifier in process context, outside
   spinlocks. Disable the activated, exclusively owned parent IRQ where necessary.
   `synchronize_irq()` drains **every registered** parent action, including the
   `parent_failed` path that used `disable_irq_nosync()` in its own thread.
3. `cancel_delayed_work_sync()` drains the worker. Future queue attempts are
   blocked by the fence. Under `io_lock`, perform one checked inhibit and one
   checked zero-input attempt if activation occurred. Failure retains
   `stop_error`/`fault_latched` and explicitly reports physical state unknown.
4. Unregister the exposed power_supply; property calls see stopped state.
   Remove/free the owned parent action before any nested mapping is disposed.
5. Free/drain nested child actions, dispose mappings, restore only owned mask
   bits with checked RMW, then remove the manual IRQ domain.
6. Close the combined provider after all callback/work/IRQ users are gone, then
   put the source platform-device and battery-supply references. This completes
   before driver-core devres/managed-link teardown can release supplier context.

The parent is requested without `IRQF_SHARED`, initially `IRQF_NO_AUTOEN`.
`parent_irq>=0` denotes a successfully requested action on all failure paths;
request/type failures reset it to -1. A parent thread therefore cannot look up
mappings in a removed domain or outlive the closed provider. The source raw
handlers cannot queue after stop; their `free_irq()` precedes context teardown.
This still requires the experiment to be the single PMU event owner, with no
independent ADC/watchdog/event-bank reader or foreign mask writer.

Suspend/freeze/poweroff use the same stop path. Resume does not resurrect a
retention assertion, old source lease or activation; a fresh independently
reviewed handoff/rebind remains necessary. Stop errors are not converted into a
successful analog shutdown claim. Remove cannot return that physical error, so
it retains the explicit diagnostic while completing lifetime cleanup.

## Bounded fault handling

The previous actual worker had another concrete failure: each negative supplier
snapshot called `d_fault()`, which unconditionally called `d_invalidate()` and
queued immediate work despite `fault_latched` already being true. Its final
no-retry guard could not cancel the earlier scheduling. Persistent EAGAIN/EIO
thus created a CPU/UART busy loop after the one allowed inhibit attempt.

Under the existing `io_lock`, v4 detects the first transition to the fault latch.
Every fault still clears applied validity and advances the epoch, but only the
first transition can schedule immediate work. A worker that causes its first
fault can leave one pending follow-up; the second failed iteration neither
queues again nor repeats PMU I/O because `inhibit_attempted` is already set.
The fault does not silently recover from later successful samples. New external
raw PMU events are distinct from self-requeue and remain subject to the stop
queue fence. No unknown status bit or recovery register is invented.

## Validation

Run these four self-contained entry points from the repository root:

* `python3 tests/test-experimental-current-lifecycle.py -v`: six GCC ASan/UBSan groups run
  actual candidate `d_providers_acquire/d_queue/d_invalidate/d_set/d_stop/d_release`
  functions against explicit kernel ownership/IRQ/work mocks. They exercise
  successful real-factory attachment, every partial acquisition error, absence
  of dummy supply lookup, unavailable compiled provider, exact reference unwind,
  source-parent IRQ removal before nested mappings and handle close, failed
  shutdown, parent_failed IRQ synchronization, the pre-probe write guard, and both descriptors lacking foreign callbacks.
  A deterministic pthread interleaving holds the actual queue call while stop
  begins; stop cannot pass the fence until scheduling finishes, then drain removes
  the scheduled item and 100 late invalidations cannot requeue it. This is a
  tested specific interleaving, not a universal concurrency-model proof.
* `python3 tests/test-experimental-current-pm.py -v`: one production-C PM group covers suspend,
  repeated stop, no-I/O resume, failed inhibit/zero-input and an inactive bind.
* `python3 tests/test-experimental-current-core.py -v`: two UBSan groups retain 16 original 12H321
  final-register oracle cases and checked I/O/readback boundaries. The oracle
  contains register results and an image hash, not Apple executable bytes.

The integration mock factory only returns a callback identity and can fail. Its
mock snapshot always returns `-EOPNOTSUPP`, validation always false. It never
fabricates positive source permission. Actual factory lifetime, HDQ transactions,
libcomposite set_config and completed-source grants are separately exercised by
the five actual-C groups in `../p105-source`.

* `python3 tests/test-experimental-current-fault-worker.py -v`: three ASan/UBSan groups run actual
  `d_fault()` and actual `d_worker()` against negative-only EAGAIN/EIO/ENODEV
  supplier callbacks and the production register core. Two worker iterations
  prove the immediate queue ends after one follow-up and I/O attempts remain
  bounded. Repeated fault calls still advance every epoch. A copied exact frozen
  v3 `d_fault()` body is compiled as a separate negative-control executable; it
  fails the same no-requeue assertion on the second worker iteration. The child
  core-dump limit is zero, and the historical code is never built into the module.

All twelve retained core/PM/lifecycle/fault tests and five source-notification
tests PASS. Missing GCC explicitly skips. ARMv7 object builds
against real Linux 6.12 headers with `W=1` PASS with no compiler warnings for both
reachable and unavailable provider branches (`arm-frontend-owned-v4.log` and
`arm-frontend-unavailable-v4.log`). The earlier v4 owned-branch `nm` shows its three combined-provider calls and
`synchronize_irq`; the unavailable branch has no combined symbols. The v5
notification group additionally ARM-compiles both branches and the actual
register/unregister calls; see its separate [validation](../p105-source/NOTIFICATIONS.md). `make prepare` explicitly refreshed the isolated generated
config before each branch: `olddefconfig` alone is not sufficient for an external
M= object build to consume fresh generated macros. The existing container UID
`whoami` diagnostic is unrelated to compiler warnings. No module was linked,
loaded or hardware tested. The normal `.config` SHA remains
`8b59b75e728cfacfb3441adf08b4de6e38c4ca53788fcee039ddddfdc43bed20`.

Primary kernel contracts:
[device links](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/Documentation/driver-api/device_link.rst),
[IRQ synchronization/free](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/kernel/irq/manage.c),
[workqueue cancellation](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/kernel/workqueue.c),
[power supply unregister/foreign changed work](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/power/supply/power_supply_core.c).

## Remaining runtime limits

The actual producer closes the former missing source/gauge factory gap. Current
CDC2 still provides 0 mA allowance. Explicit alternative USB2 descriptors can
supply at most 500 mA protocol allowance; they are not changed here. The frontend retains zero charge selection for owned USB2 by default. A further
default-false `allow_usb2_current` experiment can select bounded100/500mA plans;
see [its exact source, tests and limits](USB2_CURRENT.md). The legacy route
keeps its conservative experimental input>=1000mA restriction. This is
not proof that iOS cannot trickle-charge from 500 mA. No external charger/accessory
permission implementation is fabricated to bypass that limit.

Full CV/termination/fault protection and inherited analog retention, physical
source/suspend cutoff timing, complete event ownership and calibration remain
independent requirements before any runtime activation. The producer integration
and compile/test results are evidence for software ownership and transactions;
they do not prove electrical or battery safety or that charging works on hardware.

Public source stays outside the normal build. The source-provider include is
relative to the adjacent isolated component; no DT or enabled config is added.

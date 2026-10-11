# P105 host PHY: power error handling

Research date: 2026-10-11. This is a local source correction with mocked
callback tests. No USB device, iPad supply or PMGR register was accessed.

The existing `s5l_hostphy_power_on()` in
`patches/files/drivers/phy/phy-apple-s5l-usb.c` enabled LPO and HSIC supplies
before enabling the host power gates. Three failure paths were misleading:

- A deferred HSIC provider or failed later enable left a newly acquired LPO
  enable reference in place.
- An EHCI gate timeout left newly enabled supplies in place; an OHCI0 gate
  error was ignored entirely and the callback returned success.
- Power-off ignored failed regulator disables and cleared both state flags,
  losing track of failed cleanup.

The correction propagates acquisition errors other than optional-supply
absence (`-ENODEV`), propagates both gate errors, and undoes only supply
references acquired by the failing call. It preserves the original failure
even when cleanup also fails. Previously enabled references are retained.
Power-off attempts both releases and returns the first error; a failed release
retains the corresponding flag for a subsequent attempt.

There is no new PMGR gate-off/reset sequence. A failed PMGR enable might have
changed gate state before its timeout; the patch does not claim to restore it.
There are no new PHY tuning, Lightning routing, VBUS or charger writes. The
successful power-on sequence retains the previous register operations.

## Scope of reference accounting

The flags represent this driver's consumer enable references, not a measured
rail voltage. P105's `wlan_lpo` and `wlan_reg_on` supplies use the existing
`apple-pmu-pwrsw` provider, with enable/disable/is_enabled operations. The DT
has no parent supply, coupling or consumer load for these supplies. In that
topology a provider disable failure returns before the consumer reference is
released.

This is not a general guarantee of `regulator_disable()`. Linux v6.12
[`drivers/regulator/core.c`](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/regulator/core.c#L2983)
can also report an error after releasing a consumer reference, from load
updates, coupled-rail balancing or a parent-supply disable. Reference/retry
handling needs another review if the board's supply topology changes.

The Linux PHY core retains `power_count` after a failed power-off callback;
partial cleanup can therefore be retried. The test models early provider
failures only, not the regulator core's complete dependency graph.

## Verification

`tests/test-usb-phy-power.py` extracts the actual production callbacks and
gate constants, then compiles them with fake regulators, PMGR and MMIO under
UBSan and `-Wall -Wextra -Werror`. Its 18 cases cover successful activation,
repeat activation, optional absence, deferred/failed acquisition, enable
failures, both gate failures, preservation of existing references, failed
rollback, power-off failure and subsequent cleanup. No electrical behavior
or successful EHCI enumeration is established by those tests.

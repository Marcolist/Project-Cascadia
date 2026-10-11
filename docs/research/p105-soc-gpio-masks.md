# P105 SoC GPIO: the second mux bit and a bounded Linux comparison

## Result and scope

The current A5 Linux GPIO driver clears selector bit `0x20`, but leaves selector
bit `0x40` behind when configuring a GPIO output. Its peripheral branch sets
`0x20` without first clearing `0x40`. The verified P105 firmware treats these
bits as a two-bit function selector. This is a reproducible source-level mask
problem, independent of the still unproven electrical purpose of accessory GPIO
132.

This research group changes **no runtime driver**. The comparison compiles the
actual Linux callbacks, then compiles a temporary candidate with only their
selector clear masks changed. Both execute against ordinary C arrays. The
firmware oracle executes original instructions in Unicorn using synthetic RAM.
There is no hardware MMIO backend, device access, GPIO operation, or claim that
this alone enables accessory power, VBUS, USB host mode or charging.

## Pinned inputs and dispatch proof

Firmware input is the locally decrypted official
`iPad2,5_8.4.1_12H321_Restore.ipsw` kernelcache. Its Mach-O SHA256 is
`db1ddc8343aa9debc00e0a083fba59d9f555722db60957dc333b854fac21dd2c`.
The public harness refuses other bytes. No firmware bytes are included here.

The original AppleS5L8930X GPIOIC constructor's PIC load/add at
`0x80ded0d8/0x80ded0da`, including the instance-vtable `+8`, resolves to
`0x80df1938`. The harness checks these actual slots before execution:

| Instance slot | Thumb target | Role |
| --- | --- | --- |
| `+0x378` | `0x80ded989` | Raw register read |
| `+0x37c` | `0x80ded991` | Raw register write |
| `+0x380` | `0x80ded869` | Configuration mode |

The configuration function uses a 16-bit shadow array at object `+0x80` and a
register base at `+0x64`. In the harness these point to synthetic allocations.
Line 132 selects fake register offset `4 * 132`; that arithmetic does not
identify a physical pad or board net. Only the original IRQ/lock import calls
at `0x80df0874`, `0x80df05a4`, `0x80df05b4` are stubbed. Instruction execution is
bounded and must return. The audited output setter at `0x80ded938` uses modes
14/15 for logical levels 0/1, as also established by the separate
[accessory GPIO provider experiment](p105-accessory-gpio.md).

Linux source is
`patches/files-sandcastle-port/drivers/pinctrl/pinctrl-s5l8940x-gpio.c`.
The audited baseline SHA256 is
`e71fc77818ad2a6358b55ee8233da79c30b2f88985decd9e34bcadb01456c53f`.
Every result includes the hash of the source actually compiled. The temporary
candidate rejects unexpected callback shape. The harness extracts the existing
macros and eight callback bodies; it does not reimplement the Linux decisions in
Python. Only readl/writel, small containing structures and data-access helpers
are replaced with fake equivalents. Existing `cc` compiles with warnings as
errors and undefined-behavior instrumentation.

## Actual firmware selector behavior

For old firmware shadow `s`, the original instruction results are:

| Audited mode | Clear mask | Selected value | Meaning justified here |
| --- | --- | --- | --- |
| 14 | `0x6f` | `0x02` | GPIO output, low |
| 15 | `0x6f` | `0x03` | GPIO output, high |
| 2 | `0x260` | `0x220` | Function selector `0x20`, config bit set |
| 3 | `0x260` | `0x240` | Function selector `0x40`, config bit set |
| 4 | `0x260` | `0x260` | Function selector `0x60`, config bit set |

Modes 2/3/4 compute `(s & ~0x260) | selected_value`; they preserve DATA and the
IRQ field. GPIO output modes compute `(s & ~0x6f) | selected_value`. **Mode 2's
mask is `0x260`, not `0x6e`.** No pin-specific alternate-function names are
assigned from these values.

Mode 0 clears the function selector using mask `0x26e`, sets `0x200`, and
preserves or normalizes the old IRQ field: old values `0x02` and `0x0e` become
zero, while other old IRQ values survive. DATA is preserved. This does not match
Linux's separate policy of selecting IRQ-off `0x0e` for a plain input.

## Linux baseline and comparison-only candidate

The current definition `REG_GPIOx_PERIPH = 1 << 5` has two distinct jobs:
recognizing/setting the one supported peripheral function, and serving as the
clear mask. The second job is too narrow. The candidate introduces a separate
`REG_GPIOx_MUX_MASK = 3u << 5` for clear masks only:

- Output, enabled-IRQ and plain-input refresh clear `0x60` instead of `0x20`.
- Peripheral refresh additionally clears `0x60`, then continues to set `0x20`.
- Function count/names, software flags, DATA/IRQ handling, initialization
  decoder, `CFG_DONE`, register width, timing and all board consumers remain
  as in the existing driver.

Representative final fake-register values, starting with `CFG_DONE` already
set:

| Operation | Initial | Current Linux | Temporary mask candidate | Actual firmware |
| --- | --- | --- | --- | --- |
| Output low | `0x2d0` | `0x2d2` | `0x292` | `0x292`, mode 14 |
| Output high | `0x2d0` | `0x2d3` | `0x293` | `0x293`, mode 15 |
| Set output low | `0x2d2` | `0x2d2` | `0x292` | `0x292`, mode 14 |
| Set output high | `0x2d2` | `0x2d3` | `0x293` | `0x293`, mode 15 |
| Plain input | `0x2d0` | `0x2de` | `0x29e` | `0x290`, mode 0 |
| Select peripheral | `0x2d0` | `0x2f0` | `0x2b0` | `0x2b0`, mode 2 |
| Input with inherited peripheral | `0x2b0` | `0x2b0` | `0x2b0` | `0x290`, mode 0 |

The last two input rows deliberately record remaining differences. They are not
passed off as firmware equivalence. All four refresh branches are separately
covered by actual-C fixtures. Upper 32-bit fields are preserved: input
`0xa50002d0` becomes output high `0xa5000293` in the candidate. The firmware
shadow itself is only 16-bit, so upper-field preservation is a Linux test,
not a firmware comparison.

## Binding and primary-source cross-checks

The P105 Linux DT's `gpio@fa00000` binds to `apple,s5l8940x-gpio`, the compatible
matched by this driver, with 224 pins. The currently declared functions are
`gpio` and `periph`; `periph` selects `0x20`. Its explicit DT consumer
`uart1-pins` requests that function for GPIOs 40–43. The pin-function catalog is
not expanded by the comparison. The original P105 ADT GPIO node and the pinned
kernelcache instead identify AppleS5L8930XGPIOIC with `gpio,s5l8930x`. The
different naming must not be taken as evidence that an unrelated SoC driver is
equivalent; the pinned firmware is the A5 evidence used above.

OpeniBoot's A4 implementation clears both selector bits for GPIO modes and has
three alternate selector values `0x20/0x40/0x60`. This corroborates the family
convention; its A4 pull/config policy is not imported as P105 behavior.
[Primary source, revision 866562fdb1cfd019bcd77885c80fbf0af65d5c15](https://github.com/iDroid-Project/openiBoot/blob/866562fdb1cfd019bcd77885c80fbf0af65d5c15/plat-a4/gpio.c).

Linux v6.12's modern Apple GPIO driver also defines a two-bit peripheral field
and clears it during both direction callbacks. Its later-SoC input-enable and
pull definitions are not A5 register documentation.
[Primary source, revision adc218676eef25575469234709c2d87185ca223a](https://raw.githubusercontent.com/torvalds/linux/adc218676eef25575469234709c2d87185ca223a/drivers/pinctrl/pinctrl-apple-gpio.c).

Linux's pinmux core invokes optional GPIO request/direction hooks when provided;
it does not substitute a call to the driver's `set_mux("gpio")` when those hooks
are absent. This A5 driver supplies neither `gpio_request_enable` nor
`gpio_set_direction`, so that path does not resolve its inherited input-state
issue.
[Primary core source at the same Linux revision](https://raw.githubusercontent.com/torvalds/linux/adc218676eef25575469234709c2d87185ca223a/drivers/pinctrl/pinmux.c).

## Narrow runtime proposal and excluded changes

A separate selector mask `0x60` in the four refresh clear masks is technically
supported by the actual P105 function, with the output branch the strongest
exact oracle match. Keep `REG_GPIOx_PERIPH = 0x20` as the existing selected
function and software-state decoder. Replacing that constant globally with
`0x60` would instead select a different function and is incorrect.

Before any runtime application, review these distinct questions independently:

1. `direction_input()` clears OUTEN but retains cached PERIPH. It can leave an
   explicitly requested GPIO input in peripheral mode. A mux-mask change alone
   does not fix this.
2. Initialization recognizes `0x20`, but not a `0x40`-only alternate function.
   Representing unknown inherited functions requires a separate state policy.
3. Firmware mode 2 preserves IRQ/DATA; Linux clears IRQ and applies cached DATA.
   Example `0xfffe` yields firmware `0xffbe`, candidate `0xffb0`; `0x291` yields
   firmware `0x2b1`, candidate `0x2b0`. These existing policies are not changed.
4. Linux's config helper can write twice if `CFG_DONE` was absent. Starting at
   `0xd0`, candidate output-high writes `0x93` then `0x293`; firmware mode 15
   writes only `0x93`. The mask evidence does not authorize changing this timing.
5. Actual pad mux availability, consumer transitions, GPIO 132 board wiring,
   power-switch polarity, accessory voltage and host VBUS remain hardware
   questions. No voltage or power capability follows from clearing `0x40`.

## Reproduce without hardware

Use an existing Python/Unicorn environment and existing C compiler:

```sh
python3 tests/test_soc_gpio_masks.py
python3 scripts/compare-soc-gpio.py build/firmware/kernelcache.12H321.macho
```

Nine unittest methods cover baseline-versus-candidate outputs, all refresh
branches, alternate functions, input differences, 32-bit preservation,
config-write ordering and rejected inputs/source drift. Firmware-dependent
tests explicitly skip when local firmware, Unicorn or `cc` are absent; a skip
is not a firmware validation. The recorded local verification used all
dependencies and ran without skips. No package installation is required by
these scripts. The generated comparison exists only in a temporary directory;
the public source reports `runtime_source_changed: false`.

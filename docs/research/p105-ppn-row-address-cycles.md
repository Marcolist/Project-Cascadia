# P105 PPN 1.5 row-address cycle mismatch

**Source-qualified candidate; physical qualification is pending.** The kernel
and userspace PIO page readers both sent three row-address bytes. The original
firmware selects four for the PPN 1.5.x profile documented for this port, even
when the fourth address byte is zero. This patch changes that count in both
`0A ROW 37` readers. It does not change the row value, geometry, command
allowlist, status interpretation, data transfer, or controller restoration.

The port still assumes a fixed NAND profile. The connected iPad's actual
protocol revision and geometry have not been identified by these tests. This
candidate must not be treated as a generic version detector or a qualified
replacement for every iPad NAND variant. Older PPN revisions have a different
selection rule; retain the draft until the applicable profile is verified.

## Original firmware evidence

All addresses are from the specifically identified **iBEC** images, not from
an iBoot image or a neighboring firmware revision:

| Image | Complete plaintext SHA-256 |
| --- | --- |
| iPad2,5 12H321 iBEC | `30c040052c444222edc8646316f95a355a9e338d6aadc7168f8a7acc7c4578ec` |
| iPad2,5 13G36 iBEC | `17020be7b0fa2d67637e00106254002084f9b51925ba1d91e10a95bf5101a0a8` |

In 12H321, `0x9ff03116..312a` packs ID bytes 3,4,5 as
`major << 16 | minor << 8 | patch`. The value is passed as the final stack
argument at `0x9ff0343a..343e`; channel setup stores it in the PPN object at
offset `0x200` at `0x9ff089a8`. The geometry reader then selects the widths:

| Selection | 12H321 | 13G36 |
| --- | --- | --- |
| Version load / compare | `9ff084ba..84c6` | `9ff08a16..8a22` |
| Compared literal | `0x000104ff` at `9ff08800` | `0x000104ff` at `9ff08d54` |
| Older-version geometry sum / ceil to bytes | `9ff084c8..84da` | `9ff08a24..8a36` |
| Newer-version row count = 4 | `9ff08502..8504` | `9ff08a5e..8a60` |
| Row-plus-column count = 8 | `9ff08508..850e` | `9ff08a64..8a6a` |

The selected row count is stored at PPN-object offset `0x260`; the combined
count is at `0x261`. For the documented ID `PPN 01 05 05`, the packed revision
is `0x010505`, above the cutoff. Five original arithmetic/selection slices per
image were executed offline for versions `010400`, `0104ff`, `010500`,
`010505`, and `010600`: all ten cases selected the expected 3/7 or 4/8 widths.
Only synthetic RAM and the original instruction bytes were used; no helper
mock or MMIO was involved. This proves the selection, not the unit's ID.

The width is consumed by an actual read command, not just stored unused:

- The direct 12H321 reader loads `0A` and `37` at `9ff0790c..790e`, loads
  `PPN+260` at `9ff07910`, and passes it to the command/address helper at
  `9ff07914..7918`.
- The normal sequential read function loads `PPN+260`, subtracts one and
  queues it at FMI offset `c0014` at `9ff0a038..a04a`. The same function
  queues `370a` at `9ff0a29a..a2da` (or `3707` for preceding pages).
- Both Linux command/address helpers encode an N-byte address as
  `(N + 7) & 7` in `FMC_ADDRNUM`. Passing three therefore writes 2; passing
  four writes 3. Writing a 32-bit `FMC_ADDR0` alone does not select four cycles.

Earlier bring-up notes and the PIO implementation used three bytes. Those
historical read observations are not discarded, but they do not explain why
that abbreviated command was tolerated. The native fixed-profile selection
is the basis of this candidate. Firmware bytes remain outside the repository.

## Offline regression and build scope

`python3 tests/test-ppn-row-cycles.py -v` compiles the actual two page-reader
functions and their actual command/address helpers under UBSan and Werror.
The local register/API fixtures check four row values, successful reads,
command failures and status failures: 24 transactions in two groups. Both
groups pass; unchanged main fails both at the encoded-address-count check.
The row, CE release, end command, data-transfer gating and saved-state
restoration are checked alongside the count. The fixture does not establish
physical bus timing or data validity.

A complete ARM kernel module build with `W=1`/`-Werror`, and an ARM userspace
`ppn.c` object build with `-Wall -Wextra -Werror`, passed without warnings.
Builds used at most two CPUs and 1 GiB, with original kernel sources read-only.
No driver, firmware or tool was transferred to the iPad.

## Relation to the current read failure

Four earlier bounded reads on the running frozen kernel returned status
`0x50`, ECC-failure counters and invalid data. Existing boot logs show
`FMC_ON=5` on both buses; that does not qualify the rest of the inherited
interface state. The address-width discrepancy is a concrete investigation
lead, **not a demonstrated cause or repair of those failures**. No further
NAND reads or controller resets were made for this work. NAND program/erase,
partitioning and Linux filesystem installation remain excluded.

The late transport-error fixes in #9 and unknown-status handling in #13
remain independent. This count-only patch must retain those corrections when
combined; it does not replace them.

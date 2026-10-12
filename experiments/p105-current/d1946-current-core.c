/* SPDX-License-Identifier: GPL-2.0 */
/* Experimental current controls only. No CV/termination/OTP defaults. */
#include "d1946-current-core.h"

int d1946_update_checked(const struct d1946_io *io, unsigned int reg, u8 mask,
			 u8 value)
{
	u8 before, wanted, actual;
	int ret;
	if (!io || !io->read || !io->write || reg > 255 || !mask)
		return -EINVAL;
	ret = io->read(io->context, reg, &before, 1);
	if (ret)
		return ret;
	wanted = (before & ~mask) | (value & mask);
	if (wanted != before) {
		ret = io->write(io->context, reg, &wanted, 1);
		if (ret)
			return ret;
	}
	ret = io->read(io->context, reg, &actual, 1);
	if (ret)
		return ret;
	return (actual & mask) == (wanted & mask) ? 0 : -EIO;
}

/* Frontend API constraint; zero is a valid inhibit request. */
int d1946_charge_request(unsigned int ma)
{
	return ma > 720 || (ma && ma < 40) ? -EINVAL : 0;
}

int d1946_current_limit(const struct d1946_io *io, unsigned int ma, u8 ceiling)
{
	static const u8 slot_max[5] = { 0, 0, 63, 63, 63 };
	unsigned int i, code;
	int ret;
	if (ma > 2520 || ceiling > 63)
		return -EINVAL;
	if (!ma)
		return d1946_update_checked(io, 0x3f, 0x40, 0x40);
	code = ma / 40;
	if (code > ceiling)
		code = ceiling;
	if (!code)
		return -ERANGE;
	for (i = 0; i < 5; i++) {
		unsigned int limited = code < slot_max[i] ? code : slot_max[i];
		ret = d1946_update_checked(io, 0x4b + 2 * i, 0xff, limited);
		if (ret)
			return ret;
	}
	return d1946_update_checked(io, 0x3f, 0x40, 0);
}

/* These five absent-calibration fallback points execute in the pinned 12H321
	* oracle. A general calibration formula is intentionally not approximated. */
int d1946_input_profile(unsigned int ma)
{
	switch (ma) {
	case 0:
		return 0;
	case 100:
		return 2;
	case 500:
		return 34;
	case 1000:
		return 72;
	case 1500:
		return 110;
	case 2100:
		return 158;
	default:
		return -EINVAL;
	}
}

int d1946_input_limit(const struct d1946_io *io, unsigned int ma)
{
	int code = d1946_input_profile(ma), ret;
	if (code < 0)
		return code;
	ret = d1946_update_checked(io, 0x1b, 0x04, ma ? 0 : 0x04);
	if (ret)
		return ret;
	ret = d1946_update_checked(io, 0x1c, 0x80, ma ? 0 : 0x80);
	if (ret)
		return ret;
	return d1946_update_checked(io, 0x3d, 0xff, code);
}

int d1946_mask_checked(const struct d1946_io *io, unsigned int event,
		       bool masked, u8 *committed_bank)
{
	u8 actual;
	unsigned int reg;
	int ret;
	if (event >= 72 || !committed_bank)
		return -EINVAL;
	reg = 0x12 + event / 8;
	ret = d1946_update_checked(io, reg, 1u << (event % 8),
				   masked ? 1u << (event % 8) : 0);
	if (ret)
		return ret;
	ret = io->read(io->context, reg, &actual, 1);
	if (ret)
		return ret;
	*committed_bank = actual;
	return 0;
}

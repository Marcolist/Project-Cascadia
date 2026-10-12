/* SPDX-License-Identifier: GPL-2.0 */
#ifndef P105_COMBINED_PROVIDER_H
#define P105_COMBINED_PROVIDER_H
struct device;
struct power_supply;
struct d1946_current_provider;
struct p105_combined_provider;
/* Constructor runs only in consumer probe with held source-device/battery-psy
 * references. No DT, charger callback or registration is supplied. Caller stops
 * and drains every snapshot/valid user before close on remove or probe error.
 * Ordinary input-current power_supply publication remains consumer integration
 * work; the source reader is authoritative, not the callback's input psy arg. */
struct p105_combined_provider *
p105_combined_provider_open(struct device *, struct device *,
			    struct power_supply *);
void p105_combined_provider_close(struct p105_combined_provider *);
const struct d1946_current_provider *
p105_combined_provider_ops(struct p105_combined_provider *);
#endif

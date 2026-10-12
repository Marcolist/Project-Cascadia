// SPDX-License-Identifier: GPL-2.0
/* Actual managed source-reader + HDQ-reader adapter for the current-only C
 * experiment. USB protocol budget and battery sampling are separate contracts.
 * No CV/termination/fault programming, external-accessory grant, fake source
 * cap, descriptor increase or1000mA source-detection threshold is introduced.
 */
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/ktime.h>
#include <linux/power_supply.h>
#include "d1946-current-provider.h"
#include "apple-hdq-snapshot.h"
#include "p105-dwc2-source.h"
#include "p105-combined-provider.h"
struct p105_combined_provider {
	spinlock_t lock;
	bool dead, valid;
	u64 serial;
	struct p105_dwc2_source_reader *source;
	struct apple_hdq_reader *gauge;
	struct power_supply *battery_identity;
	struct p105_usb_source_sample source_sample;
	struct apple_hdq_sample gauge_sample;
	struct d1946_snapshot published;
	struct d1946_current_provider ops;
};
static bool p105_same_source(const struct p105_usb_source_sample *a,
			     const struct p105_usb_source_sample *b)
{
	return a->generation == b->generation &&
	       a->completed_cookie == b->completed_cookie &&
	       a->budget_ua == b->budget_ua && a->kind == b->kind &&
	       a->online == b->online;
}
static bool p105_same_published(const struct d1946_snapshot *a,
				const struct d1946_snapshot *b)
{
	return a->generation == b->generation &&
	       a->sampled_ns == b->sampled_ns &&
	       a->valid_until_ns == b->valid_until_ns &&
	       a->online == b->online && a->budget_ua == b->budget_ua &&
	       a->present == b->present && a->voltage_uv == b->voltage_uv &&
	       a->temp_decic == b->temp_decic;
}
static int p105_combined_snapshot(void *context, struct power_supply *input,
				  struct power_supply *battery,
				  struct d1946_snapshot *out)
{
	struct p105_combined_provider *p = context;
	struct p105_usb_source_sample before, after;
	struct apple_hdq_sample gauge;
	struct d1946_snapshot result;
	unsigned long flags;
	u64 now;
	int ret;
	/* input psy is not a substitute for the owned controller source reader. */
	(void)input;
	if (!p || !out || battery != p->battery_identity)
		return -EINVAL;
	if (READ_ONCE(p->dead))
		return -ENODEV;
	ret = p105_dwc2_source_snapshot(p->source, &before);
	if (!ret)
		ret = apple_hdq_reader_snapshot(p->gauge, NSEC_PER_SEC, &gauge);
	if (!ret)
		ret = p105_dwc2_source_snapshot(p->source, &after);
	if (!ret && !p105_same_source(&before, &after))
		ret = -EAGAIN;
	if (!ret && (!p105_dwc2_source_valid(p->source, &after) ||
		     !apple_hdq_reader_valid(p->gauge, &gauge)))
		ret = -ESTALE;
	if (ret) {
		spin_lock_irqsave(&p->lock, flags);
		p->valid = false;
		p->serial++;
		spin_unlock_irqrestore(&p->lock, flags);
		return ret;
	}
	/* Start age at earliest battery/source observation, never at completion. */
	result = (struct d1946_snapshot){
		.sampled_ns = min(gauge.begin_ns, after.observed_ns),
		.valid_until_ns =
			min(gauge.valid_until_ns, after.valid_until_ns),
		.online = after.online,
		.budget_ua = after.budget_ua,
		.present = gauge.gauge_present,
		.voltage_uv = gauge.voltage_uv,
		.temp_decic = gauge.temp_decic,
	};
	now = ktime_get_ns();
	if (result.sampled_ns > now || result.valid_until_ns <= now ||
	    result.valid_until_ns - result.sampled_ns > NSEC_PER_SEC) {
		spin_lock_irqsave(&p->lock, flags);
		p->valid = false;
		p->serial++;
		spin_unlock_irqrestore(&p->lock, flags);
		return -ESTALE;
	}
	spin_lock_irqsave(&p->lock, flags);
	if (p->dead)
		ret = -ENODEV;
	else {
		result.generation = ++p->serial;
		p->source_sample = after;
		p->gauge_sample = gauge;
		p->published = result;
		p->valid = true;
	}
	spin_unlock_irqrestore(&p->lock, flags);
	if (ret)
		return ret;
	*out = result;
	return 0;
}
static bool p105_combined_valid(void *context,
				const struct d1946_snapshot *sample)
{
	struct p105_combined_provider *p = context;
	struct p105_usb_source_sample source;
	struct apple_hdq_sample gauge;
	unsigned long flags;
	bool valid;
	u64 now = ktime_get_ns();
	if (!p || !sample || sample->sampled_ns > now ||
	    sample->valid_until_ns <= now ||
	    sample->valid_until_ns - sample->sampled_ns > NSEC_PER_SEC)
		return false;
	if (!spin_trylock_irqsave(&p->lock, flags))
		return false;
	valid = !p->dead && p->valid &&
		p105_same_published(sample, &p->published);
	if (valid) {
		source = p->source_sample;
		gauge = p->gauge_sample;
	}
	spin_unlock_irqrestore(&p->lock, flags);
	if (!valid || !p105_dwc2_source_valid(p->source, &source) ||
	    !apple_hdq_reader_valid(p->gauge, &gauge))
		return false;
	/* A concurrent newer snapshot cannot make this older tuple valid. */
	if (!spin_trylock_irqsave(&p->lock, flags))
		return false;
	valid = !p->dead && p->valid &&
		p105_same_published(sample, &p->published) &&
		ktime_get_ns() < sample->valid_until_ns;
	spin_unlock_irqrestore(&p->lock, flags);
	return valid;
}
struct p105_combined_provider *
p105_combined_provider_open(struct device *consumer, struct device *source,
			    struct power_supply *battery)
{
	struct p105_combined_provider *p;
	int ret;
	if (!try_module_get(THIS_MODULE))
		return ERR_PTR(-ENODEV);
	p = kzalloc(sizeof(*p), GFP_KERNEL);
	if (!p) {
		module_put(THIS_MODULE);
		return ERR_PTR(-ENOMEM);
	}
	spin_lock_init(&p->lock);
	p->source = p105_dwc2_source_open(consumer, source);
	if (IS_ERR(p->source)) {
		ret = PTR_ERR(p->source);
		goto free;
	}
	p->gauge = apple_hdq_reader_open(consumer, battery);
	if (IS_ERR(p->gauge)) {
		ret = PTR_ERR(p->gauge);
		goto close_source;
	}
	p->battery_identity = battery;
	p->ops =
		(struct d1946_current_provider){ .context = p,
						 .snapshot =
							 p105_combined_snapshot,
						 .valid = p105_combined_valid };
	return p;
close_source:
	p105_dwc2_source_close(p->source);
free:
	kfree(p);
	module_put(THIS_MODULE);
	return ERR_PTR(ret);
}
EXPORT_SYMBOL_GPL(p105_combined_provider_open);
void p105_combined_provider_close(struct p105_combined_provider *p)
{
	unsigned long flags;
	if (!p || IS_ERR(p))
		return;
	/* Caller already stopped/drained every callback; no close/read race allowed. */
	spin_lock_irqsave(&p->lock, flags);
	p->dead = true;
	p->valid = false;
	p->serial++;
	spin_unlock_irqrestore(&p->lock, flags);
	apple_hdq_reader_close(p->gauge);
	p105_dwc2_source_close(p->source);
	kfree(p);
	module_put(THIS_MODULE);
}
EXPORT_SYMBOL_GPL(p105_combined_provider_close);
const struct d1946_current_provider *
p105_combined_provider_ops(struct p105_combined_provider *p)
{
	return p && !IS_ERR(p) ? &p->ops : NULL;
}
EXPORT_SYMBOL_GPL(p105_combined_provider_ops);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION(
	"Private P105 USB2 protocol/gauge snapshot provider candidate");

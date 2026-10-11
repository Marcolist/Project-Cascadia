#!/usr/bin/env python3
"""Run actual S5L host-PHY callbacks with fake supplies and PMGR, offline."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'patches/files/drivers/phy/phy-apple-s5l-usb.c'


def function(text, name):
    start = text.index('static int ' + name + '(')
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class HostPower(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'requires a C compiler')
    def test_real_callbacks_failures_cleanup_and_retry(self):
        text = SOURCE.read_text()
        macros = '\n'.join(line for line in text.splitlines() if re.match(
            r'#define\s+(PMGR_USB_EHCI|PMGR_USB_OHCI0|USBCPLX_HSIC_EN)\b', line))
        self.assertEqual(len(macros.splitlines()), 3)
        harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define EPROBE_DEFER 517
#define BIT(n) (1u << (n))
#define IS_ERR(p) ((intptr_t)(p) < 0)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
/* SOURCE_MACROS */
struct regulator { int id; };
struct device { int unused; };
struct s5l_usbphy {
 void *pmgr, *usbcplx;
 struct regulator *hsic_supply, *lpo_supply;
 bool hsic_supply_on, lpo_supply_on;
 struct device *dev;
};
struct phy { struct s5l_usbphy *data; };
static struct regulator supplies[2]={{0},{1}};
static int get_errors[2], enable_errors[2], disable_errors[2], gate_errors[2];
static unsigned gets[2], enables[2], disables[2], gates[2], sleeps, writes;
static struct s5l_usbphy *phy_get_drvdata(struct phy *phy) { return phy->data; }
static struct regulator *devm_regulator_get_optional(struct device *dev, const char *name) {
 (void)dev; int i=!strcmp(name,"hsic"); assert(i || !strcmp(name,"lpo"));
 gets[i]++; return get_errors[i] ? ERR_PTR(get_errors[i]) : &supplies[i];
}
static int regulator_enable(struct regulator *r) { enables[r->id]++; return enable_errors[r->id]; }
static int regulator_disable(struct regulator *r) { assert(r); disables[r->id]++; return disable_errors[r->id]; }
static void msleep(unsigned n) { assert(n==10); sleeps++; }
static int s5l_pmgr_on(struct s5l_usbphy *p, unsigned gate) {
 (void)p; int i=gate==PMGR_USB_OHCI0; assert(i || gate==PMGR_USB_EHCI);
 gates[i]++; return gate_errors[i];
}
static uint32_t readl(void *p) { return *(uint32_t *)p; }
static void writel(uint32_t value, void *p) { writes++; *(uint32_t *)p=value; }
''' .replace('/* SOURCE_MACROS */', macros)
        harness += '\n'.join(function(text, name) for name in (
            's5l_supply_disable', 's5l_hostphy_power_on', 's5l_hostphy_power_off'))
        harness += r'''
static void reset(struct s5l_usbphy *p, uint32_t *complex) {
 memset(p,0,sizeof(*p)); *complex=0x100;
 p->usbcplx=complex;
 memset(get_errors,0,sizeof(get_errors)); memset(enable_errors,0,sizeof(enable_errors));
 memset(disable_errors,0,sizeof(disable_errors)); memset(gate_errors,0,sizeof(gate_errors));
 memset(gets,0,sizeof(gets)); memset(enables,0,sizeof(enables));
 memset(disables,0,sizeof(disables)); memset(gates,0,sizeof(gates)); sleeps=writes=0;
}
int main(void) {
 struct s5l_usbphy p; struct phy phy={&p}; uint32_t complex;
 unsigned cases=0;
 reset(&p,&complex);
 assert(!s5l_hostphy_power_on(&phy));
 assert(p.lpo_supply_on && p.hsic_supply_on && enables[0]==1 && enables[1]==1);
 assert(gates[0]==1 && gates[1]==1 && writes==1 && complex==(0x100|USBCPLX_HSIC_EN));
 assert(sleeps==2 && !disables[0] && !disables[1]); cases++;
 assert(!s5l_hostphy_power_on(&phy));
 assert(enables[0]==1 && enables[1]==1 && sleeps==2); cases++;
 assert(!s5l_hostphy_power_off(&phy) && !p.lpo_supply_on && !p.hsic_supply_on);
 assert(disables[0]==1 && disables[1]==1);
 assert(!s5l_hostphy_power_off(&phy) && disables[0]==1 && disables[1]==1); cases++;
 /* Acquisition/enable failures and both PMGR failures must stop before
  * usb-complex writes, undo only acquired supplies, and retain the cause. */
 for (int kind=0; kind<7; kind++) {
  reset(&p,&complex);
  const int errors[]={-EPROBE_DEFER,-ENOMEM,-EIO,-EPROBE_DEFER,-EACCES,-ETIMEDOUT,-EIO};
  int error=errors[kind];
  if (kind<2) get_errors[0]=error;
  if (kind==2) enable_errors[0]=error;
  if (kind==3) get_errors[1]=error;
  if (kind==4) enable_errors[1]=error;
  if (kind>=5) gate_errors[kind-5]=error;
  assert(s5l_hostphy_power_on(&phy)==error && !writes && complex==0x100);
  assert(!p.lpo_supply_on && !p.hsic_supply_on);
  assert(disables[0]==(kind>=3) && disables[1]==(kind>=5));
  if (kind==5) assert(!gates[1]);
  cases++;
 }
 reset(&p,&complex); get_errors[0]=get_errors[1]=-ENODEV;
 assert(!s5l_hostphy_power_on(&phy) && !p.lpo_supply_on && !p.hsic_supply_on);
 assert(!enables[0] && !enables[1] && gates[0]==1 && gates[1]==1); cases++;
 reset(&p,&complex); p.lpo_supply=&supplies[0]; p.hsic_supply=&supplies[1];
 p.lpo_supply_on=p.hsic_supply_on=true; gate_errors[0]=-ETIMEDOUT;
 assert(s5l_hostphy_power_on(&phy)==-ETIMEDOUT);
 assert(p.lpo_supply_on && p.hsic_supply_on && !disables[0] && !disables[1]); cases++;
 reset(&p,&complex); p.lpo_supply=&supplies[0]; p.lpo_supply_on=true;
 gate_errors[0]=-ETIMEDOUT;
 assert(s5l_hostphy_power_on(&phy)==-ETIMEDOUT);
 assert(p.lpo_supply_on && !p.hsic_supply_on && !disables[0] && disables[1]==1); cases++;
 reset(&p,&complex); gate_errors[1]=-ETIMEDOUT; disable_errors[1]=-EIO;
 assert(s5l_hostphy_power_on(&phy)==-ETIMEDOUT);
 assert(!p.lpo_supply_on && p.hsic_supply_on && disables[0]==1 && disables[1]==1); cases++;
 disable_errors[1]=0;
 assert(!s5l_hostphy_power_off(&phy) && !p.hsic_supply_on && disables[1]==2); cases++;
 reset(&p,&complex); assert(!s5l_hostphy_power_on(&phy));
 disable_errors[0]=-ETIMEDOUT; disable_errors[1]=-EIO;
 assert(s5l_hostphy_power_off(&phy)==-EIO && p.lpo_supply_on && p.hsic_supply_on);
 assert(disables[0]==1 && disables[1]==1); cases++;
 disable_errors[1]=0;
 assert(s5l_hostphy_power_off(&phy)==-ETIMEDOUT && p.lpo_supply_on && !p.hsic_supply_on); cases++;
 disable_errors[0]=0;
 assert(!s5l_hostphy_power_off(&phy) && !p.lpo_supply_on); cases++;
 printf("USB PHY power: %u actual callback cases passed\n",cases);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='cascadia-phy-power-') as td:
            source, binary = Path(td) / 'power.c', Path(td) / 'power'
            source.write_text(harness)
            subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra',
                            '-Werror', '-fsanitize=undefined', str(source), '-o', str(binary)],
                           check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()

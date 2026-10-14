from pathlib import Path
import re,resource,shutil,subprocess,tempfile,unittest,os,hashlib
ROOT=Path(os.environ.get('CASCADIA_CURRENT_ROOT',Path(__file__).resolve().parents[1]/'experiments/p105-current'))

def function(s,n):
 pos=re.search(r'\b'+re.escape(n)+r'\(',s).start();a=s.rfind('\n',0,pos)+1;b=s.index('{',pos);depth=1;e=b+1
 while depth:depth+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[a:e]

class Worker(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('gcc'):raise unittest.SkipTest('gcc required')
  src=(ROOT/'apple-d1946-current-only.c').read_text()
  c=r'''
#define main core_original_main
#include "core-fixture.c"
#undef main
#include <stddef.h>
#include <stdint.h>
typedef uint64_t u64;
#define READ_ONCE(x) (x)
#define min(a,b) ((a)<(b)?(a):(b))
#define min_t(t,a,b) min((t)(a),(t)(b))
#define NSEC_PER_SEC 1000000000ULL
#define D_EXPERIMENT_MAX_MA 720
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define dev_err(...) ((void)0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct work_struct {int marker;};
struct delayed_work {struct work_struct work;};
static struct delayed_work *to_delayed_work(struct work_struct *w){return container_of(w,struct delayed_work,work);}
struct mutex {int locked;};
typedef struct {int locked;}spinlock_t;
static void mutex_lock(struct mutex *l){assert(!l->locked);l->locked=1;}
static void mutex_unlock(struct mutex *l){assert(l->locked);l->locked=0;}
static void splock(spinlock_t *l){assert(!l->locked);l->locked=1;}
static void spunlock(spinlock_t *l){assert(l->locked);l->locked=0;}
#define spin_lock_irqsave(l,f) ((f)=0,splock(l))
#define spin_unlock_irqrestore(l,f) ((void)(f),spunlock(l))
static void atomic_inc(unsigned int *e){(*e)++;}
static unsigned int atomic_read(unsigned int *e){return *e;}
struct device {int unused;};struct power_supply {int unused;};
struct d1946_snapshot {u64 generation,sampled_ns,valid_until_ns;int online,budget_ua,present,voltage_uv,temp_decic;};
struct d1946_current_provider {void *context;int(*snapshot)(void *,struct power_supply *,struct power_supply *,struct d1946_snapshot *);bool(*valid)(void *,const struct d1946_snapshot *);};
struct d1946_current {
 struct delayed_work work;struct mutex io_lock;spinlock_t queue_lock;
 struct device *dev;const struct d1946_current_provider *provider;struct power_supply *input,*battery,*psy;
 struct d1946_io io;unsigned int epoch,requested_input,requested_charge,applied_input,applied_charge,applied_epoch,status_epoch;
 bool ready,events_enabled,stopping,fault_latched,applied_valid,status_valid,inhibit_attempted;
 u8 ceiling,status[6];u64 status_time_ns;
};
static unsigned int schedules,pending,snapshots,changes;static int provider_error;
static void *system_wq;
static void mod_delayed_work(void *wq,struct delayed_work *w,unsigned long delay){(void)wq;(void)delay;assert(w->work.marker==123);schedules++;pending=1;}
static unsigned long msecs_to_jiffies(unsigned int t){return t;}
static u64 ktime_get_ns(void){return NSEC_PER_SEC;}
static int failed_snapshot(void *ctx,struct power_supply *i,struct power_supply *b,struct d1946_snapshot *s){(void)ctx;(void)i;(void)b;(void)s;snapshots++;return provider_error;}
static bool denied_valid(void *c,const struct d1946_snapshot *s){(void)c;(void)s;return false;}
static bool owned_usb2_source,allow_usb2_current;
static struct d1946_snapshot positive_sample;
static unsigned int validity_calls,deny_at,invalidate_at,enable_writes,stale_enables;
static bool validator_revoked;
static struct d1946_current *active;
static bool inject_epoch;
/* Explicit positive supplier/PMU fakes test only the worker policy; they are not
 * produced USB permission, battery calibration or an analog-retention proof. */
static int explicit_snapshot(void *ctx,struct power_supply *i,struct power_supply *b,struct d1946_snapshot *s){(void)ctx;(void)i;(void)b;snapshots++;if(provider_error)return provider_error;*s=positive_sample;return 0;}
/* Deliberately return a captured true result after frontend revocation. This
 * models the final validator-return window, not a real source permission. */
static bool explicit_valid(void *c,const struct d1946_snapshot *s){
 (void)c;(void)s;validity_calls++;
 if(validity_calls==invalidate_at){atomic_inc(&active->epoch);validator_revoked=true;}
 return validity_calls!=deny_at;
}
static const struct d1946_current_provider explicit_provider={NULL,explicit_snapshot,explicit_valid};
static int explicit_write(void *ctx,unsigned int reg,const u8 *bytes,unsigned int n){
 int ret=write_fake(ctx,reg,bytes,n);
 if(!ret&&reg==0x3f&&n==1&&!(*bytes&0x40)){
  enable_writes++;if(validator_revoked)stale_enables++;
  if(inject_epoch){inject_epoch=false;active->epoch++;}
 }return ret;
}
static const struct d1946_current_provider denied_provider={NULL,failed_snapshot,denied_valid};
static int d_read(void *ctx,unsigned int reg,u8 *out,unsigned int n){struct d1946_current *d=ctx;return d->io.read(d->io.context,reg,out,n);}
static void power_supply_changed(struct power_supply *p){assert(p);changes++;}
'''
  for name in ['d_queue','d_invalidate','d_fault','d_snapshot_valid','d_profile_floor','d_decoded_input','d_charge_for_input','d_worker']:c+=function(src,name)+'\n'
  c+=r'''
static void init(struct d1946_current *d,struct fake *f){
 memset(d,0,sizeof(*d));setup(f,0xbf);d->io=(struct d1946_io){f,read_fake,write_fake};
 d->ready=d->events_enabled=d->applied_valid=true;d->provider=&denied_provider;d->work.work.marker=123;d->ceiling=63;
 schedules=pending=snapshots=changes=0;provider_error=-EAGAIN;
}
static void fault_test(void){
 struct d1946_current d;struct fake f;init(&d,&f);
 mutex_lock(&d.io_lock);d_fault(&d);d_fault(&d);d_fault(&d);mutex_unlock(&d.io_lock);
 assert(d.fault_latched&&!d.applied_valid&&d.epoch==3&&schedules==1&&pending==1&&f.calls==0);
 mutex_lock(&d.io_lock);d.stopping=true;d_fault(&d);mutex_unlock(&d.io_lock);assert(d.epoch==4&&schedules==1);
 puts("actual repeated fault/epoch/first-only queue fixtures PASS");
}
static void worker_test(void){
 const int errors[]={-EAGAIN,-EIO,-ENODEV};
 for(unsigned int i=0;i<ARRAY_SIZE(errors);i++){
  struct d1946_current d;struct fake f;init(&d,&f);provider_error=errors[i];
  d_worker(&d.work.work);
  assert(d.fault_latched&&d.inhibit_attempted&&!d.applied_valid&&d.epoch==1&&snapshots==1&&schedules==1&&pending==1&&f.calls>0);
  unsigned int calls=f.calls,writes=f.writes;pending=0;
  d_worker(&d.work.work);
  /* No firmware/source grant exists: both attempts received the actual error. */
  assert(snapshots==2&&d.epoch==2&&d.fault_latched&&f.calls==calls&&f.writes==writes);
  assert(schedules==1&&pending==0);
 }
 puts("actual worker two failure iterations/bounded inhibit/no busyloop fixtures PASS");
}

static void make_small(struct d1946_current *d,struct fake *f,unsigned int budget,bool enabled){
 init(d,f);d->provider=&explicit_provider;d->requested_input=500;d->requested_charge=720;d->applied_valid=false;
 d->io.write=explicit_write;active=d;owned_usb2_source=true;allow_usb2_current=enabled;
 positive_sample=(struct d1946_snapshot){.generation=1,.sampled_ns=NSEC_PER_SEC-1,.valid_until_ns=NSEC_PER_SEC+1000,.online=1,.budget_ua=budget,.present=1,.voltage_uv=3900000,.temp_decic=250};
 provider_error=0;validity_calls=deny_at=invalidate_at=enable_writes=stale_enables=0;inject_epoch=validator_revoked=false;f->regs[0x0a]=8;memset(f->regs+0x0b,0,5);
}
static void plans_test(void){
 const unsigned int budgets[]={0,100000,500000};
 const unsigned int inputs[]={0,100,500},currents[]={0,80,480};
 for(unsigned int i=0;i<3;i++)for(unsigned int enabled=0;enabled<=1;enabled++){
  struct d1946_current d;struct fake f;make_small(&d,&f,budgets[i],enabled);d_worker(&d.work.work);
  unsigned int charge=enabled?currents[i]:0;
  assert(d.applied_valid&&!d.fault_latched&&d.applied_input==inputs[i]&&d.applied_charge==charge);
  assert(!!(f.regs[0x3f]&0x40)==!charge);
  if(charge)assert(f.regs[0x4b]==0&&f.regs[0x4d]==0&&f.regs[0x4f]==charge/40&&f.regs[0x51]==charge/40&&f.regs[0x53]==charge/40);
 }
 struct d1946_current d;struct fake f;
 for(unsigned int request=0;request<=720;request+=40){
  make_small(&d,&f,500000,true);d.requested_charge=request;d_worker(&d.work.work);
  assert(d.applied_charge==min(request,480)&&d.applied_charge<=500&&d.applied_charge%40==0);
 }
 make_small(&d,&f,500000,true);d.requested_charge=100;d_worker(&d.work.work);assert(d.applied_charge==80);
 make_small(&d,&f,500000,true);d.ceiling=1;d_worker(&d.work.work);assert(d.applied_charge==40&&f.regs[0x4f]==1&&f.regs[0x4b]==0&&f.regs[0x4d]==0);
 make_small(&d,&f,600000,true);d_worker(&d.work.work);assert(d.applied_charge==0);
 make_small(&d,&f,500000,true);owned_usb2_source=false;d_worker(&d.work.work);assert(d.applied_charge==0);
 make_small(&d,&f,1000000,true);owned_usb2_source=false;d.requested_input=1000;d_worker(&d.work.work);assert(d.applied_charge==720&&d.applied_input==975);
 puts("actual worker defaultoff/owned100and500/rounding/ceiling/legacy fixtures PASS");
}
static void stale_test(void){
 struct d1946_current d;struct fake f;
 for(unsigned int at=1;at<=3;at++){
  make_small(&d,&f,500000,true);deny_at=at;d_worker(&d.work.work);
  assert(!d.applied_valid&&(f.regs[0x3f]&0x40));
  if(at==1)assert(d.fault_latched);
 }
 make_small(&d,&f,500000,true);positive_sample.valid_until_ns=NSEC_PER_SEC;d_worker(&d.work.work);assert(d.fault_latched&&(f.regs[0x3f]&0x40));
 make_small(&d,&f,500000,true);inject_epoch=true;d_worker(&d.work.work);assert(!d.applied_valid&&(f.regs[0x3f]&0x40)&&d.epoch==1);
 puts("actual worker stale/expiry/epochduringenable fixtures PASS");
}
static void health_test(void){
 struct d1946_current d;struct fake f;
 const int temperatures[]={99,451};
 for(unsigned int i=0;i<2;i++){make_small(&d,&f,500000,true);positive_sample.temp_decic=temperatures[i];d_worker(&d.work.work);assert(d.applied_charge==0&&d.applied_input==0&&(f.regs[0x3f]&0x40));}
 make_small(&d,&f,500000,true);positive_sample.present=0;d_worker(&d.work.work);assert(!d.applied_charge&&(f.regs[0x3f]&0x40));
 make_small(&d,&f,500000,true);positive_sample.online=0;d_worker(&d.work.work);assert(!d.applied_charge&&(f.regs[0x3f]&0x40));
 for(unsigned int bit=3;bit<=5;bit++){make_small(&d,&f,500000,true);f.regs[0x0b]=1U<<bit;d_worker(&d.work.work);assert(d.fault_latched&&d.inhibit_attempted&&!d.applied_valid&&(f.regs[0x3f]&0x40));}
 puts("actual worker absent/offline/thermal/statusfault fixtures PASS");
}
static void failures_test(void){
 struct d1946_current d;struct fake f;make_small(&d,&f,500000,true);d_worker(&d.work.work);unsigned int length=f.calls;
 for(unsigned int at=1;at<=length;at++){
  make_small(&d,&f,500000,true);f.fail_at=at;d_worker(&d.work.work);
  assert(d.fault_latched&&d.inhibit_attempted&&!d.applied_valid&&(f.regs[0x3f]&0x40));
 }
 const int errors[]={-EAGAIN,-EIO,-ENODEV};
 for(unsigned int i=0;i<3;i++){
  make_small(&d,&f,500000,true);provider_error=errors[i];d_worker(&d.work.work);
  assert(d.fault_latched&&d.inhibit_attempted&&(f.regs[0x3f]&0x40));unsigned int calls=f.calls,queued=schedules;
  d_worker(&d.work.work);assert(f.calls==calls&&schedules==queued);
 }
 puts("actual worker everytransportfailure/noGrant/boundedretry fixtures PASS");
}
/* Three distinct callback windows; the register fake records actual core
 * writes. No timing sleeps, UDC grant, PMU or physical safety is emulated. */
static void validator_epoch_test(const char *phase){
 struct d1946_current d;struct fake f;make_small(&d,&f,500000,true);
 d.epoch=7;
 if(!strcmp(phase,"validator-fast")){
  d.applied_valid=true;d.applied_epoch=7;d.applied_input=500;d.applied_charge=480;
  invalidate_at=2;
 }else if(!strcmp(phase,"validator-pre"))invalidate_at=2;
 else{assert(!strcmp(phase,"validator-post"));invalidate_at=3;}
 d_worker(&d.work.work);
 assert(validator_revoked&&d.epoch==8&&!d.fault_latched);
 if(!strcmp(phase,"validator-fast"))
  assert(!d.applied_valid&&"validator_epoch_fastpath");
 else if(!strcmp(phase,"validator-pre"))
  assert(!stale_enables&&"validator_epoch_preenable");
 else
  assert((f.regs[0x3f]&0x40)&&"validator_epoch_postenable");
 assert(!d.applied_valid&&(f.regs[0x3f]&0x40));
 assert(validity_calls==invalidate_at&&stale_enables==0);
 if(!strcmp(phase,"validator-post"))assert(enable_writes==1);
 else assert(enable_writes==0);
 puts("actual worker callback-spanning epoch fixtures PASS");
}
int main(int argc,char **argv){assert(argc==2);if(!strncmp(argv[1],"validator-",10))validator_epoch_test(argv[1]);else if(!strcmp(argv[1],"plans"))plans_test();else if(!strcmp(argv[1],"stale"))stale_test();else if(!strcmp(argv[1],"health"))health_test();else if(!strcmp(argv[1],"errors"))failures_test();else if(!strcmp(argv[1],"fault"))fault_test();else worker_test();}
'''
  cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name);(p/'test.c').write_text(c);cls.bin=p/'test';cls.old=p/'historical-test';cls.epoch_old=p/'historical-epoch-test'
  old=(ROOT/'historical-d-fault.c').read_text()
  (p/'historical.c').write_text(c.replace(function(src,'d_fault'),function(old,'d_fault')))
  epoch_old=(ROOT/'historical-d-worker-epoch.c').read_text()
  assert hashlib.sha256(epoch_old.encode()).hexdigest()=='1501b8fb2b96241621eb10c83efe124bfcb2fb5ef7845bc0dfde0b19a5a90256'
  (p/'historical-epoch.c').write_text(c.replace(function(src,'d_worker'),function(epoch_old,'d_worker')))
  for source,target in [('test.c',cls.bin),('historical.c',cls.old),('historical-epoch.c',cls.epoch_old)]:
   subprocess.run(['gcc','-DCASCADIA_OFFLINE','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(ROOT),str(p/source),str(ROOT/'d1946-current-core.c'),'-o',str(target)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def run_case(self,name):self.assertIn('fixtures PASS',subprocess.check_output([str(self.bin),name],text=True,timeout=10))
 def test_actual_defaultoff_optin_owned_small_profile(self):self.run_case('plans')
 def test_actual_source_stale_and_epoch_race(self):self.run_case('stale')
 def test_actual_thermal_absent_and_status_fault(self):self.run_case('health')
 def test_actual_all_io_failures_no_grant_bounded_retry(self):self.run_case('errors')
 def test_actual_first_fault_queue_and_epoch(self):self.assertIn('fixtures PASS',subprocess.check_output([str(self.bin),'fault'],text=True))
 def test_actual_two_worker_failure_iterations(self):self.assertIn('fixtures PASS',subprocess.check_output([str(self.bin),'worker'],text=True))
 def test_historical_worker_selfrequeue_is_rejected(self):
  def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))
  result=subprocess.run([str(self.old),'worker'],text=True,capture_output=True,preexec_fn=no_core)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('schedules==1&&pending==0',result.stderr)
 def test_actual_validator_fastpath_epoch(self):self.run_case('validator-fast')
 def test_actual_validator_preenable_epoch(self):self.run_case('validator-pre')
 def test_actual_validator_postenable_epoch(self):self.run_case('validator-post')
 def historical_epoch_case(self,phase,marker):
  def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))
  result=subprocess.run([str(self.epoch_old),phase],text=True,capture_output=True,preexec_fn=no_core,timeout=10)
  self.assertNotEqual(result.returncode,0)
  self.assertIn(marker,result.stderr)
 def test_historical_validator_fastpath_epoch(self):self.historical_epoch_case('validator-fast','validator_epoch_fastpath')
 def test_historical_validator_preenable_epoch(self):self.historical_epoch_case('validator-pre','validator_epoch_preenable')
 def test_historical_validator_postenable_epoch(self):self.historical_epoch_case('validator-post','validator_epoch_postenable')
if __name__=='__main__':unittest.main()

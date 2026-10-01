import { execFileSync } from "node:child_process";
import type { Browser, TestInfo } from "@playwright/test";
import { memoryMethod, probeHost, projectPython, workerIdentity } from "./host.ts";

type ProcessMemory = { id: number; parent_id: number; name: string; working_set_mib: number; private_mib: number | null; unique_set_mib: number | null };
type Snapshot = { timestamp_utc: string; available_gib: number; host_cpu_percent: number; worker: ProcessMemory; chromium: ProcessMemory[]; errors: string[] };

/** Préfixes des processus Chromium de Playwright : `chrome*.exe` sous Windows ; sous Linux, le headless shell s'appelle aussi `headless_shell`. */
const CHROMIUM_PREFIXES = { win32: ["chrome"], linux: ["chrome", "chromium", "headless_shell"] } as const;

export async function monitorBrowser(browser: Browser, phase: string, info: TestInfo): Promise<Snapshot> {
  const host = probeHost();
  // Fixed read-only psutil probe of this live Node test worker and only its
  // Chromium descendants. PID, worker identity and prefixes are argv values, never shell interpolation.
  // Windows private is committed private memory; USS is separately measured (Windows and Linux).
  const source = `import datetime,json,os,sys,psutil
owner=psutil.Process(int(sys.argv[1]))
kind,expected=sys.argv[2].split(':',1)
actual=owner.name().casefold() if kind=='name' else os.path.realpath(owner.exe())
if actual!=(expected if kind=='name' else os.path.realpath(expected)): raise RuntimeError('Qualification owner is not the live Node worker')
prefixes=tuple(sys.argv[3].split(','))
errors=[]
def sample(p):
    with p.oneshot():
        memory=p.memory_info()
        value={'id':p.pid,'parent_id':p.ppid(),'name':p.name(),'working_set_mib':round(memory.rss/1048576,1),'private_mib':round(memory.private/1048576,1) if hasattr(memory,'private') else None,'unique_set_mib':None}
    try: value['unique_set_mib']=round(p.memory_full_info().uss/1048576,1)
    except (psutil.Error,AttributeError) as error: errors.append(type(error).__name__+': USS unavailable for owned PID '+str(p.pid))
    return value
chromium=[]
for child in owner.children(recursive=True):
    try:
        if child.name().casefold().startswith(prefixes): chromium.append(sample(child))
    except psutil.Error as error: errors.append(type(error).__name__+': owned child exited or unavailable')
print(json.dumps({'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'available_gib':round(psutil.virtual_memory().available/1073741824,3),'host_cpu_percent':psutil.cpu_percent(interval=0.1),'worker':sample(owner),'chromium':chromium,'errors':errors}))`;
  const raw = execFileSync(projectPython(host), ["-c", source, String(process.pid), workerIdentity(host), CHROMIUM_PREFIXES[host].join(",")], { encoding: "utf8", timeout: 15000, windowsHide: true });
  const snapshot = JSON.parse(raw.trim()) as Snapshot;
  await info.attach(`resources-${phase}`, { body: Buffer.from(JSON.stringify({ phase, ...snapshot, method: memoryMethod(host) }, null, 2)), contentType: "application/json" });
  if (snapshot.available_gib < 1.5) {
    await browser.close();
    throw new Error(`Host RAM ${snapshot.available_gib} GiB below 1.5 GiB; closed only this test browser.`);
  }
  return snapshot;
}

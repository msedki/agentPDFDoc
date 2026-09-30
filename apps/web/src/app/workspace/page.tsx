import { SessionGate } from "@/components/session-gate";
import { Workspace } from "@/components/workspace";
export default function Page() { return <SessionGate><Workspace /></SessionGate>; }

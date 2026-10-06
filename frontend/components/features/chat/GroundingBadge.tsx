import { Badge } from "@/components/ui/badge";
import type { AgentGrounding } from "@/lib/api";

export function PrivateBadge() {
  return <Badge variant="warn">Private repo</Badge>;
}

export function GroundingBadge({ grounding }: { grounding: AgentGrounding }) {
  if (grounding.status === "grounded") return <Badge variant="success">Grounded</Badge>;
  if (grounding.status === "partial") {
    return <Badge variant="warn">Partially grounded — see gaps</Badge>;
  }
  return null;
}

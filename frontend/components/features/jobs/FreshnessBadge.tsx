import { Badge } from "@/components/ui/badge";

const STALE_DAYS = 30;

export function staleness(posting: {
  expires_at: string | null | undefined;
  posted_at: string | null | undefined;
}): { label: string; variant: "neutral" | "warn" } | null {
  if (posting.expires_at) {
    return {
      label: `Expires ${new Date(posting.expires_at).toLocaleDateString()}`,
      variant: "neutral",
    };
  }
  if (!posting.posted_at) return null;
  const posted = new Date(posting.posted_at);
  if (Number.isNaN(posted.getTime())) return null;
  const days = (Date.now() - posted.getTime()) / 86_400_000;
  return days > STALE_DAYS ? { label: "Stale", variant: "warn" } : null;
}

export function FreshnessBadge({
  expiresAt,
  postedAt,
}: {
  expiresAt: string | null | undefined;
  postedAt: string | null | undefined;
}) {
  const freshness = staleness({ expires_at: expiresAt, posted_at: postedAt });
  if (freshness === null) return null;
  return <Badge variant={freshness.variant}>{freshness.label}</Badge>;
}

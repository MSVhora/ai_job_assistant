import Link from "next/link";

import { Card } from "@/components/ui/card";
import type { SourceInfo } from "@/lib/api";

export function JobsNotices({
  setupWarnings,
  unconfigured,
}: {
  setupWarnings: string[];
  unconfigured: SourceInfo[];
}) {
  return (
    <>
      {setupWarnings.length > 0 && (
        <Card title="Provider setup incomplete">
          <ul className="list-inside list-disc text-sm text-amber-800">
            {setupWarnings.map((warning) => (
              <li key={warning} role="alert">
                {warning}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-sm text-gray-600">
            Fix this before your first search —{" "}
            <Link
              href="/setup"
              className="font-medium text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              go to setup
            </Link>
            .
          </p>
        </Card>
      )}
      {unconfigured.length > 0 && (
        <Card title="Sources missing their API key">
          <p role="alert" className="text-sm text-amber-800">
            Enabled but unconfigured: {unconfigured.map((source) => source.name).join(", ")}. Their
            searches will fail until the key is set in <code>.env</code> —{" "}
            <Link
              href="/setup"
              className="font-medium text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              go to setup
            </Link>
            .
          </p>
        </Card>
      )}
    </>
  );
}

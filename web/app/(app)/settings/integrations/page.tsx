"use client";

import { IntegrationConnectionsCard } from "@/components/integrations";
import { PageHeading } from "@/components/shell";

export default function IntegrationsSettingsPage() {
  return (
    <>
      <PageHeading
        title="Integrations"
        description="Connect the tools you already use so they show up on a contract — a scheduled call, or a read-only glance at recent progress."
      />
      <IntegrationConnectionsCard />
    </>
  );
}

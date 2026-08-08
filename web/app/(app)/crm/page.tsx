"use client";

import * as React from "react";

import { ContactsPanel, PipelinePanel, TasksPanel } from "@/components/crm";
import { PlanBadge, UsageMeter, useEntitlements } from "@/components/professional";
import { PageHeading } from "@/components/shell";
import { Alert, Card, Segmented } from "@/components/ui";
import { UNLIMITED, professional } from "@/lib/api";
import { useLoader } from "@/lib/session";

type Tab = "pipeline" | "contacts" | "tasks";

export default function CrmPage() {
  const [tab, setTab] = React.useState<Tab>("pipeline");
  const { rights } = useEntitlements();

  // Owned here rather than inside the pipeline panel: the contact ceiling is
  // shown above the tabs, so the count has to survive switching away from the
  // tab that would otherwise have fetched it.
  const summary = useLoader(() => professional.pipeline(), []);
  const refresh = React.useCallback(() => void summary.reload(), [summary]);

  const capped = rights && rights.crm_contact_limit !== UNLIMITED;

  return (
    <>
      <PageHeading
        title="Clients"
        description="Your pipeline, your contacts, and what you owe them next — covering the clients you found here and the ones you did not."
        action={rights && <PlanBadge tier={rights.tier} name={rights.plan_name} />}
      />

      {summary.error && <Alert tone="critical" className="mb-6">{summary.error}</Alert>}

      {/* Shown before the limit is hit rather than at the moment of refusal:
          this is the only ceiling a free user reaches by accident. */}
      {capped && summary.data && (
        <Card className="mb-6 p-5">
          <UsageMeter
            used={summary.data.contacts}
            limit={rights.crm_contact_limit}
            label="Contacts used on your plan"
          />
        </Card>
      )}

      <div className="pb-6">
        <Segmented
          label="CRM section"
          value={tab}
          onChange={setTab}
          options={[
            { value: "pipeline", label: "Pipeline", icon: "chart" },
            { value: "contacts", label: "Contacts", icon: "users" },
            { value: "tasks", label: "Follow-ups", icon: "check" },
          ]}
        />
      </div>

      {tab === "pipeline" && <PipelinePanel summary={summary.data} onChanged={refresh} />}
      {tab === "contacts" && <ContactsPanel onChanged={refresh} />}
      {tab === "tasks" && <TasksPanel onChanged={refresh} />}
    </>
  );
}

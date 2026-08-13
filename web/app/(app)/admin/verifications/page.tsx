"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Segmented,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { admin, type AdminVerification } from "@/lib/api";
import { useAsyncAction, useLoader } from "@/lib/session";

const STATUS_TABS = [
  { value: "under_review", label: "Awaiting review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
] as const;

function VerificationRow({
  application,
  onDecided,
}: {
  application: AdminVerification;
  onDecided: () => void;
}) {
  const [rejecting, setRejecting] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const approve = useAsyncAction(admin.approveVerification);
  const reject = useAsyncAction(admin.rejectVerification);

  const pending = application.status === "under_review";

  return (
    <li className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[14px] font-medium text-fg">{application.applicant_name}</p>
          <p className="text-[12.5px] text-muted">
            {application.applicant_handle} · {application.applicant_email}
          </p>
          <p className="mt-1.5 text-[12.5px] text-fg">
            {application.university_name}
            <span className="text-muted"> — {application.university_email}</span>
          </p>
        </div>
        <Badge
          tone={
            application.status === "approved"
              ? "positive"
              : application.status === "rejected"
                ? "critical"
                : "accent"
          }
        >
          {application.status.replace("_", " ")}
        </Badge>
      </div>

      {application.id_card_url ? (
        <a
          href={application.id_card_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-accent hover:underline"
        >
          <Icon name="id" className="size-3.5" />
          View submitted ID card
        </a>
      ) : (
        <p className="mt-3 text-[12.5px] text-subtle">No ID card on file yet.</p>
      )}

      {application.status === "rejected" && application.rejection_reason && (
        <p className="mt-3 rounded-md border border-line bg-sunken p-3 text-[13px] text-muted">
          {application.rejection_reason}
        </p>
      )}

      {pending && (
        <div className="mt-4 border-t border-line pt-4">
          {rejecting ? (
            <div className="space-y-3">
              <Textarea
                placeholder="Why is this being rejected? Shown to the applicant verbatim."
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  loading={reject.pending}
                  disabled={!reason.trim()}
                  onClick={async () => {
                    if (await reject.run(application.id, reason)) onDecided();
                  }}
                >
                  Confirm rejection
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>
                  Cancel
                </Button>
              </div>
              {reject.error && <p className="text-[12.5px] text-critical">{reject.error}</p>}
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                loading={approve.pending}
                onClick={async () => {
                  if (await approve.run(application.id)) onDecided();
                }}
              >
                Approve
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setRejecting(true)}>
                Reject
              </Button>
              {approve.error && <p className="text-[12.5px] text-critical">{approve.error}</p>}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function AdminVerificationsPage() {
  const [tab, setTab] = React.useState<(typeof STATUS_TABS)[number]["value"]>("under_review");
  const queue = useLoader(() => admin.verifications(tab), [tab]);
  const rows = queue.data?.results ?? [];

  return (
    <>
      <PageHeading
        title="Verification queue"
        description="Prove membership of a university — an applicant's email and ID card, reviewed by a person."
      />

      <div className="mb-6">
        <Segmented
          label="Verification status"
          value={tab}
          onChange={setTab}
          options={STATUS_TABS.map((t) => ({ value: t.value, label: t.label }))}
        />
      </div>

      {queue.loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-32" />
          ))}
        </div>
      ) : queue.error ? (
        <Alert tone="critical">{queue.error}</Alert>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="id" className="size-5" />}
            title="Nothing here"
            description="No applications in this state right now."
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {rows.map((application) => (
              <VerificationRow
                key={application.id}
                application={application}
                onDecided={() => void queue.reload()}
              />
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

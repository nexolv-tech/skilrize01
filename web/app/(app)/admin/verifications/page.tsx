"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  AdminTabs,
  PersonLink,
  QuickAction,
  StatusText,
} from "@/components/admin";
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
import { admin, type AdminIdentityCase, type AdminVerification } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

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

/* -------------------------------------------------------------------------- */
/* Identity (CNIC)                                                            */
/* -------------------------------------------------------------------------- */

const IDENTITY_STATES = [
  { value: "pending", label: "Awaiting review" },
  { value: "verified", label: "Approved" },
  { value: "rejected", label: "Rejected" },
] as const;

function IdentityRow({ row, onDecided }: { row: AdminIdentityCase; onDecided: () => void }) {
  return (
    <div className="grid gap-5 p-5 md:grid-cols-[minmax(0,1fr)_16rem]">
      <div className="min-w-0 space-y-2">
        <p className="text-[13.5px]">
          <PersonLink person={row.user} />
        </p>
        <p className="text-[12.5px] text-muted">
          Joined {formatRelative(row.joined_at)}
          {row.submitted_at && <> · submitted {formatRelative(row.submitted_at)}</>} · email{" "}
          {row.email_verified ? "confirmed" : "not confirmed"} · phone{" "}
          {row.phone_verified ? "confirmed" : "not confirmed"}
        </p>
        <p className="text-[12.5px] text-muted">
          Check that the name matches the account, the photo is of the card itself rather
          than a screen, and every corner is visible.
        </p>
        {row.status === "pending" ? (
          <div className="flex flex-wrap items-start gap-2 pt-1">
            <QuickAction
              label="Approve"
              variant="primary"
              icon="check"
              onRun={async () => {
                await admin.approveIdentity(row.user.id);
                onDecided();
              }}
            />
            <ActionWithInput
              label="Reject"
              confirmLabel="Reject"
              tone="danger"
              prompt="Why? This is sent to the member, who can upload again."
              placeholder="e.g. The photo is blurred and the name cannot be read."
              onConfirm={async (reason) => {
                await admin.rejectIdentity(row.user.id, reason);
                onDecided();
              }}
            />
          </div>
        ) : (
          <StatusText tone={row.status === "verified" ? "positive" : "critical"}>
            {row.status === "verified" ? "Approved" : "Rejected"}
          </StatusText>
        )}
      </div>
      <div>
        {row.document_url ? (
          <a href={row.document_url} target="_blank" rel="noreferrer" className="block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={row.document_url}
              alt={`Identity document of ${row.user.name}`}
              className="max-h-44 w-full rounded-md border border-line bg-sunken object-contain"
            />
            <span className="mt-1.5 block text-[12px] text-accent">Open full size</span>
          </a>
        ) : (
          <p className="grid h-32 place-items-center rounded-md border border-dashed border-line px-3 text-center text-[12.5px] text-subtle">
            {row.document_scan === "pending"
              ? "The document is still being virus-scanned."
              : "The document could not be shown."}
          </p>
        )}
      </div>
    </div>
  );
}

function IdentityTab() {
  const [state, setState] = React.useState<(typeof IDENTITY_STATES)[number]["value"]>("pending");
  const [page, setPage] = React.useState(1);
  const queue = useLoader(() => admin.identityQueue(state, page), [state, page]);
  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Identity status"
          size="sm"
          value={state}
          onChange={(next) => {
            setState(next);
            setPage(1);
          }}
          options={IDENTITY_STATES.map((t) => ({ value: t.value, label: t.label }))}
        />
        <p className="text-[12.5px] text-subtle">Opening this list is recorded in the audit log.</p>
      </div>
      <AdminList
        data={queue.data}
        loading={queue.loading}
        page={page}
        onPage={setPage}
        empty={{
          icon: "id",
          title: state === "pending" ? "No identity checks waiting" : "Nothing here yet",
          description:
            state === "pending"
              ? "A member appears here after uploading a photo of their CNIC."
              : undefined,
        }}
      >
        {(row: AdminIdentityCase) => (
          <IdentityRow key={row.user.id} row={row} onDecided={() => void queue.reload()} />
        )}
      </AdminList>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Students                                                                   */
/* -------------------------------------------------------------------------- */

function StudentsTab() {
  const [tab, setTab] = React.useState<(typeof STATUS_TABS)[number]["value"]>("under_review");
  const queue = useLoader(() => admin.verifications(tab), [tab]);
  const rows = queue.data?.results ?? [];

  return (
    <>
      <div className="mb-5">
        <Segmented
          label="Verification status"
          size="sm"
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

function VerificationsContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = params.get("tab") === "students" ? "students" : "identity";
  const { data: overview } = useLoader(() => admin.overview(), [tab]);

  return (
    <>
      <AdminHeading
        title="Verifications"
        description="People prove who they are before they can buy, sell or get paid: a CNIC for everyone, and a student ID for campus portals."
      />
      <AdminTabs
        label="Verification type"
        value={tab}
        onChange={(next) =>
          router.replace(next === "identity" ? pathname : `${pathname}?tab=${next}`, {
            scroll: false,
          })
        }
        tabs={[
          { value: "identity", label: "Identity (CNIC)", count: overview?.queues.identity },
          { value: "students", label: "Students", count: overview?.queues.students },
        ]}
      />
      {tab === "identity" ? <IdentityTab /> : <StudentsTab />}
    </>
  );
}

export default function AdminVerificationsPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <VerificationsContent />
    </React.Suspense>
  );
}

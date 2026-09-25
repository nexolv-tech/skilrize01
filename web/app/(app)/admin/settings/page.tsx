"use client";

import * as React from "react";

import { AdminHeading } from "@/components/admin";
import { Card, CardHeader, Icon, Skeleton, cn } from "@/components/ui";
import { admin } from "@/lib/api";
import { useLoader } from "@/lib/session";

function Line({
  label,
  value,
  ok,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  ok?: boolean;
  hint?: string;
}) {
  return (
    <div className="grid gap-1 px-5 py-3.5 sm:grid-cols-[14rem_1fr]">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="text-[13.5px] text-fg">
        <span className="inline-flex items-center gap-2">
          {ok !== undefined && (
            <Icon
              name={ok ? "check" : "x"}
              className={cn("size-4", ok ? "text-positive" : "text-caution")}
            />
          )}
          {value}
        </span>
        {hint && <span className="mt-0.5 block text-[12.5px] text-subtle">{hint}</span>}
      </dd>
    </div>
  );
}

export default function AdminSettingsPage() {
  const { data } = useLoader(() => admin.settings(), []);

  return (
    <>
      <AdminHeading
        title="Settings"
        description="How this server is set up. These values live in deploy/production.env on the server; change one there and redeploy. They are deliberately not editable from a web page."
      />
      {!data ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader title="Payments" />
            <dl className="divide-y divide-line">
              <Line
                label="Bank account shown to buyers"
                ok={data.bank_transfer.available}
                value={
                  data.bank_transfer.available
                    ? `${data.bank_transfer.bank_name} · ${data.bank_transfer.account_title} · ending ${data.bank_transfer.account_number_last4}`
                    : "Not set"
                }
                hint={
                  data.bank_transfer.available
                    ? undefined
                    : "Checkout cannot take payments until PLATFORM_BANK_NAME, PLATFORM_BANK_ACCOUNT_TITLE and PLATFORM_BANK_ACCOUNT_NUMBER are set."
                }
              />
              <Line label="Commission" value={`${data.commission_percent}% of each release`} />
            </dl>
          </Card>

          <Card>
            <CardHeader title="Email" />
            <dl className="divide-y divide-line">
              <Line
                label="Sending"
                ok={data.email.sending}
                value={data.email.sending ? "Emails are sent" : "Emails are not being sent"}
                hint={data.email.sending ? undefined : "Set EMAIL_HOST and its credentials."}
              />
              <Line label="From address" value={data.email.from} />
            </dl>
          </Card>

          <Card>
            <CardHeader title="Security" />
            <dl className="divide-y divide-line">
              <Line
                label="New-device hold"
                value={`${data.security.device_hold_minutes} minutes before a new device can move money`}
              />
              <Line
                label="Emailed code on a new device"
                ok={data.security.new_device_email_code}
                value={data.security.new_device_email_code ? "On" : "Off"}
              />
              <Line
                label="Phone verification required"
                value={data.security.phone_verification_required ? "Yes" : "No"}
                hint={
                  data.security.phone_verification_required
                    ? undefined
                    : "Off until an SMS provider is connected."
                }
              />
              <Line
                label="Virus scanning of uploads"
                ok={data.security.virus_scanner_required}
                value={data.security.virus_scanner_required ? "Required" : "Not required"}
              />
              <Line
                label="Error reporting"
                ok={data.error_reporting}
                value={data.error_reporting ? "Connected" : "Not connected"}
                hint={data.error_reporting ? undefined : "Set SENTRY_DSN to be told about errors."}
              />
            </dl>
          </Card>

          <Card>
            <CardHeader title="Connected accounts" />
            <dl className="divide-y divide-line">
              {data.integrations.map((row) => (
                <Line
                  key={row.provider}
                  label={row.label}
                  ok={row.enabled}
                  value={row.enabled ? "Members can connect it" : "Coming soon"}
                />
              ))}
            </dl>
            <p className="border-t border-line px-5 py-3.5 text-[12.5px] text-subtle">
              Step 10 of deploy/README.md explains how to switch each one on.
            </p>
          </Card>

          <p className="text-[12.5px] text-subtle">Environment: {data.environment}</p>
        </div>
      )}
    </>
  );
}

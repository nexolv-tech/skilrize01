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
                label="Online payments (Swich)"
                ok={data.payments.available}
                value={
                  data.payments.available
                    ? `Taking payments · Swich ${data.payments.environment}`
                    : "Not taking payments yet"
                }
                hint={
                  data.payments.available
                    ? undefined
                    : "Checkout says payments are opening shortly until SWICH_ENABLED, SWICH_CLIENT_ID and SWICH_SECRET_KEY are set."
                }
              />
              <Line
                label="Payouts and refunds (Swich)"
                ok={data.payments.payouts}
                value={
                  data.payments.payouts
                    ? `Sent automatically${data.payments.payout_balance !== null ? ` · balance Rs ${Number(data.payments.payout_balance).toLocaleString()}` : ""}`
                    : "Sent by hand from Payments"
                }
                hint={
                  data.payments.payouts
                    ? "Keep the Swich payout balance funded: payouts are paid from it."
                    : "Set SWICH_PAYOUTS_ENABLED once Swich has whitelisted this server's IP address and funded the payout balance."
                }
              />
              <Line
                label="Callback URL for Swich"
                value={<span className="break-all font-mono text-[12.5px]">{data.payments.callback_url}</span>}
                hint="Register this in the Swich merchant portal: it is how Swich confirms each payment."
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

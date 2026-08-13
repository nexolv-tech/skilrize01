"use client";

/**
 * Third-party integrations — Phase 10.
 *
 * `IntegrationConnectionsCard` is the account-wide connect/disconnect surface
 * (lives on `/settings/integrations`). `MeetingsPanel` and `ActivityFeedPanel`
 * are contract-scoped and rendered on a contract's own page — a meeting or an
 * activity source always belongs to one contract, never to the account as a
 * whole.
 *
 * Every provider can come back `is_enabled: false` — no OAuth app has real
 * credentials in this environment yet (see `integrations.providers` in the
 * API, and `ZOOM_ENABLED` etc. in the backend settings). The UI treats that
 * as a normal, expected state ("Not available yet"), not an error.
 */

import * as React from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Select,
} from "@/components/ui";
import {
  integrations,
  type ActivityProvider,
  type IntegrationProvider,
  type MeetingProvider,
} from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Account-wide connections                                                   */
/* -------------------------------------------------------------------------- */

export function IntegrationConnectionsCard() {
  const { data, loading, reload } = useLoader(() => integrations.providers(), []);
  const rows = data ?? [];

  const connect = useAsyncAction(async (provider: IntegrationProvider) => {
    const { authorize_url: authorizeUrl } = await integrations.authorize(provider);
    window.location.href = authorizeUrl;
  });

  const disconnect = useAsyncAction(async (provider: IntegrationProvider) => {
    await integrations.disconnect(provider);
    await reload();
  });

  return (
    <Card>
      <CardHeader
        title="Connected accounts"
        description="Link Zoom or Google Meet to schedule calls from a contract, or GitHub/Figma/Notion to show a client read-only progress activity."
      />
      {connect.error && (
        <div className="px-5 pt-4">
          <Alert tone="critical">{connect.error}</Alert>
        </div>
      )}
      {loading ? (
        <div className="p-5 text-[13px] text-muted">Loading…</div>
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((row) => (
            <li key={row.provider} className="flex items-center gap-3 px-5 py-4">
              <span className="grid size-9 shrink-0 place-items-center rounded-md bg-sunken text-muted">
                <Icon name="link" className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[13.5px] font-medium text-fg">{row.label}</p>
                <p className="truncate text-[12px] text-muted">
                  {row.is_connected
                    ? (row.external_label || "Connected")
                    : row.is_enabled
                      ? "Not connected"
                      : "Not available yet in this environment"}
                </p>
              </div>
              {row.is_connected ? (
                <Button
                  size="sm"
                  variant="ghost"
                  loading={disconnect.pending}
                  onClick={() => void disconnect.run(row.provider)}
                >
                  Disconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!row.is_enabled}
                  loading={connect.pending}
                  onClick={() => void connect.run(row.provider)}
                >
                  Connect
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Meetings                                                                   */
/* -------------------------------------------------------------------------- */

const MEETING_PROVIDERS: Array<{ value: MeetingProvider; label: string }> = [
  { value: "zoom", label: "Zoom" },
  { value: "google_meet", label: "Google Meet" },
];

export function MeetingsPanel({ contractId }: { contractId: number }) {
  const { data, loading, reload } = useLoader(() => integrations.meetings(contractId), [contractId]);
  const meetings = data ?? [];

  const [provider, setProvider] = React.useState<MeetingProvider>("zoom");
  const [topic, setTopic] = React.useState("");
  const [startTime, setStartTime] = React.useState("");

  const schedule = useAsyncAction(async () => {
    await integrations.scheduleMeeting(contractId, {
      provider,
      topic,
      start_time: new Date(startTime).toISOString(),
    });
    setTopic("");
    setStartTime("");
    await reload();
  });

  const cancel = useAsyncAction(async (meetingId: number) => {
    await integrations.cancelMeeting(meetingId);
    await reload();
  });

  return (
    <Card>
      <CardHeader
        title="Meetings"
        description="Schedule a real Zoom or Google Meet call tied to this contract."
      />

      <div className="p-5">
        {loading ? (
          <p className="text-[13px] text-muted">Loading…</p>
        ) : meetings.length === 0 ? (
          <EmptyState
            icon={<Icon name="video" className="size-5" />}
            title="No meetings scheduled"
            description="Whoever connects Zoom or Google Meet in Settings → Integrations can schedule one below."
          />
        ) : (
          <ul className="space-y-3">
            {meetings.map((meeting) => (
              <li
                key={meeting.id}
                className="flex items-center justify-between gap-3 rounded-md border border-line p-3.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-medium text-fg">{meeting.topic}</p>
                  <p className="text-[12px] text-muted">
                    {MEETING_PROVIDERS.find((p) => p.value === meeting.provider)?.label} ·{" "}
                    {new Date(meeting.start_time).toLocaleString()} · {meeting.duration_minutes} min
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {meeting.status === "scheduled" ? (
                    <>
                      <a href={meeting.join_url} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="secondary">
                          Join
                        </Button>
                      </a>
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={cancel.pending}
                        onClick={() => void cancel.run(meeting.id)}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Badge>Cancelled</Badge>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <form
        className="space-y-4 border-t border-line p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void schedule.run();
        }}
      >
        {schedule.error && (
          <Alert tone={schedule.code === "not_connected" ? "caution" : "critical"}>
            {schedule.error}
          </Alert>
        )}
        <div className="grid gap-4 sm:grid-cols-[auto_1fr_auto]">
          <Field label="Provider" htmlFor="meeting_provider">
            <Select
              id="meeting_provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value as MeetingProvider)}
            >
              {MEETING_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Topic" htmlFor="meeting_topic" required>
            <Input
              id="meeting_topic"
              required
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="Kickoff call"
            />
          </Field>
          <Field label="When" htmlFor="meeting_start" required>
            <Input
              id="meeting_start"
              type="datetime-local"
              required
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
            />
          </Field>
        </div>
        <Button type="submit" size="sm" loading={schedule.pending}>
          <Icon name="video" className="size-4" />
          Schedule
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Activity feed                                                              */
/* -------------------------------------------------------------------------- */

const ACTIVITY_PROVIDERS: Array<{ value: ActivityProvider; label: string; placeholder: string }> = [
  { value: "github", label: "GitHub", placeholder: "owner/repo" },
  { value: "figma", label: "Figma", placeholder: "File key from the Figma file URL" },
  { value: "notion", label: "Notion", placeholder: "Notion page id" },
];

export function ActivityFeedPanel({ contractId }: { contractId: number }) {
  const { data, loading, reload } = useLoader(
    () => integrations.activitySources(contractId),
    [contractId],
  );
  const sources = data ?? [];

  const [provider, setProvider] = React.useState<ActivityProvider>("github");
  const [externalRef, setExternalRef] = React.useState("");

  const add = useAsyncAction(async () => {
    await integrations.addActivitySource(contractId, { provider, external_ref: externalRef });
    setExternalRef("");
    await reload();
  });

  const sync = useAsyncAction(async (sourceId: number) => {
    await integrations.syncActivitySource(sourceId);
    await reload();
  });

  const providerMeta = ACTIVITY_PROVIDERS.find((p) => p.value === provider)!;

  return (
    <Card>
      <CardHeader
        title="Linked activity"
        description="Point this contract at a GitHub repo, Figma file, or Notion page you already have access to — a read-only feed of recent activity, not a claim of work done."
      />

      <div className="p-5">
        {loading ? (
          <p className="text-[13px] text-muted">Loading…</p>
        ) : sources.length === 0 ? (
          <EmptyState
            icon={<Icon name="link" className="size-5" />}
            title="Nothing linked yet"
            description="Add a source below, once its provider is connected in Settings → Integrations."
          />
        ) : (
          <ul className="space-y-4">
            {sources.map((source) => (
              <li key={source.id} className="rounded-md border border-line p-3.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-medium text-fg">
                      {ACTIVITY_PROVIDERS.find((p) => p.value === source.provider)?.label}:{" "}
                      {source.external_ref}
                    </p>
                    <p className="text-[12px] text-muted">
                      {source.last_synced_at
                        ? `Synced ${formatRelative(source.last_synced_at)}`
                        : "Never synced"}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    loading={sync.pending}
                    onClick={() => void sync.run(source.id)}
                  >
                    Sync now
                  </Button>
                </div>
                {sync.error && sync.code && (
                  <p className="mt-2 text-[12px] text-critical">{sync.error}</p>
                )}
                {source.recent_events.length > 0 && (
                  <ol className="mt-3 space-y-2 border-t border-line pt-3">
                    {source.recent_events.slice(0, 5).map((event) => (
                      <li key={event.id} className="text-[12.5px] text-muted">
                        <span className="text-fg">{event.summary}</span> ·{" "}
                        {formatRelative(event.occurred_at)}
                      </li>
                    ))}
                  </ol>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <form
        className="space-y-4 border-t border-line p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void add.run();
        }}
      >
        {add.error && (
          <Alert tone={add.code === "not_connected" ? "caution" : "critical"}>{add.error}</Alert>
        )}
        <div className="grid gap-4 sm:grid-cols-[auto_1fr]">
          <Field label="Provider" htmlFor="activity_provider">
            <Select
              id="activity_provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value as ActivityProvider)}
            >
              {ACTIVITY_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={providerMeta.placeholder} htmlFor="activity_ref" required>
            <Input
              id="activity_ref"
              required
              value={externalRef}
              onChange={(event) => setExternalRef(event.target.value)}
              placeholder={providerMeta.placeholder}
            />
          </Field>
        </div>
        <Button type="submit" size="sm" loading={add.pending}>
          <Icon name="link" className="size-4" />
          Add
        </Button>
      </form>
    </Card>
  );
}

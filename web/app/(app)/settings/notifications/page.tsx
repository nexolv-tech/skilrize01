"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import { Alert, Badge, Button, Card, CardHeader, Icon, Select, Skeleton, Switch } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsyncAction } from "@/lib/session";

interface Preferences {
  overrides: Record<string, Record<string, boolean>>;
  digest_frequency: "instant" | "daily" | "weekly";
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  defaults: Record<string, boolean>;
  categories: Array<{ value: string; label: string }>;
}

const CHANNELS: Array<{ key: string; label: string }> = [
  { key: "email", label: "Email" },
  { key: "push", label: "Push" },
  { key: "sms", label: "SMS" },
];

/**
 * Mirrors the server rules so the UI never offers a switch that would be
 * ignored. The server is still the authority — this only keeps the interface
 * honest about what it can actually change.
 */
const UNMUTABLE = new Set(["security", "payment", "dispute"]);
const SMS_ELIGIBLE = new Set(["security", "payment"]);

export default function NotificationSettingsPage() {
  const [prefs, setPrefs] = React.useState<Preferences | null>(null);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.get<Preferences>("/notifications/preferences/");
        if (!cancelled) setPrefs(result);
      } catch {
        if (!cancelled) setPrefs(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useAsyncAction(async (next: Partial<Preferences>) => {
    const result = await api.patch<Preferences>("/notifications/preferences/", next);
    setPrefs(result);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  });

  function isOn(category: string, channel: string): boolean {
    if (!prefs) return false;
    if (UNMUTABLE.has(category)) return channel !== "sms" || SMS_ELIGIBLE.has(category);
    if (channel === "sms") return false;
    return prefs.overrides[category]?.[channel] ?? prefs.defaults[channel] ?? false;
  }

  function toggle(category: string, channel: string, value: boolean) {
    if (!prefs) return;
    const overrides = {
      ...prefs.overrides,
      [category]: { ...(prefs.overrides[category] ?? {}), [channel]: value },
    };
    setPrefs({ ...prefs, overrides });
    void save.run({ overrides });
  }

  if (!prefs) {
    return (
      <>
        <PageHeading title="Notifications" />
        <Card className="p-5">
          <div className="space-y-3">
            {[0, 1, 2, 3].map((row) => (
              <Skeleton key={row} className="h-10 w-full" />
            ))}
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Notifications"
        description="Choose what reaches you and how. Security, payment, and dispute notices always get through."
        action={
          saved ? (
            <span className="animate-fade inline-flex items-center gap-1.5 text-[13px] text-positive">
              <Icon name="check" className="size-4" strokeWidth={2.6} />
              Saved
            </span>
          ) : undefined
        }
      />

      <div className="space-y-6">
        {save.error && <Alert tone="critical">{save.error}</Alert>}

        <Card>
          <CardHeader
            title="By category"
            description="SMS is reserved for security and payment-critical events only, so it is never billed against ordinary activity."
          />

          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem]">
              <thead>
                <tr className="border-b border-line text-left">
                  <th scope="col" className="px-5 py-3 text-[12px] font-medium text-muted">
                    Category
                  </th>
                  {CHANNELS.map((channel) => (
                    <th
                      key={channel.key}
                      scope="col"
                      className="w-24 px-3 py-3 text-center text-[12px] font-medium text-muted"
                    >
                      {channel.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {prefs.categories.map((category) => {
                  const locked = UNMUTABLE.has(category.value);
                  return (
                    <tr key={category.value}>
                      <th scope="row" className="px-5 py-3.5 text-left font-normal">
                        <span className="flex items-center gap-2 text-[13.5px] text-fg">
                          {category.label}
                          {locked && <Badge tone="accent">Always on</Badge>}
                        </span>
                      </th>
                      {CHANNELS.map((channel) => {
                        const unavailable =
                          channel.key === "sms" && !SMS_ELIGIBLE.has(category.value);
                        return (
                          <td key={channel.key} className="px-3 py-3.5 text-center">
                            {unavailable ? (
                              <span className="text-[12px] text-subtle" aria-label="Not available">
                                —
                              </span>
                            ) : (
                              <span className="inline-flex">
                                <Switch
                                  label={`${category.label} by ${channel.label}`}
                                  checked={isOn(category.value, channel.key)}
                                  disabled={locked}
                                  onChange={(next) => toggle(category.value, channel.key, next)}
                                />
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Delivery"
            description="Batch non-urgent notifications so a busy week does not become a full inbox."
          />
          <div className="max-w-xs p-5">
            <label htmlFor="digest" className="mb-1.5 block text-[13px] font-medium text-fg">
              Digest frequency
            </label>
            <Select
              id="digest"
              value={prefs.digest_frequency}
              onChange={(event) =>
                void save.run({
                  digest_frequency: event.target.value as Preferences["digest_frequency"],
                })
              }
            >
              <option value="instant">Send immediately</option>
              <option value="daily">Daily digest</option>
              <option value="weekly">Weekly digest</option>
            </Select>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Quiet hours"
            description="Non-urgent notifications are held during these hours, in your own timezone. Security and payment events ignore them."
            action={<Badge>Phase 5</Badge>}
          />
          <div className="p-5">
            <Button variant="secondary" size="sm" disabled>
              <Icon name="moon" className="size-4" />
              Configure quiet hours
            </Button>
          </div>
        </Card>
      </div>
    </>
  );
}

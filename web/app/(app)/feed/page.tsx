"use client";

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import { Alert, Avatar, Card, EmptyState, Icon, Skeleton, type IconName } from "@/components/ui";
import { communities, type FeedEntry } from "@/lib/api";
import { formatRelative, useLoader, useSession } from "@/lib/session";

/** One glyph per verb, so the feed is scannable without reading every line. */
const VERB_ICON: Record<string, IconName> = {
  community_created: "users",
  joined_community: "user",
  thread_posted: "quote",
  event_created: "clock",
  resource_shared: "file",
  gig_published: "layers",
  project_posted: "briefcase",
};

export default function FeedPage() {
  const { surface, user } = useSession();
  const { data, loading, error } = useLoader(() => communities.feed(), [surface]);

  const campus = (user?.surfaces ?? []).find((option) => option.kind === "university");
  const onCampus = surface === "university";

  return (
    <>
      <PageHeading
        title={onCampus ? `${campus?.university?.short_code ?? "Campus"} activity` : "Activity"}
        description={
          onCampus
            ? "What is happening across your university portal."
            : "What is happening across the global marketplace."
        }
      />

      {error && <Alert tone="critical">{error}</Alert>}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((key) => (
            <Skeleton key={key} className="h-16" />
          ))}
        </div>
      ) : data && data.results.length > 0 ? (
        <Card>
          <ul className="divide-y divide-line">
            {data.results.map((entry: FeedEntry) => {
              const row = (
                <div className="flex items-start gap-3 p-4">
                  <Avatar
                    name={entry.actor.display_name}
                    src={entry.actor.avatar_url}
                    size={34}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px] leading-relaxed text-fg">{entry.summary}</p>
                    <p className="mt-0.5 text-[12px] text-subtle">
                      {formatRelative(entry.created_at)}
                    </p>
                  </div>
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-sunken text-subtle">
                    <Icon name={VERB_ICON[entry.verb] ?? "sparkles"} className="size-4" />
                  </span>
                </div>
              );

              return (
                <li key={entry.id}>
                  {entry.url ? (
                    <Link
                      href={entry.url}
                      className="block transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                      {row}
                    </Link>
                  ) : (
                    row
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="sparkles" className="size-5" />}
            title="Nothing yet"
            description={
              onCampus
                ? "Activity from your campus will appear here."
                : "Join a community or post something to get started."
            }
          />
        </Card>
      )}
    </>
  );
}

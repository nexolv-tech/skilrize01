"use client";

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  Field,
  Icon,
  Input,
  Segmented,
  Skeleton,
  Textarea,
  cn,
} from "@/components/ui";
import { communities, type Community } from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

const KIND_LABEL: Record<Community["kind"], string> = {
  open: "Anyone can join",
  request: "Approval needed",
  closed: "Invite only",
};

function CommunityCard({ community, onJoin }: { community: Community; onJoin: () => void }) {
  const join = useAsyncAction(async () => {
    await communities.join(community.id);
    onJoin();
  });

  return (
    <Card className="lift flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <Link
          href={`/communities/${community.id}`}
          className="min-w-0 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <h3 className="truncate text-[15.5px] font-semibold text-fg hover:text-accent">
            {community.name}
          </h3>
        </Link>
        {community.visibility === "university" && <Badge tone="accent">Campus</Badge>}
      </div>

      {community.tagline && (
        <p className="mt-1.5 line-clamp-2 text-[13.5px] leading-relaxed text-muted">
          {community.tagline}
        </p>
      )}

      <div className="mt-4 flex items-center gap-3 text-[12.5px] text-subtle">
        <span className="inline-flex items-center gap-1.5">
          <Icon name="users" className="size-3.5" />
          {community.member_count}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Icon name="quote" className="size-3.5" />
          {community.thread_count}
        </span>
        <span className="ml-auto">{KIND_LABEL[community.kind]}</span>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        {community.my_role ? (
          <ButtonLink href={`/communities/${community.id}`} variant="secondary" size="sm" block>
            Open
          </ButtonLink>
        ) : (
          <Button
            size="sm"
            block
            loading={join.pending}
            onClick={() => void join.run()}
            disabled={community.kind === "closed"}
          >
            {community.kind === "closed"
              ? "Invite only"
              : community.kind === "request"
                ? "Request to join"
                : "Join"}
          </Button>
        )}
        {join.error && <p className="mt-2 text-[12.5px] text-critical">{join.error}</p>}
      </div>
    </Card>
  );
}

function CreateCommunity({ onCreated }: { onCreated: () => void }) {
  const { user, surface } = useSession();
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [tagline, setTagline] = React.useState("");
  const [kind, setKind] = React.useState<Community["kind"]>("open");

  const create = useAsyncAction(async () => {
    await communities.create({
      name,
      tagline,
      kind,
      // A community created while standing in a campus portal belongs to that
      // campus. Deriving it from the active surface rather than asking is what
      // keeps the answer consistent with everything else on screen.
      visibility: surface === "university" ? "university" : "global",
    });
    setOpen(false);
    setName("");
    setTagline("");
    onCreated();
  });

  if (!user) return null;

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)}>
        <Icon name="plus" className="size-4" />
        New community
      </Button>
    );
  }

  return (
    <Card className="w-full p-5">
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void create.run();
        }}
      >
        {create.error && <Alert tone="critical">{create.error}</Alert>}
        {surface === "university" && (
          <Alert tone="accent">
            This will be a campus community — visible only to verified students of your
            university.
          </Alert>
        )}

        <Field label="Name" htmlFor="name" error={create.fieldErrors.name} required>
          <Input
            id="name"
            required
            autoFocus
            placeholder="Robotics Society"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>

        <Field label="Tagline" htmlFor="tagline" hint="One line on what this is for.">
          <Textarea
            id="tagline"
            rows={2}
            placeholder="We build things and break things."
            value={tagline}
            onChange={(event) => setTagline(event.target.value)}
          />
        </Field>

        <Field label="Who can join" htmlFor="kind">
          <Segmented
            label="Who can join"
            value={kind}
            onChange={setKind}
            options={[
              { value: "open", label: "Anyone" },
              { value: "request", label: "On approval" },
              { value: "closed", label: "Invite only" },
            ]}
          />
        </Field>

        <div className="flex gap-3">
          <Button type="submit" loading={create.pending}>
            Create
          </Button>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default function CommunitiesPage() {
  const { surface } = useSession();
  const [query, setQuery] = React.useState("");
  const [mine, setMine] = React.useState<"all" | "mine">("all");
  const [nonce, setNonce] = React.useState(0);

  const { data, loading, error } = useLoader(
    () =>
      communities.list({
        q: query || undefined,
        mine: mine === "mine" ? "true" : undefined,
      }),
    // `surface` is a dependency so switching portals refetches, rather than
    // leaving the previous surface's directory on screen under a new banner.
    [query, mine, surface, nonce],
  );

  return (
    <>
      <PageHeading
        title="Communities"
        description="Societies, study groups, and shared spaces. Campus communities are visible only inside your university portal."
        action={<CreateCommunity onCreated={() => setNonce((n) => n + 1)} />}
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
          />
          <Input
            placeholder="Search communities"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="pl-9"
          />
        </div>
        <Segmented
          label="Which communities"
          value={mine}
          onChange={setMine}
          options={[
            { value: "all", label: "All" },
            { value: "mine", label: "Mine" },
          ]}
        />
      </div>

      {error && <Alert tone="critical">{error}</Alert>}

      {loading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((key) => (
            <Skeleton key={key} className="h-44" />
          ))}
        </div>
      ) : data && data.results.length > 0 ? (
        <div className={cn("grid gap-5 sm:grid-cols-2 lg:grid-cols-3")}>
          {data.results.map((community) => (
            <CommunityCard
              key={community.id}
              community={community}
              onJoin={() => setNonce((n) => n + 1)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="users" className="size-5" />}
            title={mine === "mine" ? "You have not joined anything yet" : "No communities yet"}
            description={
              surface === "university"
                ? "Be the first to start one for your campus."
                : "Start one and invite people to it."
            }
          />
        </Card>
      )}
    </>
  );
}

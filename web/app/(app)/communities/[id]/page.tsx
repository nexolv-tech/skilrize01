"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  Alert,
  Avatar,
  Badge,
  Button,
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
import {
  communities,
  type ChatMessage,
  type Community,
  type CommunityEvent,
  type CommunityResource,
  type CommunityThread,
} from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

type Tab = "discussions" | "chat" | "events" | "resources";

/* -------------------------------------------------------------------------- */
/* Discussions                                                                */
/* -------------------------------------------------------------------------- */

function Discussions({ community }: { community: Community }) {
  const [nonce, setNonce] = React.useState(0);
  const [composing, setComposing] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [body, setBody] = React.useState("");

  const { data, loading } = useLoader(
    () => communities.threads(community.id),
    [community.id, nonce],
  );

  const post = useAsyncAction(async () => {
    await communities.createThread(community.id, title, body);
    setTitle("");
    setBody("");
    setComposing(false);
    setNonce((n) => n + 1);
  });

  return (
    <div className="space-y-5">
      {community.can_post &&
        (composing ? (
          <Card className="p-5">
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void post.run();
              }}
            >
              {post.error && <Alert tone="critical">{post.error}</Alert>}
              <Field label="Title" htmlFor="thread_title" error={post.fieldErrors.title} required>
                <Input
                  id="thread_title"
                  required
                  autoFocus
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
              <Field label="Post" htmlFor="thread_body" error={post.fieldErrors.body} required>
                <Textarea
                  id="thread_body"
                  rows={5}
                  required
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                />
              </Field>
              <div className="flex gap-3">
                <Button type="submit" loading={post.pending}>
                  Post
                </Button>
                <Button type="button" variant="ghost" onClick={() => setComposing(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <Button onClick={() => setComposing(true)}>
            <Icon name="plus" className="size-4" />
            Start a discussion
          </Button>
        ))}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-20" />
          ))}
        </div>
      ) : data && data.results.length > 0 ? (
        <Card>
          <ul className="divide-y divide-line">
            {data.results.map((thread: CommunityThread) => (
              <li key={thread.id}>
                <Link
                  href={`/communities/${community.id}/threads/${thread.id}`}
                  className="flex items-start gap-3 p-5 transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  <Avatar
                    name={thread.author.display_name}
                    src={thread.author.avatar_url}
                    size={36}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {thread.is_pinned && <Badge tone="accent">Pinned</Badge>}
                      {thread.is_locked && <Badge tone="caution">Locked</Badge>}
                      <p className="truncate text-[14.5px] font-medium text-fg">{thread.title}</p>
                    </div>
                    <p className="mt-1 text-[12.5px] text-subtle">
                      {thread.author.display_name} · {formatRelative(thread.last_activity_at)} ·{" "}
                      {thread.reply_count} {thread.reply_count === 1 ? "reply" : "replies"}
                    </p>
                  </div>
                  <Icon name="chevronLeft" className="mt-1 size-4 rotate-180 text-subtle" />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="quote" className="size-5" />}
            title="No discussions yet"
            description={community.can_post ? "Start the first one." : "Join to start one."}
          />
        </Card>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Chat                                                                       */
/* -------------------------------------------------------------------------- */

function Chat({ community }: { community: Community }) {
  const { user } = useSession();
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [body, setBody] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const bottom = React.useRef<HTMLDivElement>(null);

  // Polled rather than pushed. The read model is what a socket would need, so
  // swapping the transport later is a delivery change, not a rewrite.
  React.useEffect(() => {
    let cancelled = false;
    const pull = async () => {
      try {
        const next = await communities.chat(community.id);
        if (!cancelled) {
          setMessages(next);
          setError(null);
        }
      } catch (caught) {
        if (!cancelled) setError((caught as Error).message);
      }
    };
    void pull();
    const timer = setInterval(pull, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [community.id]);

  React.useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const send = useAsyncAction(async () => {
    const sent = await communities.sendChat(community.id, body);
    setMessages((previous) => [...previous, sent]);
    setBody("");
  });

  if (!community.my_role) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="lock" className="size-5" />}
          title="Members only"
          description="Join this community to read and take part in its chat."
        />
      </Card>
    );
  }

  return (
    <Card className="flex h-[32rem] flex-col">
      {error && <Alert tone="critical" className="m-4">{error}</Alert>}

      <div className="flex-1 space-y-3 overflow-y-auto p-5">
        {messages.length === 0 && (
          <p className="py-10 text-center text-[13.5px] text-subtle">
            Nothing here yet. Say something.
          </p>
        )}
        {messages.map((message) => {
          const mine = message.author.id === user?.id;
          return (
            <div
              key={message.id}
              className={cn("flex gap-2.5", mine && "flex-row-reverse")}
            >
              <Avatar
                name={message.author.display_name}
                src={message.author.avatar_url}
                size={30}
              />
              <div className={cn("max-w-[75%]", mine && "text-right")}>
                <p className="text-[11.5px] text-subtle">
                  {mine ? "You" : message.author.display_name} ·{" "}
                  {formatRelative(message.created_at)}
                </p>
                <div
                  className={cn(
                    "mt-1 inline-block rounded-xl px-3.5 py-2 text-[13.5px] leading-relaxed",
                    mine ? "bg-accent text-on-accent" : "bg-sunken text-fg",
                    message.is_deleted && "italic opacity-60",
                  )}
                >
                  {message.body}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>

      <form
        className="flex gap-2 border-t border-line p-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (body.trim()) void send.run();
        }}
      >
        <Input
          placeholder="Message the community"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          aria-label="Message"
        />
        <Button type="submit" loading={send.pending} disabled={!body.trim()}>
          <Icon name="send" className="size-4" />
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Events                                                                     */
/* -------------------------------------------------------------------------- */

function Events({ community }: { community: Community }) {
  const [nonce, setNonce] = React.useState(0);
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState({
    title: "",
    starts_at: "",
    location: "",
    capacity: "",
  });

  const { data, loading } = useLoader(
    () => communities.events(community.id),
    [community.id, nonce],
  );

  const create = useAsyncAction(async () => {
    await communities.createEvent({
      community: community.id,
      title: form.title,
      starts_at: new Date(form.starts_at).toISOString(),
      location: form.location,
      capacity: form.capacity ? Number(form.capacity) : 0,
    });
    setOpen(false);
    setForm({ title: "", starts_at: "", location: "", capacity: "" });
    setNonce((n) => n + 1);
  });

  return (
    <div className="space-y-5">
      {community.can_post &&
        (open ? (
          <Card className="p-5">
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void create.run();
              }}
            >
              {create.error && <Alert tone="critical">{create.error}</Alert>}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Title" htmlFor="event_title" required>
                  <Input
                    id="event_title"
                    required
                    value={form.title}
                    onChange={(event) => setForm({ ...form, title: event.target.value })}
                  />
                </Field>
                <Field label="Starts" htmlFor="event_start" required>
                  <Input
                    id="event_start"
                    type="datetime-local"
                    required
                    value={form.starts_at}
                    onChange={(event) => setForm({ ...form, starts_at: event.target.value })}
                  />
                </Field>
                <Field label="Where" htmlFor="event_where" required>
                  <Input
                    id="event_where"
                    required
                    placeholder="Lab 3, or a meeting link"
                    value={form.location}
                    onChange={(event) => setForm({ ...form, location: event.target.value })}
                  />
                </Field>
                <Field label="Capacity" htmlFor="event_cap" hint="Leave blank for unlimited.">
                  <Input
                    id="event_cap"
                    type="number"
                    min={0}
                    value={form.capacity}
                    onChange={(event) => setForm({ ...form, capacity: event.target.value })}
                  />
                </Field>
              </div>
              <div className="flex gap-3">
                <Button type="submit" loading={create.pending}>
                  Schedule
                </Button>
                <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <Button onClick={() => setOpen(true)}>
            <Icon name="plus" className="size-4" />
            Schedule an event
          </Button>
        ))}

      {loading ? (
        <Skeleton className="h-32" />
      ) : data && data.results.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {data.results.map((event: CommunityEvent) => (
            <EventCard key={event.id} event={event} onChanged={() => setNonce((n) => n + 1)} />
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="clock" className="size-5" />}
            title="Nothing scheduled"
            description="No upcoming events in this community."
          />
        </Card>
      )}
    </div>
  );
}

function EventCard({ event, onChanged }: { event: CommunityEvent; onChanged: () => void }) {
  const rsvp = useAsyncAction(async (status: "going" | "interested") => {
    await communities.rsvp(event.id, status);
    onChanged();
  });

  const when = new Date(event.starts_at);

  return (
    <Card className={cn("p-5", event.is_cancelled && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-fg">{event.title}</h3>
          <p className="mt-1 text-[12.5px] text-muted">
            {when.toLocaleString(undefined, {
              weekday: "short",
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        {event.is_cancelled ? (
          <Badge tone="critical">Cancelled</Badge>
        ) : event.is_full ? (
          <Badge tone="caution">Full</Badge>
        ) : null}
      </div>

      <p className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-muted">
        <Icon name="building" className="size-3.5" />
        {event.location || event.online_url}
      </p>

      <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
        <span className="text-[12.5px] text-subtle">
          {event.going_count} going
          {event.capacity ? ` · ${event.capacity} max` : ""}
        </span>
        {!event.is_cancelled && (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={event.my_rsvp === "going" ? "primary" : "secondary"}
              loading={rsvp.pending}
              onClick={() => void rsvp.run("going")}
            >
              Going
            </Button>
            <Button
              size="sm"
              variant={event.my_rsvp === "interested" ? "primary" : "ghost"}
              onClick={() => void rsvp.run("interested")}
            >
              Interested
            </Button>
          </div>
        )}
      </div>
      {rsvp.error && <p className="mt-2 text-[12.5px] text-critical">{rsvp.error}</p>}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Resources                                                                  */
/* -------------------------------------------------------------------------- */

function Resources({ community }: { community: Community }) {
  const [nonce, setNonce] = React.useState(0);
  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const [url, setUrl] = React.useState("");

  const { data, loading } = useLoader(
    () => communities.resources(community.id),
    [community.id, nonce],
  );

  const share = useAsyncAction(async () => {
    await communities.shareResource(
      community.id,
      { title, kind: file ? "file" : "link", url: file ? "" : url },
      file,
    );
    setOpen(false);
    setTitle("");
    setFile(null);
    setUrl("");
    setNonce((n) => n + 1);
  });

  return (
    <div className="space-y-5">
      {community.can_post &&
        (open ? (
          <Card className="p-5">
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void share.run();
              }}
            >
              {share.error && <Alert tone="critical">{share.error}</Alert>}
              <Field label="Title" htmlFor="res_title" required>
                <Input
                  id="res_title"
                  required
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
              <Field label="File" htmlFor="res_file" hint="Or paste a link below instead.">
                <Input
                  id="res_file"
                  type="file"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  className="file:mr-3 file:rounded-md file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-[13px] file:text-fg"
                />
              </Field>
              {!file && (
                <Field label="Link" htmlFor="res_url">
                  <Input
                    id="res_url"
                    type="url"
                    placeholder="https://…"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                  />
                </Field>
              )}
              <div className="flex gap-3">
                <Button type="submit" loading={share.pending} disabled={!file && !url}>
                  Share
                </Button>
                <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <Button onClick={() => setOpen(true)}>
            <Icon name="plus" className="size-4" />
            Share a resource
          </Button>
        ))}

      {loading ? (
        <Skeleton className="h-32" />
      ) : data && data.results.length > 0 ? (
        <Card>
          <ul className="divide-y divide-line">
            {data.results.map((resource: CommunityResource) => (
              <li key={resource.id} className="flex items-center gap-3 p-4">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-sunken text-muted">
                  <Icon name={resource.kind === "file" ? "file" : "globe"} className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium text-fg">{resource.title}</p>
                  <p className="text-[12px] text-subtle">
                    {resource.uploaded_by.display_name} · {formatRelative(resource.created_at)}
                  </p>
                </div>
                <a
                  href={resource.file_url ?? resource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-[13px] font-medium text-accent underline-offset-4 hover:underline"
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="file" className="size-5" />}
            title="Nothing shared yet"
            description="Past papers, templates, reading lists — anything useful."
          />
        </Card>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export default function CommunityPage() {
  const params = useParams<{ id: string }>();
  const [tab, setTab] = React.useState<Tab>("discussions");
  const [nonce, setNonce] = React.useState(0);

  const { data: community, loading, error } = useLoader(
    () => communities.detail(params.id),
    [params.id, nonce],
  );

  const join = useAsyncAction(async () => {
    await communities.join(Number(params.id));
    setNonce((n) => n + 1);
  });

  if (loading) return <Skeleton className="h-64" />;
  if (error || !community) return <Alert tone="critical">{error ?? "Not found."}</Alert>;

  return (
    <>
      <div className="mb-6">
        <Link
          href="/communities"
          className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg"
        >
          <Icon name="chevronLeft" className="size-3.5" />
          All communities
        </Link>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">
                {community.name}
              </h1>
              {community.visibility === "university" && <Badge tone="accent">Campus only</Badge>}
              {community.my_role === "owner" && <Badge tone="positive">Owner</Badge>}
              {community.my_role === "moderator" && <Badge tone="positive">Moderator</Badge>}
            </div>
            {community.tagline && (
              <p className="mt-2 max-w-2xl text-[14.5px] text-muted">{community.tagline}</p>
            )}
            <p className="mt-2 text-[12.5px] text-subtle">
              {community.member_count} members · {community.thread_count} discussions
            </p>
          </div>

          {!community.my_role && community.kind !== "closed" && (
            <Button loading={join.pending} onClick={() => void join.run()}>
              {community.kind === "request" ? "Request to join" : "Join"}
            </Button>
          )}
        </div>
        {join.error && <Alert tone="critical" className="mt-3">{join.error}</Alert>}
      </div>

      <div className="mb-6">
        <Segmented
          label="Section"
          value={tab}
          onChange={setTab}
          options={[
            { value: "discussions", label: "Discussions", icon: "quote" },
            { value: "chat", label: "Chat", icon: "send" },
            { value: "events", label: "Events", icon: "clock" },
            { value: "resources", label: "Resources", icon: "file" },
          ]}
        />
      </div>

      {tab === "discussions" && <Discussions community={community} />}
      {tab === "chat" && <Chat community={community} />}
      {tab === "events" && <Events community={community} />}
      {tab === "resources" && <Resources community={community} />}
    </>
  );
}

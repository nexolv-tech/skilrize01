"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Skeleton,
  cn,
} from "@/components/ui";
import { messages, type Conversation } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

function Thread({ conversation }: { conversation: Conversation }) {
  const { user } = useSession();
  const [nonce, setNonce] = React.useState(0);
  const [body, setBody] = React.useState("");
  const bottom = React.useRef<HTMLDivElement>(null);

  const { data, loading } = useLoader(
    () => messages.thread(conversation.id),
    [conversation.id, nonce],
  );

  React.useEffect(() => {
    bottom.current?.scrollIntoView();
  }, [data?.results.length]);

  const send = useAsyncAction(async () => {
    await messages.send(conversation.id, body);
    setBody("");
    setNonce((n) => n + 1);
  });

  return (
    <Card className="flex h-[34rem] flex-col">
      <div className="flex items-center gap-3 border-b border-line p-4">
        <Avatar
          name={conversation.other?.display_name ?? "?"}
          src={conversation.other?.avatar_url}
          size={36}
        />
        <div className="min-w-0">
          <p className="truncate text-[14px] font-medium text-fg">
            {conversation.other?.display_name}
          </p>
          <p className="truncate text-[12px] text-subtle">@{conversation.other?.handle}</p>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-5">
        {loading ? (
          <Skeleton className="h-20" />
        ) : (
          (data?.results ?? []).map((message) => {
            const mine = message.sender.id === user?.id;
            return (
              <div key={message.id} className={cn("flex", mine && "justify-end")}>
                <div className={cn("max-w-[75%]", mine && "text-right")}>
                  <div
                    className={cn(
                      "inline-block rounded-xl px-3.5 py-2 text-[13.5px] leading-relaxed",
                      mine ? "bg-accent text-on-accent" : "bg-sunken text-fg",
                    )}
                  >
                    {message.body}
                  </div>
                  <p className="mt-1 text-[11px] text-subtle">
                    {formatRelative(message.created_at)}
                  </p>
                </div>
              </div>
            );
          })
        )}
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
          placeholder="Write a message"
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

export default function MessagesPage() {
  const [selected, setSelected] = React.useState<Conversation | null>(null);
  const [handle, setHandle] = React.useState("");
  const [nonce, setNonce] = React.useState(0);

  const { data, loading, error } = useLoader(() => messages.conversations(), [nonce]);

  const start = useAsyncAction(async () => {
    const conversation = await messages.start(handle.replace(/^@/, ""));
    setHandle("");
    setNonce((n) => n + 1);
    setSelected(conversation);
  });

  return (
    <>
      <PageHeading
        title="Messages"
        description="Direct conversations. Contract discussions stay on the contract itself, where a dispute officer can read them in order."
      />

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-4">
          <Card className="p-4">
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (handle.trim()) void start.run();
              }}
            >
              <Input
                placeholder="@handle"
                value={handle}
                onChange={(event) => setHandle(event.target.value)}
                aria-label="Start a conversation with"
              />
              <Button type="submit" loading={start.pending} disabled={!handle.trim()}>
                Start
              </Button>
            </form>
            {start.error && <p className="mt-2 text-[12.5px] text-critical">{start.error}</p>}
          </Card>

          {error && <Alert tone="critical">{error}</Alert>}

          {loading ? (
            <Skeleton className="h-40" />
          ) : data && data.results.length > 0 ? (
            <Card>
              <ul className="divide-y divide-line">
                {data.results.map((conversation) => (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(conversation)}
                      className={cn(
                        "flex w-full items-center gap-3 p-4 text-left transition-colors",
                        "hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                        selected?.id === conversation.id && "bg-sunken",
                      )}
                    >
                      <Avatar
                        name={conversation.other?.display_name ?? "?"}
                        src={conversation.other?.avatar_url}
                        size={36}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-fg">
                          {conversation.other?.display_name}
                        </p>
                        <p className="truncate text-[12px] text-subtle">
                          {conversation.last_message?.body ?? "No messages yet"}
                        </p>
                      </div>
                      {conversation.unread_count > 0 && (
                        <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent text-[11px] font-semibold text-on-accent">
                          {conversation.unread_count}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          ) : (
            <Card>
              <EmptyState
                icon={<Icon name="send" className="size-5" />}
                title="No conversations"
                description="Start one with someone's handle."
              />
            </Card>
          )}
        </div>

        {selected ? (
          <Thread key={selected.id} conversation={selected} />
        ) : (
          <Card>
            <EmptyState
              icon={<Icon name="send" className="size-5" />}
              title="Pick a conversation"
              description="Or start a new one from the left."
            />
          </Card>
        )}
      </div>
    </>
  );
}

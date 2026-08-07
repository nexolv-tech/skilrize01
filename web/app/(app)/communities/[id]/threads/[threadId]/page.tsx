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
  Icon,
  Skeleton,
  Textarea,
  cn,
} from "@/components/ui";
import { communities, type ThreadReply } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

/**
 * Rebuild the reply tree from a flat, chronological list.
 *
 * The API returns replies in creation order with a `parent` pointer rather than
 * pre-nested, because a nested payload would have to pick a traversal order and
 * the client is the only side that knows how it wants to render. Depth is
 * capped server-side, so this recursion is bounded.
 */
function nest(replies: ThreadReply[]): Array<ThreadReply & { children: ThreadReply[] }> {
  const byId = new Map<number, ThreadReply & { children: ThreadReply[] }>();
  const roots: Array<ThreadReply & { children: ThreadReply[] }> = [];

  for (const reply of replies) byId.set(reply.id, { ...reply, children: [] });
  for (const reply of replies) {
    const node = byId.get(reply.id)!;
    const parent = reply.parent ? byId.get(reply.parent) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function ReplyNode({
  reply,
  onReply,
  onRemove,
  canModerate,
}: {
  reply: ThreadReply & { children: ThreadReply[] };
  onReply: (parent: number) => void;
  onRemove: (id: number) => void;
  canModerate: boolean;
}) {
  const { user } = useSession();
  const mine = reply.author.id === user?.id;

  return (
    <li>
      <div className="flex gap-3 py-4">
        <Avatar name={reply.author.display_name} src={reply.author.avatar_url} size={32} />
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] text-subtle">
            <span className="font-medium text-fg">{reply.author.display_name}</span> ·{" "}
            {formatRelative(reply.created_at)}
          </p>
          <p
            className={cn(
              "mt-1.5 whitespace-pre-wrap text-[14px] leading-relaxed",
              reply.is_deleted ? "italic text-subtle" : "text-fg",
            )}
          >
            {reply.body}
          </p>

          {!reply.is_deleted && (
            <div className="mt-2 flex gap-3">
              <button
                type="button"
                onClick={() => onReply(reply.id)}
                className="text-[12.5px] text-muted hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                Reply
              </button>
              {(mine || canModerate) && (
                <button
                  type="button"
                  onClick={() => onRemove(reply.id)}
                  className="text-[12.5px] text-muted hover:text-critical focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  Remove
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {reply.children.length > 0 && (
        <ul className="ml-6 border-l border-line pl-4">
          {reply.children.map((child) => (
            <ReplyNode
              key={child.id}
              reply={child as ThreadReply & { children: ThreadReply[] }}
              onReply={onReply}
              onRemove={onRemove}
              canModerate={canModerate}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function ThreadPage() {
  const params = useParams<{ id: string; threadId: string }>();
  const [nonce, setNonce] = React.useState(0);
  const [body, setBody] = React.useState("");
  const [replyingTo, setReplyingTo] = React.useState<number | null>(null);

  const { data: thread, loading } = useLoader(
    () => communities.thread(params.threadId),
    [params.threadId, nonce],
  );
  const { data: replies } = useLoader(
    () => communities.replies(params.threadId),
    [params.threadId, nonce],
  );
  const { data: community } = useLoader(() => communities.detail(params.id), [params.id]);

  const post = useAsyncAction(async () => {
    await communities.reply(params.threadId, body, replyingTo);
    setBody("");
    setReplyingTo(null);
    setNonce((n) => n + 1);
  });

  const remove = useAsyncAction(async (id: number) => {
    await communities.removeReply(id);
    setNonce((n) => n + 1);
  });

  const toggleLock = useAsyncAction(async () => {
    await communities.lockThread(Number(params.threadId));
    setNonce((n) => n + 1);
  });

  const togglePin = useAsyncAction(async () => {
    await communities.pinThread(Number(params.threadId));
    setNonce((n) => n + 1);
  });

  if (loading || !thread) return <Skeleton className="h-64" />;

  const canModerate =
    community?.my_role === "owner" || community?.my_role === "moderator";
  const tree = nest(replies?.results ?? []);

  return (
    <>
      <Link
        href={`/communities/${params.id}`}
        className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg"
      >
        <Icon name="chevronLeft" className="size-3.5" />
        Back to community
      </Link>

      <Card className="mt-4 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {thread.is_pinned && <Badge tone="accent">Pinned</Badge>}
              {thread.is_locked && <Badge tone="caution">Locked</Badge>}
            </div>
            <h1 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-fg">
              {thread.title}
            </h1>
          </div>
          {canModerate && (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => void togglePin.run()}>
                {thread.is_pinned ? "Unpin" : "Pin"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => void toggleLock.run()}>
                {thread.is_locked ? "Unlock" : "Lock"}
              </Button>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2.5">
          <Avatar name={thread.author.display_name} src={thread.author.avatar_url} size={32} />
          <p className="text-[12.5px] text-subtle">
            <span className="font-medium text-fg">{thread.author.display_name}</span> ·{" "}
            {formatRelative(thread.created_at)}
          </p>
        </div>

        <p className="mt-4 whitespace-pre-wrap text-[14.5px] leading-relaxed text-fg">
          {thread.body}
        </p>
      </Card>

      <div className="mt-6">
        <h2 className="mb-2 text-[15px] font-semibold text-fg">
          {thread.reply_count} {thread.reply_count === 1 ? "reply" : "replies"}
        </h2>

        <Card className="px-6">
          {tree.length === 0 ? (
            <p className="py-8 text-center text-[13.5px] text-subtle">No replies yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {tree.map((reply) => (
                <ReplyNode
                  key={reply.id}
                  reply={reply}
                  onReply={setReplyingTo}
                  onRemove={(id) => void remove.run(id)}
                  canModerate={canModerate}
                />
              ))}
            </ul>
          )}
        </Card>
      </div>

      {thread.is_locked ? (
        <Alert tone="caution" className="mt-5">
          This discussion is locked. No new replies.
        </Alert>
      ) : (
        <Card className="mt-5 p-5">
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void post.run();
            }}
          >
            {post.error && <Alert tone="critical">{post.error}</Alert>}
            {replyingTo && (
              <p className="flex items-center gap-2 text-[12.5px] text-muted">
                Replying to a comment
                <button
                  type="button"
                  onClick={() => setReplyingTo(null)}
                  className="font-medium text-accent underline-offset-4 hover:underline"
                >
                  cancel
                </button>
              </p>
            )}
            <Textarea
              rows={3}
              placeholder="Write a reply"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              aria-label="Reply"
            />
            <Button type="submit" loading={post.pending} disabled={!body.trim()}>
              Reply
            </Button>
          </form>
        </Card>
      )}
    </>
  );
}

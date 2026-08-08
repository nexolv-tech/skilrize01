"use client";

import * as React from "react";
import Link from "next/link";

import { CoverArt, motifFor } from "@/components/artwork";
import { LevelBadge, SuccessScore } from "@/components/reputation";
import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Card,
  EmptyState,
  Icon,
  Skeleton,
  Stars,
  cn,
} from "@/components/ui";
import { discovery, type ShowcasePiece } from "@/lib/api";
import { formatRelative, useLoader, useSession } from "@/lib/session";

function Piece({ piece }: { piece: ShowcasePiece }) {
  return (
    <Card className="lift flex flex-col overflow-hidden">
      <div className="aspect-[16/10] overflow-hidden bg-sunken">
        {piece.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={piece.cover_url}
            alt=""
            loading="lazy"
            className="size-full object-cover"
          />
        ) : (
          <CoverArt seed={piece.title} motif={motifFor(piece.category_name)} rounded={false} />
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <p className="line-clamp-2 text-[15px] font-medium leading-snug text-fg">{piece.title}</p>
        {piece.summary && (
          <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-muted">
            {piece.summary}
          </p>
        )}

        <div className="mt-4 flex items-center gap-2.5 border-t border-line pt-4">
          <Avatar
            name={piece.seller.display_name}
            src={piece.seller.avatar_url}
            size={32}
          />
          <div className="min-w-0 flex-1">
            <Link
              href={`/users/${piece.seller.handle}`}
              className="block truncate text-[13px] font-medium text-fg hover:text-accent"
            >
              {piece.seller.display_name}
            </Link>
            <p className="text-[11.5px] text-subtle">
              {piece.published_at ? formatRelative(piece.published_at) : ""}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <LevelBadge level={piece.seller.level} />
            <SuccessScore score={piece.seller.job_success_score} />
          </div>
        </div>

        {piece.rating_at_publication && (
          <div className="mt-3 flex items-center gap-1.5">
            <Stars value={piece.rating_at_publication} size={12} />
            <span className="text-[12px] text-muted">rated by the client</span>
          </div>
        )}
      </div>
    </Card>
  );
}

export default function ShowcasePage() {
  const { surface } = useSession();
  const [category, setCategory] = React.useState<string | null>(null);

  const { data, loading, error } = useLoader(
    () => discovery.showcase({ category: category ?? undefined }),
    [category, surface],
  );

  return (
    <>
      <PageHeading
        title="Work showcase"
        description="Finished work, published with both sides' permission. Every piece here is backed by a real contract that was delivered, accepted, and reviewed."
      />

      {error && <Alert tone="critical">{error}</Alert>}

      {loading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((key) => (
            <Skeleton key={key} className="h-80" />
          ))}
        </div>
      ) : data && data.results.length > 0 ? (
        <>
          {category && (
            <button
              type="button"
              onClick={() => setCategory(null)}
              className={cn(
                "mb-4 inline-flex items-center gap-1.5 rounded-full border border-line bg-raised",
                "px-3 py-1.5 text-[12.5px] text-muted hover:text-fg",
              )}
            >
              {category}
              <Icon name="x" className="size-3" strokeWidth={2.6} />
            </button>
          )}
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {data.results.map((piece) => (
              <Piece key={piece.id} piece={piece} />
            ))}
          </div>
        </>
      ) : (
        <Card>
          <EmptyState
            icon={<Icon name="sparkles" className="size-5" />}
            title="Nothing published yet"
            description="When a contract completes, both sides are asked whether the work can be shown here. Published pieces appear as they are approved."
          />
        </Card>
      )}
    </>
  );
}

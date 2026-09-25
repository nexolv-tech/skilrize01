"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { CoverArt, motifFor } from "@/components/artwork";
import {
  Alert,
  Avatar,
  Badge,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  Money,
  Segmented,
  Skeleton,
  Stars,
  Tag,
  cn,
} from "@/components/ui";
import { gigs, type GigDetail, type Package, type Tier } from "@/lib/api";
import { useLoader } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Package picker — the buying decision                                       */
/* -------------------------------------------------------------------------- */

function PackagePanel({ gig }: { gig: GigDetail }) {
  const active = gig.packages.filter((p) => p.is_active);
  const [tier, setTier] = React.useState<Tier>(active[0]?.tier ?? "basic");
  const [chosenExtras, setChosenExtras] = React.useState<number[]>([]);

  const selected: Package | undefined = active.find((p) => p.tier === tier) ?? active[0];
  const extras = gig.extras.filter((e) => e.is_active);

  const total =
    Number(selected?.price ?? 0) +
    extras
      .filter((extra) => chosenExtras.includes(extra.id))
      .reduce((sum, extra) => sum + Number(extra.price), 0);

  const days =
    (selected?.delivery_days ?? 0) +
    extras
      .filter((extra) => chosenExtras.includes(extra.id))
      .reduce((sum, extra) => sum + extra.extra_days, 0);

  const query = new URLSearchParams({ package: selected?.tier ?? "basic" });
  if (chosenExtras.length) query.set("extras", chosenExtras.join(","));
  const checkoutHref = `/checkout/${gig.id}?${query.toString()}`;

  if (!selected) {
    return (
      <Card>
        <EmptyState title="No packages available" description="This seller has not priced it yet." />
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      {active.length > 1 && (
        <div className="border-b border-line p-3">
          <Segmented
            label="Package tier"
            size="sm"
            value={tier}
            onChange={setTier}
            options={active.map((p) => ({
              value: p.tier,
              label: p.tier.charAt(0).toUpperCase() + p.tier.slice(1),
            }))}
          />
        </div>
      )}

      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold text-fg">{selected.name}</h3>
            {selected.description && (
              <p className="mt-1 text-[13px] leading-relaxed text-muted">{selected.description}</p>
            )}
          </div>
          <p className="shrink-0 text-[22px] font-semibold tracking-tight text-fg">
            <Money amount={selected.price} />
          </p>
        </div>

        <div className="mt-4 flex gap-5 text-[12.5px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="clock" className="size-3.5" />
            {selected.delivery_days}-day delivery
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Icon name="layers" className="size-3.5" />
            {selected.has_unlimited_revisions
              ? "Unlimited revisions"
              : `${selected.revisions} revision${selected.revisions === 1 ? "" : "s"}`}
          </span>
        </div>

        {selected.features.length > 0 && (
          <ul className="mt-4 space-y-2 border-t border-line pt-4">
            {selected.features.map((feature) => (
              <li key={feature} className="flex gap-2.5 text-[13px] text-fg">
                <Icon name="check" className="mt-0.5 size-3.5 shrink-0 text-positive" strokeWidth={2.6} />
                {feature}
              </li>
            ))}
          </ul>
        )}

        {extras.length > 0 && (
          <fieldset className="mt-5 border-t border-line pt-4">
            <legend className="mb-2 text-[12.5px] font-medium text-fg">Add extras</legend>
            <div className="space-y-2">
              {extras.map((extra) => (
                <label
                  key={extra.id}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors duration-150",
                    chosenExtras.includes(extra.id)
                      ? "border-accent bg-accent-soft"
                      : "border-line hover:bg-sunken",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={chosenExtras.includes(extra.id)}
                    onChange={(event) =>
                      setChosenExtras((current) =>
                        event.target.checked
                          ? [...current, extra.id]
                          : current.filter((id) => id !== extra.id),
                      )
                    }
                    className="size-4 accent-[var(--accent)]"
                  />
                  <span className="min-w-0 flex-1 text-[13px] text-fg">
                    {extra.title}
                    {extra.extra_days !== 0 && (
                      <span className="ml-1 text-subtle">
                        ({extra.extra_days > 0 ? "+" : ""}
                        {extra.extra_days}d)
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 text-[13px] font-medium text-fg">
                    <Money amount={extra.price} />
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        )}

        <div className="mt-5 flex items-baseline justify-between border-t border-line pt-4">
          <span className="text-[13px] text-muted">Total · {Math.max(1, days)}-day delivery</span>
          <span className="text-[20px] font-semibold text-fg">
            <Money amount={total} />
          </span>
        </div>

        {/* Checkout is public, so this is offered to everyone but the seller:
            a guest signs in from checkout, and anyone who cannot buy yet is
            told why there, next to the order they were building. */}
        {gig.is_owner ? (
          <Alert tone="neutral" className="mt-4">
            This is your own service.
          </Alert>
        ) : (
          <ButtonLink href={checkoutHref} block size="lg" className="mt-4">
            Continue to checkout · <Money amount={total} />
          </ButtonLink>
        )}

        <p className="mt-3 text-center text-[11.5px] leading-relaxed text-subtle">
          Your payment is held in escrow and only released when you accept the delivery.
        </p>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

export default function GigDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: gig, loading } = useLoader(() => gigs.detail(params.id), [params.id]);
  const [frame, setFrame] = React.useState(0);

  if (loading) {
    return (
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="aspect-[16/9] w-full" />
        </div>
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!gig) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="search" className="size-5" />}
          title="This service is not available"
          description="It may have been paused or withdrawn by the seller."
          action={
            <ButtonLink href="/gigs" variant="secondary">
              Back to the catalogue
            </ButtonLink>
          }
        />
      </Card>
    );
  }

  const motif = motifFor(gig.category?.name);
  const images = gig.gallery_urls;

  return (
    <>
      <nav className="mb-5 flex items-center gap-1.5 text-[13px] text-muted" aria-label="Breadcrumb">
        <Link href="/gigs" className="transition-colors hover:text-fg">
          Services
        </Link>
        {gig.category && (
          <>
            <Icon name="chevronLeft" className="size-3 rotate-180" />
            <Link
              href={`/gigs?category=${gig.category.slug}`}
              className="transition-colors hover:text-fg"
            >
              {gig.category.name}
            </Link>
          </>
        )}
      </nav>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          <div>
            <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-fg">
              {gig.title}
            </h1>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Avatar
                  name={gig.seller.display_name}
                  src={gig.seller.avatar_url}
                  size={28}
                />
                <Link
                  href={`/u/${gig.seller.handle}`}
                  className="text-[13.5px] font-medium text-fg underline-offset-2 hover:underline"
                >
                  {gig.seller.display_name}
                </Link>
              </div>
              {gig.seller.is_verified_student && (
                <Badge tone="accent">{gig.seller.university_name ?? "Verified student"}</Badge>
              )}
              {gig.rating_count > 0 ? (
                <span className="flex items-center gap-1.5 text-[13px]">
                  <Stars value={Number(gig.rating_average ?? 0)} size={13} />
                  <span className="font-medium text-fg">{gig.rating_average}</span>
                  <span className="text-subtle">({gig.rating_count})</span>
                </span>
              ) : (
                <span className="text-[13px] text-subtle">New service</span>
              )}
              {gig.orders_count > 0 && (
                <span className="text-[13px] text-subtle">{gig.orders_count} orders</span>
              )}
            </div>
          </div>

          {/* Gallery. Generated art stands in until the seller uploads. */}
          <div className="overflow-hidden rounded-xl border border-line bg-sunken">
            <div className="aspect-[16/9]">
              {images.length > 0 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={images[frame] ?? images[0]}
                  alt=""
                  className="size-full object-cover"
                />
              ) : (
                <CoverArt seed={gig.slug || gig.id} motif={motif} rounded={false} />
              )}
            </div>
            {images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto p-3">
                {images.map((url, index) => (
                  <button
                    key={url}
                    type="button"
                    onClick={() => setFrame(index)}
                    aria-label={`Image ${index + 1}`}
                    aria-current={index === frame}
                    className={cn(
                      "h-14 w-20 shrink-0 overflow-hidden rounded-md border-2 transition-colors",
                      index === frame ? "border-accent" : "border-transparent hover:border-line-strong",
                    )}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={url} alt="" className="size-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <Card className="p-6">
            <h2 className="text-[15px] font-semibold text-fg">About this service</h2>
            <p className="mt-3 whitespace-pre-wrap text-[14.5px] leading-relaxed text-fg">
              {gig.description}
            </p>

            {gig.tags.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-1.5 border-t border-line pt-4">
                {gig.tags.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </div>
            )}
          </Card>

          {gig.requirements.length > 0 && (
            <Card>
              <CardHeader
                title="What the seller needs from you"
                description="You will answer these after ordering. The delivery clock starts when you do — not before."
              />
              <ul className="divide-y divide-line">
                {gig.requirements.map((field, index) => (
                  <li key={field.key} className="flex gap-3 px-5 py-3.5">
                    <span className="text-[13px] font-medium text-subtle">{index + 1}.</span>
                    <span className="text-[13.5px] text-fg">
                      {field.label}
                      {field.required !== false && (
                        <span className="ml-1 text-critical" aria-label="required">
                          *
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {gig.faq.length > 0 && (
            <Card>
              <CardHeader title="Frequently asked" />
              <dl className="divide-y divide-line">
                {gig.faq.map((item) => (
                  <div key={item.question} className="px-5 py-4">
                    <dt className="text-[13.5px] font-medium text-fg">{item.question}</dt>
                    <dd className="mt-1 text-[13px] leading-relaxed text-muted">{item.answer}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <PackagePanel gig={gig} />
        </aside>
      </div>
    </>
  );
}

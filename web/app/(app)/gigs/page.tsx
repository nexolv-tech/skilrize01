"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { GigCard } from "@/components/marketing";
import {
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Select,
  Skeleton,
  Tag,
  cn,
  ButtonLink,
} from "@/components/ui";
import { gigs, marketplace, type Category } from "@/lib/api";
import { useLoader, useSession } from "@/lib/session";

const SORTS = [
  ["popular", "Most ordered"],
  ["rating", "Best rated"],
  ["newest", "Newest"],
] as const;

const DELIVERY = [
  ["", "Any delivery time"],
  ["1", "Within 24 hours"],
  ["3", "Up to 3 days"],
  ["7", "Up to 7 days"],
] as const;


function CatalogueContent() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useSession();
  const searchRef = React.useRef<HTMLInputElement>(null);

  const filters = React.useMemo(
    () => ({
      q: params.get("q") ?? "",
      category: params.get("category") ?? "",
      delivery_days: params.get("delivery_days") ?? "",
      price_max: params.get("price_max") ?? "",
      sort: params.get("sort") ?? "popular",
    }),
    [params],
  );

  const categoryQuery = useLoader(() => marketplace.categories(), []);
  const categories: Category[] = categoryQuery.data ?? [];
  const { data: page, loading } = useLoader(() => gigs.list(filters), [filters]);

  function apply(patch: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    router.push(`/gigs?${next.toString()}`);
  }

  const activeCategory = categories.find((c) => c.slug === filters.category);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4 pb-6">
        <div>
          <h1 className="display-md text-fg">
            {activeCategory ? activeCategory.name : "Browse services"}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {loading
              ? "Loading services…"
              : `${page?.count ?? 0} ${page?.count === 1 ? "service" : "services"} available`}
          </p>
        </div>
        {user && (
          <ButtonLink href="/gigs/new" variant="secondary">
            <Icon name="plus" className="size-4" />
            Publish a service
          </ButtonLink>
        )}
      </div>

      {/* Category rail — the fastest way into the catalogue. */}
      {categories.length > 0 && (
        <div className="mb-5 flex gap-2 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <button
            type="button"
            onClick={() => apply({ category: "" })}
            className={cn(
              "shrink-0 rounded-full border px-3.5 py-1.5 text-[13px] transition-colors duration-150",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              !filters.category
                ? "border-accent bg-accent-soft text-accent"
                : "border-line text-muted hover:border-line-strong hover:text-fg",
            )}
          >
            All
          </button>
          {categories.map((category) => (
            <button
              key={category.slug}
              type="button"
              onClick={() => apply({ category: category.slug })}
              className={cn(
                "shrink-0 rounded-full border px-3.5 py-1.5 text-[13px] transition-colors duration-150",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                filters.category === category.slug
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-muted hover:border-line-strong hover:text-fg",
              )}
            >
              {category.name}
            </button>
          ))}
        </div>
      )}

      <Card className="mb-6 p-4">
        <form
          className="flex flex-wrap items-center gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            apply({ q: searchRef.current?.value ?? "" });
          }}
        >
          <div className="relative min-w-56 flex-1">
            <Icon
              name="search"
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
            />
            <label htmlFor="gig-search" className="sr-only">
              Search services
            </label>
            <Input
              key={filters.q}
              id="gig-search"
              ref={searchRef}
              defaultValue={filters.q}
              placeholder="What are you looking for?"
              className="pl-9"
            />
          </div>

          <Select
            aria-label="Delivery time"
            value={filters.delivery_days}
            onChange={(event) => apply({ delivery_days: event.target.value })}
            className="w-auto! min-w-44"
          >
            {DELIVERY.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>

          <Select
            aria-label="Maximum price"
            value={filters.price_max}
            onChange={(event) => apply({ price_max: event.target.value })}
            className="w-auto! min-w-40"
          >
            <option value="">Any budget</option>
            <option value="5000">Under Rs 5,000</option>
            <option value="15000">Under Rs 15,000</option>
            <option value="50000">Under Rs 50,000</option>
          </Select>

          <Select
            aria-label="Sort by"
            value={filters.sort}
            onChange={(event) => apply({ sort: event.target.value })}
            className="w-auto! min-w-40"
          >
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>

          <Button type="submit" size="sm">
            Search
          </Button>
        </form>

        {filters.q && (
          <div className="mt-3 flex items-center gap-2 border-t border-line pt-3">
            <span className="text-[12px] text-subtle">Searching:</span>
            <Tag onRemove={() => apply({ q: "" })}>&ldquo;{filters.q}&rdquo;</Tag>
          </div>
        )}
      </Card>

      {loading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((row) => (
            <Card key={row} className="overflow-hidden p-0">
              <Skeleton className="aspect-[16/10] rounded-none" />
              <div className="space-y-2 p-4">
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </Card>
          ))}
        </div>
      ) : !page || page.results.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="search" className="size-5" />}
            title="No services match yet"
            description="Try another category, or be the first to publish one here."
            action={
              user ? (
                <ButtonLink href="/gigs/new">Publish a service</ButtonLink>
              ) : (
                <ButtonLink href="/signup">Create an account</ButtonLink>
              )
            }
          />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {page.results.map((gig) => (
            <GigCard key={gig.id} gig={gig} />
          ))}
        </div>
      )}
    </>
  );
}

export default function GigsPage() {
  return (
    <React.Suspense
      fallback={
        <div className="space-y-4 py-10">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-24 w-full" />
        </div>
      }
    >
      <CatalogueContent />
    </React.Suspense>
  );
}

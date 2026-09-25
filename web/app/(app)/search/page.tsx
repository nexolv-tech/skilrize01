"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { LevelBadge, PromotedTag, SuccessScore } from "@/components/reputation";
import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Money,
  Segmented,
  Skeleton,
  cn,
} from "@/components/ui";
import {
  discovery,
  type FacetOption,
  type Faceted,
  type SearchGig,
  type SearchProject,
} from "@/lib/api";
import { useLoader, useSession } from "@/lib/session";

type Mode = "gigs" | "projects";

/**
 * One facet group.
 *
 * Counts come from the server, computed before the user's own selections were
 * applied — so an unselected option never reads zero just because something
 * else is selected, and the filters stay usable after the first click.
 */
function FacetGroup({
  title,
  options,
  selected,
  onSelect,
}: {
  title: string;
  options: FacetOption[];
  selected: string | null;
  onSelect: (value: string | null) => void;
}) {
  if (!options?.length) return null;

  return (
    <div className="border-b border-line py-4 last:border-0">
      <h3 className="mb-2.5 text-[12.5px] font-semibold text-fg">{title}</h3>
      <ul className="space-y-1">
        {options.map((option) => {
          const active = selected === option.value;
          return (
            <li key={option.value}>
              <button
                type="button"
                onClick={() => onSelect(active ? null : option.value)}
                aria-pressed={active}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-[13px]",
                  "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  active ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-sunken",
                )}
              >
                <span className="truncate">{option.label}</span>
                <span className="tabular shrink-0 text-[11.5px] text-subtle">{option.count}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The catalogue's card (components/marketing GigCard), with search's extras:
 *  the promoted label, seller level and job success score. */
function GigResult({ gig }: { gig: SearchGig }) {
  return (
    <article className="group relative flex flex-col rounded-lg border border-line bg-raised p-5 transition-[border-color,box-shadow] duration-200 hover:border-line-strong hover:shadow-e2">
      {(gig.category || gig.is_promoted) && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12.5px] text-subtle">{gig.category}</span>
          {gig.is_promoted && <PromotedTag />}
        </div>
      )}
      <h3 className="mt-1.5 line-clamp-2 text-[15.5px] font-semibold leading-snug text-fg">
        <Link
          href={`/gigs/${gig.id}`}
          onClick={() => void discovery.recordClick(gig.id)}
          className="rounded-sm underline-offset-4 after:absolute after:inset-0 group-hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {gig.title}
        </Link>
      </h3>

      <div className="mt-3 flex items-center gap-2 text-[13px]">
        <Avatar name={gig.seller.display_name} src={gig.seller.avatar_url} size={22} />
        <span className="truncate text-muted">{gig.seller.display_name}</span>
        <LevelBadge level={gig.seller.level} className="shrink-0" />
      </div>

      <div className="mt-auto flex items-end justify-between gap-3 pt-5">
        <span className="flex flex-col gap-1 text-[12.5px] text-subtle">
          {gig.rating_count > 0 ? `★ ${gig.rating_average} (${gig.rating_count})` : "New"}
          <SuccessScore score={gig.seller.job_success_score} />
        </span>
        <span className="text-right">
          <span className="block text-[11.5px] text-subtle">Starting at</span>
          <Money amount={gig.starting_price} className="text-[16px] font-semibold text-fg" />
        </span>
      </div>
    </article>
  );
}

export default function SearchPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { surface } = useSession();

  const [mode, setMode] = React.useState<Mode>(
    params.get("mode") === "projects" ? "projects" : "gigs",
  );
  const [term, setTerm] = React.useState(params.get("q") ?? "");
  const [submitted, setSubmitted] = React.useState(params.get("q") ?? "");
  const [filters, setFilters] = React.useState<Record<string, string | null>>({});
  const [sort, setSort] = React.useState("");

  const active = React.useMemo(
    () => Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as Record<string, string>,
    [filters],
  );

  // Explicitly a union rather than letting inference pick one branch: the two
  // modes return genuinely different rows, and narrowing at the render site is
  // honest about that.
  const { data, loading, error } = useLoader<Faceted<SearchGig> | Faceted<SearchProject>>(
    () =>
      mode === "gigs"
        ? discovery.searchGigs({ q: submitted || undefined, sort: sort || undefined, ...active })
        : discovery.searchProjects({
            q: submitted || undefined,
            sort: sort || undefined,
            ...active,
          }),
    [mode, submitted, sort, JSON.stringify(active), surface],
  );

  const setFacet = (key: string) => (value: string | null) =>
    setFilters((previous) => ({ ...previous, [key]: value }));

  const clearAll = () => setFilters({});
  const activeCount = Object.keys(active).length;

  return (
    <>
      <PageHeading
        title="Search"
        description={
          surface === "university"
            ? "Searching inside your campus portal. Global listings are not included."
            : "Search the global marketplace."
        }
      />

      <form
        className="mb-6 flex flex-wrap gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(term);
          router.replace(`/search?q=${encodeURIComponent(term)}&mode=${mode}`);
        }}
      >
        <div className="relative min-w-64 flex-1">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
          />
          <Input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder='Try "logo design" or build -website'
            aria-label="Search"
            className="pl-9"
          />
        </div>
        <Segmented
          label="What to search"
          value={mode}
          onChange={(next) => {
            setMode(next);
            clearAll();
          }}
          options={[
            { value: "gigs", label: "Services", icon: "layers" },
            { value: "projects", label: "Projects", icon: "briefcase" },
          ]}
        />
        <Button type="submit">Search</Button>
      </form>

      {error && <Alert tone="critical">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
        <aside>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-fg">Filters</h2>
              {activeCount > 0 && (
                <button
                  type="button"
                  onClick={clearAll}
                  className="text-[12px] font-medium text-accent underline-offset-4 hover:underline"
                >
                  Clear ({activeCount})
                </button>
              )}
            </div>

            {loading && !data ? (
              <Skeleton className="mt-4 h-48" />
            ) : (
              Object.entries(data?.facets ?? {}).map(([name, options]) => (
                <FacetGroup
                  key={name}
                  title={
                    name === "level"
                      ? "Seller level"
                      : `${(name[0] ?? "").toUpperCase()}${name.slice(1)}`
                  }
                  options={options}
                  selected={filters[name] ?? null}
                  onSelect={setFacet(name)}
                />
              ))
            )}
          </Card>
        </aside>

        <div>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13.5px] text-muted">
              {loading
                ? "Searching…"
                : `${data?.count ?? 0} result${(data?.count ?? 0) === 1 ? "" : "s"}`}
              {submitted && (
                <>
                  {" "}
                  for <span className="font-medium text-fg">“{submitted}”</span>
                </>
              )}
            </p>
            <Segmented
              label="Sort"
              size="sm"
              value={sort}
              onChange={setSort}
              options={[
                { value: "", label: "Best match" },
                { value: "newest", label: "Newest" },
                ...(mode === "gigs"
                  ? ([
                      { value: "rating", label: "Rating" },
                      { value: "price", label: "Price" },
                    ] as const)
                  : []),
              ]}
            />
          </div>

          {loading ? (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2, 3, 4, 5].map((key) => (
                <Skeleton key={key} className="h-72" />
              ))}
            </div>
          ) : data && data.results.length > 0 ? (
            mode === "gigs" ? (
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {(data.results as SearchGig[]).map((gig) => (
                  <GigResult key={gig.id} gig={gig} />
                ))}
              </div>
            ) : (
              <Card>
                <ul className="divide-y divide-line">
                  {(data.results as SearchProject[]).map((project) => (
                    <li key={project.id}>
                      <Link
                        href={`/projects/${project.id}`}
                        className="block p-5 transition-colors hover:bg-sunken"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-[15px] font-medium text-fg">{project.title}</p>
                          <Badge>{project.project_type}</Badge>
                        </div>
                        <p className="mt-1.5 line-clamp-2 text-[13.5px] text-muted">
                          {project.description}
                        </p>
                        <p className="mt-2 text-[12.5px] text-subtle">
                          {project.budget_display} · {project.proposal_count} proposals
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )
          ) : (
            <Card>
              <EmptyState
                icon={<Icon name="search" className="size-5" />}
                title="Nothing matched"
                description={
                  activeCount > 0
                    ? "Try clearing a filter, or search for something broader."
                    : "Try different words — misspellings are handled, so it is probably the term."
                }
                action={
                  activeCount > 0 ? (
                    <Button variant="secondary" size="sm" onClick={clearAll}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

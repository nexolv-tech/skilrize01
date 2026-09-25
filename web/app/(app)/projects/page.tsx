"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Money,
  Select,
  Skeleton,
  Tag,
  cn,
} from "@/components/ui";
import {
  marketplace,
  type Category,
  type Paginated,
  type ProjectSummary,
} from "@/lib/api";
import { formatRelative, useLoader, useSession } from "@/lib/session";

const EXPERIENCE = [
  ["", "Any experience"],
  ["entry", "Entry level"],
  ["intermediate", "Intermediate"],
  ["expert", "Expert"],
] as const;

const SORTS = [
  ["newest", "Newest first"],
  ["budget", "Highest budget"],
  ["proposals", "Fewest proposals"],
] as const;

function ProjectCard({ project }: { project: ProjectSummary }) {
  return (
    <Card
      as="article"
      className="group p-5 transition-[border-color,box-shadow] duration-200 hover:border-line-strong hover:shadow-e2"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[16px] font-semibold leading-snug tracking-[-0.01em] text-fg">
            <Link
              href={`/projects/${project.id}`}
              className="rounded-sm after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {project.title}
            </Link>
          </h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-subtle">
            <span>{project.category_name ?? "General"}</span>
            <span aria-hidden>·</span>
            <span className="capitalize">{project.experience_level}</span>
            {project.published_at && (
              <>
                <span aria-hidden>·</span>
                <span>Posted {formatRelative(project.published_at)}</span>
              </>
            )}
          </p>
        </div>

        <div className="shrink-0 text-right">
          <p className="text-[15px] font-semibold text-fg">
            <Money amount={project.budget_max ?? project.rate_max} />
            {project.project_type === "hourly" && (
              <span className="text-[12px] font-normal text-muted">/hr</span>
            )}
          </p>
          <p className="text-[12px] text-subtle">
            {project.project_type === "hourly" ? "Hourly" : "Fixed price"}
          </p>
        </div>
      </div>

      <p className="mt-3 line-clamp-3 text-[13.5px] leading-relaxed text-muted">
        {project.description}
      </p>

      {project.skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {project.skills.slice(0, 6).map((skill) => (
            <Tag key={skill.id}>{skill.name}</Tag>
          ))}
          {project.skills.length > 6 && <Tag>+{project.skills.length - 6}</Tag>}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-3 text-[12.5px] text-subtle">
        <span className="inline-flex items-center gap-1.5">
          <Icon name="send" className="size-3.5" />
          {project.proposal_count} {project.proposal_count === 1 ? "proposal" : "proposals"}
        </span>
        {project.weekly_hours && (
          <span className="inline-flex items-center gap-1.5">
            <Icon name="clock" className="size-3.5" />
            {project.weekly_hours} hrs/week
          </span>
        )}
        {project.expected_duration_days && (
          <span className="inline-flex items-center gap-1.5">
            <Icon name="clock" className="size-3.5" />
            About {project.expected_duration_days} days
          </span>
        )}
        {project.client_country && (
          <span className="inline-flex items-center gap-1.5">
            <Icon name="globe" className="size-3.5" />
            {project.client_country}
          </span>
        )}
        {project.verified_students_only && (
          <Badge tone="accent" className="ml-auto">
            Students only
          </Badge>
        )}
      </div>
    </Card>
  );
}

function BrowseContent() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useSession();

  // The URL is the source of truth for filters, so a filtered browse is
  // shareable and the back button behaves.
  const filters = React.useMemo(
    () => ({
      q: params.get("q") ?? "",
      category: params.get("category") ?? "",
      type: params.get("type") ?? "",
      experience: params.get("experience") ?? "",
      sort: params.get("sort") ?? "newest",
    }),
    [params],
  );

  // Uncontrolled, keyed on the applied term: navigating (or clearing a filter
  // chip) remounts the input with the new value, so no effect has to mirror
  // the URL into state.
  const searchRef = React.useRef<HTMLInputElement>(null);

  const categoryQuery = useLoader(() => marketplace.categories(), []);
  const categories: Category[] = categoryQuery.data ?? [];

  const { data: page, loading } = useLoader<Paginated<ProjectSummary>>(
    () => marketplace.projects(filters),
    [filters],
  );

  function apply(patch: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    router.push(`/projects?${next.toString()}`);
  }

  const activeFilters = [
    filters.category && {
      key: "category",
      label: categories.find((c) => c.slug === filters.category)?.name ?? filters.category,
    },
    filters.type && { key: "type", label: filters.type === "hourly" ? "Hourly" : "Fixed price" },
    filters.experience && { key: "experience", label: filters.experience },
  ].filter(Boolean) as Array<{ key: string; label: string }>;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4 pb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">Find work</h1>
          <p className="mt-1 text-sm text-muted">
            {loading
              ? "Loading open briefs…"
              : `${page?.count ?? 0} open ${page?.count === 1 ? "brief" : "briefs"} right now`}
          </p>
        </div>
        {user && (
          <Link href="/projects/new">
            <Button variant="secondary">
              <Icon name="plus" className="size-4" />
              Post a project
            </Button>
          </Link>
        )}
      </div>

      {/* Filter bar */}
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
            <label htmlFor="browse-search" className="sr-only">
              Search briefs
            </label>
            <Input
              key={filters.q}
              id="browse-search"
              ref={searchRef}
              defaultValue={filters.q}
              placeholder="Search by title or description"
              className="pl-9"
            />
          </div>

          <Select
            aria-label="Category"
            value={filters.category}
            onChange={(event) => apply({ category: event.target.value })}
            className="w-auto! min-w-44"
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.name}
              </option>
            ))}
          </Select>

          <Select
            aria-label="Project type"
            value={filters.type}
            onChange={(event) => apply({ type: event.target.value })}
            className="w-auto! min-w-36"
          >
            <option value="">Any type</option>
            <option value="fixed">Fixed price</option>
            <option value="hourly">Hourly</option>
          </Select>

          <Select
            aria-label="Experience level"
            value={filters.experience}
            onChange={(event) => apply({ experience: event.target.value })}
            className="w-auto! min-w-40"
          >
            {EXPERIENCE.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
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

        {(activeFilters.length > 0 || filters.q) && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <span className="text-[12px] text-subtle">Filtering by:</span>
            {filters.q && (
              <Tag onRemove={() => apply({ q: "" })}>&ldquo;{filters.q}&rdquo;</Tag>
            )}
            {activeFilters.map((filter) => (
              <Tag key={filter.key} onRemove={() => apply({ [filter.key]: "" })}>
                <span className="capitalize">{filter.label}</span>
              </Tag>
            ))}
            <button
              type="button"
              onClick={() => router.push("/projects")}
              className="ml-1 text-[12px] text-accent underline-offset-2 hover:underline"
            >
              Clear all
            </button>
          </div>
        )}
      </Card>

      {/* Results */}
      {loading ? (
        <div className="space-y-4">
          {[0, 1, 2, 3].map((row) => (
            <Card key={row} className="space-y-3 p-5">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-12 w-full" />
            </Card>
          ))}
        </div>
      ) : !page || page.results.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="search" className="size-5" />}
            title="No briefs match those filters"
            description="Try widening the category or clearing the search term."
            action={
              <Button variant="secondary" onClick={() => router.push("/projects")}>
                Clear filters
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          <div className="space-y-4">
            {page.results.map((project) => (
              <div key={project.id} className="relative">
                <ProjectCard project={project} />
              </div>
            ))}
          </div>

          {(page.next || page.previous) && (
            <nav
              aria-label="Pagination"
              className="mt-8 flex items-center justify-center gap-3"
            >
              <Button
                variant="secondary"
                size="sm"
                disabled={!page.previous}
                onClick={() => {
                  const current = Number(params.get("page") ?? 1);
                  apply({ page: String(Math.max(1, current - 1)) });
                }}
              >
                <Icon name="chevronLeft" className="size-4" />
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={!page.next}
                onClick={() => {
                  const current = Number(params.get("page") ?? 1);
                  apply({ page: String(current + 1) });
                }}
              >
                Next
                <Icon name="chevronLeft" className={cn("size-4 rotate-180")} />
              </Button>
            </nav>
          )}
        </>
      )}
    </>
  );
}

export default function ProjectsPage() {
  return (
    <React.Suspense
      fallback={
        <div className="space-y-4 py-10">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-24 w-full" />
        </div>
      }
    >
      <BrowseContent />
    </React.Suspense>
  );
}

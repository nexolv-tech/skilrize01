"use client";

/**
 * Agencies and shared workspaces.
 *
 * An agency is a way to sell jointly — it never absorbs a member's profile,
 * reputation, or earnings history, so leaving one takes your reviews with you.
 * That is a product decision made in the model, and the copy here says it out
 * loud because it is the first question anyone asks before joining someone
 * else's team.
 */

import * as React from "react";

import { ActionError, PlanBadge, UpgradePrompt, useEntitlements } from "@/components/professional";
import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Segmented,
  Select,
  Skeleton,
  Textarea,
} from "@/components/ui";
import {
  professional,
  type AgencyTeam,
  type Entitlements,
  type SharedWorkspace,
} from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Agencies                                                                   */
/* -------------------------------------------------------------------------- */

function MemberList({ agency, onChanged }: { agency: AgencyTeam; onChanged: () => void }) {
  const { user } = useSession();
  const members = useLoader(() => professional.agencyMembers(agency.id), [agency.id]);
  const invite = useAsyncAction(professional.inviteToAgency);
  const remove = useAsyncAction(professional.removeMember);
  const [form, setForm] = React.useState({ handle: "", role: "member" });

  const canManage = agency.my_role === "owner" || agency.my_role === "admin";

  return (
    <div className="space-y-4">
      {members.loading ? (
        <Skeleton className="h-24" />
      ) : (
        <ul className="space-y-2">
          {members.data?.map((member) => (
            <li key={member.id} className="flex items-center gap-3">
              <Avatar name={member.display_name} src={member.avatar_url} size={32} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-fg">{member.display_name}</p>
                <p className="text-[12px] text-subtle">@{member.handle}</p>
              </div>
              {member.revenue_share > 0 && (
                <span className="tabular hidden text-[12px] text-muted sm:block">
                  {member.revenue_share}%
                </span>
              )}
              <Badge tone={member.status === "invited" ? "caution" : "neutral"}>
                {member.status === "invited" ? "Invited" : member.role}
              </Badge>
              {canManage && member.role !== "owner" && member.user !== user?.id && (
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove ${member.display_name}`}
                  onClick={async () => {
                    if (await remove.run(agency.id, member.id)) {
                      void members.reload();
                      onChanged();
                    }
                  }}
                >
                  <Icon name="x" className="size-3.5" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {remove.error && <Alert tone="critical">{remove.error}</Alert>}

      {canManage && (
        <form
          className="flex flex-wrap gap-2 border-t border-line pt-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await invite.run(agency.id, form.handle.replace(/^@/, ""), form.role)) {
              setForm({ handle: "", role: "member" });
              void members.reload();
              onChanged();
            }
          }}
        >
          <Input
            required
            value={form.handle}
            placeholder="@handle"
            onChange={(event) => setForm({ ...form, handle: event.target.value })}
            className="min-w-40 flex-1"
            aria-label="Handle to invite"
          />
          <Select
            aria-label="Role"
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value })}
            className="w-32"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </Select>
          <Button type="submit" loading={invite.pending}>
            Invite
          </Button>
        </form>
      )}
      <ActionError error={invite.error} code={invite.code} />
    </div>
  );
}

function AgencyCard({ agency, onChanged }: { agency: AgencyTeam; onChanged: () => void }) {
  const [open, setOpen] = React.useState(false);
  const accept = useAsyncAction(professional.acceptAgency);
  const invited = agency.my_status === "invited";

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            {agency.name}
            {agency.my_role && <Badge tone="accent">{agency.my_role}</Badge>}
            {invited && <Badge tone="caution">Invitation</Badge>}
          </span>
        }
        description={agency.tagline || `${agency.seats_used} member${agency.seats_used === 1 ? "" : "s"}`}
        action={
          invited ? (
            <Button
              size="sm"
              loading={accept.pending}
              onClick={async () => {
                if (await accept.run(agency.id)) onChanged();
              }}
            >
              Accept
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>
              {open ? "Hide" : "Members"}
            </Button>
          )
        }
      />
      {accept.error && (
        <div className="p-5 pt-0">
          <Alert tone="critical">{accept.error}</Alert>
        </div>
      )}
      {open && !invited && (
        <div className="p-5">
          {agency.description && (
            <p className="mb-4 whitespace-pre-wrap text-[13px] leading-relaxed text-muted">
              {agency.description}
            </p>
          )}
          <MemberList agency={agency} onChanged={onChanged} />
        </div>
      )}
    </Card>
  );
}

function AgenciesPanel({ rights }: { rights: Entitlements | null }) {
  const [creating, setCreating] = React.useState(false);
  const agencies = useLoader(() => professional.agencies({ mine: "true" }), []);
  const create = useAsyncAction(professional.createAgency);
  const [form, setForm] = React.useState({ name: "", tagline: "", description: "" });

  const reload = React.useCallback(() => void agencies.reload(), [agencies]);
  const rows = agencies.data?.results ?? [];

  if (rights && !rights.can_create_agency && rows.length === 0) {
    return (
      <UpgradePrompt
        tier="elite"
        title="Agencies are an Elite feature"
        description="Bring other freelancers under one team, split revenue per member, and share a client pipeline. Everyone keeps their own profile and reviews."
      />
    );
  }

  return (
    <div className="space-y-5">
      {rights?.can_create_agency && (
        <Card>
          <CardHeader
            title="Your agencies"
            description={`Your plan includes ${rights.team_seats} seats.`}
            action={
              <Button
                size="sm"
                variant={creating ? "ghost" : "secondary"}
                onClick={() => setCreating(!creating)}
              >
                {creating ? "Cancel" : <><Icon name="plus" className="size-3.5" /> New agency</>}
              </Button>
            }
          />
          {creating && (
            <form
              className="space-y-4 p-5"
              onSubmit={async (event) => {
                event.preventDefault();
                if (await create.run(form)) {
                  setForm({ name: "", tagline: "", description: "" });
                  setCreating(false);
                  reload();
                }
              }}
            >
              <Field label="Name" htmlFor="agency-name" required error={create.fieldErrors.name}>
                <Input
                  id="agency-name"
                  required
                  maxLength={120}
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </Field>
              <Field label="Tagline" htmlFor="agency-tagline" hint="One line on what the team does.">
                <Input
                  id="agency-tagline"
                  maxLength={180}
                  value={form.tagline}
                  onChange={(event) => setForm({ ...form, tagline: event.target.value })}
                />
              </Field>
              <Field label="Description" htmlFor="agency-description">
                <Textarea
                  id="agency-description"
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </Field>
              <Button type="submit" loading={create.pending}>
                Create agency
              </Button>
              <ActionError error={create.error} code={create.code} />
            </form>
          )}
        </Card>
      )}

      {agencies.loading ? (
        <Skeleton className="h-28" />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="building" className="size-5" />}
            title="No agencies yet"
            description="Create one to sell jointly with other freelancers, or wait to be invited to somebody else's."
          />
        </Card>
      ) : (
        rows.map((agency) => (
          <AgencyCard key={agency.id} agency={agency} onChanged={reload} />
        ))
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Workspaces                                                                 */
/* -------------------------------------------------------------------------- */

function WorkspaceCard({
  workspace,
  onChanged,
}: {
  workspace: SharedWorkspace;
  onChanged: () => void;
}) {
  const [inviting, setInviting] = React.useState(false);
  const invite = useAsyncAction(professional.inviteToWorkspace);
  const [form, setForm] = React.useState({ handle: "", isClient: false });

  return (
    <Card>
      <CardHeader
        title={workspace.name}
        description={
          workspace.description ||
          `${workspace.members.length} member${workspace.members.length === 1 ? "" : "s"} · ${workspace.contract_count} contract${workspace.contract_count === 1 ? "" : "s"}`
        }
        action={
          <Button size="sm" variant="ghost" onClick={() => setInviting(!inviting)}>
            {inviting ? "Close" : "Add people"}
          </Button>
        }
      />

      <div className="space-y-4 p-5">
        <ul className="flex flex-wrap gap-2">
          {workspace.members.map((member) => (
            <li key={member.id} className="flex items-center gap-2 rounded-md bg-sunken px-2.5 py-1.5">
              <Avatar name={member.display_name} size={20} />
              <span className="text-[12.5px] text-fg">{member.display_name}</span>
              {member.is_client && <Badge tone="accent">Client</Badge>}
            </li>
          ))}
        </ul>

        {inviting && (
          <form
            className="flex flex-wrap items-end gap-3 border-t border-line pt-4"
            onSubmit={async (event) => {
              event.preventDefault();
              if (await invite.run(workspace.id, form.handle.replace(/^@/, ""), form.isClient)) {
                setForm({ handle: "", isClient: false });
                setInviting(false);
                onChanged();
              }
            }}
          >
            <Input
              required
              value={form.handle}
              placeholder="@handle"
              onChange={(event) => setForm({ ...form, handle: event.target.value })}
              className="min-w-40 flex-1"
              aria-label="Handle to add"
            />
            <label className="flex items-center gap-2 pb-2.5 text-[13px] text-fg">
              <input
                type="checkbox"
                checked={form.isClient}
                onChange={(event) => setForm({ ...form, isClient: event.target.checked })}
                className="size-4 accent-[var(--color-accent)]"
              />
              They are the client
            </label>
            <Button type="submit" loading={invite.pending}>
              Add
            </Button>
          </form>
        )}
        <ActionError error={invite.error} code={invite.code} />
      </div>
    </Card>
  );
}

function WorkspacesPanel() {
  const [creating, setCreating] = React.useState(false);
  const workspaces = useLoader(() => professional.workspaces(), []);
  const create = useAsyncAction(professional.createWorkspace);
  const [form, setForm] = React.useState({ name: "", description: "" });

  const reload = React.useCallback(() => void workspaces.reload(), [workspaces]);
  const rows = workspaces.data?.results ?? [];

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Shared workspaces"
          description="One space per client engagement — your side and theirs, with the contracts attached."
          action={
            <Button
              size="sm"
              variant={creating ? "ghost" : "secondary"}
              onClick={() => setCreating(!creating)}
            >
              {creating ? "Cancel" : <><Icon name="plus" className="size-3.5" /> New workspace</>}
            </Button>
          }
        />
        {creating && (
          <form
            className="space-y-4 p-5"
            onSubmit={async (event) => {
              event.preventDefault();
              if (await create.run(form)) {
                setForm({ name: "", description: "" });
                setCreating(false);
                reload();
              }
            }}
          >
            <Field label="Name" htmlFor="workspace-name" required error={create.fieldErrors.name}>
              <Input
                id="workspace-name"
                required
                value={form.name}
                placeholder="Acme — website rebuild"
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label="What is this for?" htmlFor="workspace-description">
              <Textarea
                id="workspace-description"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            <Button type="submit" loading={create.pending}>
              Create workspace
            </Button>
            <ActionError error={create.error} code={create.code} />
          </form>
        )}
      </Card>

      {workspaces.loading ? (
        <Skeleton className="h-28" />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="layers" className="size-5" />}
            title="No workspaces yet"
            description="Open one per client so everything for that engagement — people, contracts, and context — lives in one place."
          />
        </Card>
      ) : (
        rows.map((workspace) => (
          <WorkspaceCard key={workspace.id} workspace={workspace} onChanged={reload} />
        ))
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export default function TeamsPage() {
  const [tab, setTab] = React.useState<"agencies" | "workspaces">("agencies");
  const { rights } = useEntitlements();

  return (
    <>
      <PageHeading
        title="Teams"
        description="Sell as a team without giving up your own profile. Members keep their reviews, their level, and their earnings history — an agency is a way to work together, not a way to pool identity."
        action={rights && <PlanBadge tier={rights.tier} name={rights.plan_name} />}
      />

      <div className="pb-6">
        <Segmented
          label="Teams section"
          value={tab}
          onChange={setTab}
          options={[
            { value: "agencies", label: "Agencies", icon: "building" },
            { value: "workspaces", label: "Workspaces", icon: "layers" },
          ]}
        />
      </div>

      {tab === "agencies" ? <AgenciesPanel rights={rights} /> : <WorkspacesPanel />}
    </>
  );
}

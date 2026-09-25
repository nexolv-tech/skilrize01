"use client";

import * as React from "react";

import { AdminHeading, AdminList } from "@/components/admin";
import { Alert, Badge, Button, Card, Input, Switch } from "@/components/ui";
import { admin, type AdminCategory } from "@/lib/api";
import { useLoader } from "@/lib/session";

function AddCategory({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  return (
    <Card className="mb-6 p-5">
      <form
        className="grid gap-3 md:grid-cols-[1fr_2fr_auto] md:items-end"
        onSubmit={async (event) => {
          event.preventDefault();
          setPending(true);
          setError(null);
          try {
            await admin.createCategory({ name, description });
            setName("");
            setDescription("");
            onAdded();
          } catch (caught) {
            setError((caught as { message?: string }).message ?? "Could not add it.");
          } finally {
            setPending(false);
          }
        }}
      >
        <label className="text-[12.5px] font-medium text-fg">
          New category
          <Input className="mt-1.5" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Video & Animation" />
        </label>
        <label className="text-[12.5px] font-medium text-fg">
          Short description
          <Input
            className="mt-1.5"
            value={description}
            maxLength={200}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What sellers offer in it, in a line"
          />
        </label>
        <Button type="submit" loading={pending} disabled={name.trim().length < 2}>
          Add category
        </Button>
      </form>
      {error && (
        <Alert tone="critical" className="mt-3">
          {error}
        </Alert>
      )}
    </Card>
  );
}

function CategoryRow({ row, onChanged }: { row: AdminCategory; onChanged: () => void }) {
  const [editing, setEditing] = React.useState(false);
  const [name, setName] = React.useState(row.name);
  const [description, setDescription] = React.useState(row.description);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save(body: Parameters<typeof admin.updateCategory>[1]) {
    setPending(true);
    setError(null);
    try {
      await admin.updateCategory(row.id, body);
      setEditing(false);
      onChanged();
    } catch (caught) {
      setError((caught as { message?: string }).message ?? "Could not save.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-wrap items-start gap-4 p-5">
      <div className="min-w-0 flex-1 space-y-1.5">
        {editing ? (
          <div className="grid gap-2 md:grid-cols-[1fr_2fr]">
            <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
            <Input
              value={description}
              maxLength={200}
              onChange={(e) => setDescription(e.target.value)}
              aria-label="Description"
            />
          </div>
        ) : (
          <>
            <p className="flex flex-wrap items-center gap-2 text-[14px] font-medium text-fg">
              {row.name}
              {!row.is_active && <Badge tone="neutral">Hidden</Badge>}
              {row.parent_id && <Badge tone="neutral">Subcategory</Badge>}
            </p>
            {row.description && <p className="text-[13px] text-muted">{row.description}</p>}
          </>
        )}
        <p className="text-[12.5px] text-subtle">
          {row.services} {row.services === 1 ? "service" : "services"} · {row.briefs}{" "}
          {row.briefs === 1 ? "brief" : "briefs"} · /{row.slug}
        </p>
        {error && <p className="text-[12.5px] text-critical">{error}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {editing ? (
          <>
            <Button size="sm" loading={pending} onClick={() => void save({ name, description })}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <span className="inline-flex items-center gap-2 text-[12.5px] text-muted">
              {row.is_active ? "Shown" : "Hidden"}
              <Switch
                checked={row.is_active}
                disabled={pending}
                onChange={(next: boolean) => void save({ is_active: next })}
                label={`Show ${row.name} in menus and filters`}
              />
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default function AdminCategoriesPage() {
  const list = useLoader(() => admin.categories(), []);
  return (
    <>
      <AdminHeading
        title="Categories"
        description="The categories sellers file services under and clients file briefs under. A hidden category stops appearing in menus and filters; what is already in it stays."
      />
      <AddCategory onAdded={() => void list.reload()} />
      <AdminList data={list.data} loading={list.loading} empty={{ title: "No categories yet" }}>
        {(row: AdminCategory) => <CategoryRow key={row.id} row={row} onChanged={() => void list.reload()} />}
      </AdminList>
    </>
  );
}

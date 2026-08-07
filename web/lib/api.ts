/**
 * API client.
 *
 * Tokens live in HttpOnly cookies, so there is nothing here that reads or
 * stores a credential — the browser attaches them and JavaScript cannot see
 * them. What this module does own is the two things that follow from that
 * choice: sending the CSRF token on every state-changing request, and
 * transparently refreshing an expired access token exactly once before giving
 * up.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  status: number;
  code: string;
  /** Per-field messages, when the server rejected a form. */
  fields: Record<string, string>;

  constructor(status: number, code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
  return match?.[2] ? decodeURIComponent(match[2]) : null;
}

/** Ask Django to set the CSRF cookie. Safe to call more than once. */
export async function primeCsrf(): Promise<void> {
  if (readCookie("csrftoken")) return;
  await fetch(`${API}/auth/csrf/`, { credentials: "include" }).catch(() => undefined);
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Turn a DRF error body into a message plus per-field errors. DRF returns
 * `{field: ["msg"]}` for serializer failures and `{detail, code}` for
 * everything else; the UI wants both shapes normalised.
 */
function parseError(status: number, body: unknown): ApiError {
  if (!body || typeof body !== "object") {
    return new ApiError(status, "error", "Something went wrong. Please try again.");
  }

  const data = body as Record<string, unknown>;
  const code = typeof data.code === "string" ? data.code : "error";

  const fields: Record<string, string> = {};
  for (const [key, value] of Object.entries(data)) {
    if (key === "detail" || key === "code") continue;
    const first = Array.isArray(value) ? value[0] : value;
    if (typeof first === "string") fields[key] = first;
  }

  const detail =
    typeof data.detail === "string"
      ? data.detail
      : (Object.values(fields)[0] ?? "Something went wrong. Please try again.");

  return new ApiError(status, code, detail, fields);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Set by the retry path so a refresh loop cannot recurse. */
  retrying?: boolean;
  signal?: AbortSignal;
}

/**
 * In-flight refresh, shared by every caller.
 *
 * Refresh tokens rotate, and presenting a rotated token is treated by the
 * server as theft — it revokes the whole family. So if two requests both hit a
 * 401 and both tried to refresh, the second would look exactly like an attack
 * and sign the user out. Concurrent callers must therefore await one refresh,
 * not race to start their own.
 */
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const csrf = readCookie("csrftoken");
      const response = await fetch(`${API}/auth/refresh/`, {
        method: "POST",
        credentials: "include",
        headers: csrf ? { "X-CSRFToken": csrf } : {},
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      // Cleared after the promise settles so the next 401 starts a fresh one.
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  const isFormData = options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) headers["Content-Type"] = "application/json";

  if (UNSAFE.has(method)) {
    await primeCsrf();
    const token = readCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }

  const response = await fetch(`${API}${path}`, {
    method,
    headers,
    credentials: "include",
    signal: options.signal,
    body: isFormData
      ? (options.body as FormData)
      : options.body !== undefined
        ? JSON.stringify(options.body)
        : undefined,
  });

  // An expired access token is the expected case, not an error: rotate once
  // and replay the original request.
  if (response.status === 401 && !options.retrying && path !== "/auth/refresh/") {
    if (await refreshSession()) return request<T>(path, { ...options, retrying: true });
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) throw parseError(response.status, payload);
  return payload as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/* -------------------------------------------------------------------------- */
/* Types — mirrors of the API serializers.                                    */
/* -------------------------------------------------------------------------- */

export type VerificationStatus = "unverified" | "pending" | "verified" | "rejected";

export interface University {
  id: number;
  name: string;
  short_code: string;
  city: string;
  brand_color: string;
}

export interface SellerProfile {
  overview: string;
  skills: string[];
  hourly_rate: string | null;
  availability: "available" | "limited" | "unavailable";
  hours_per_week: number | null;
  job_success_score: number | null;
  contracts_completed: number;
  on_time_delivery_rate: number | null;
  response_time_minutes: number | null;
  repeat_client_rate: number | null;
}

export interface BuyerProfile {
  company_name: string;
  industry: string;
  company_size: string;
  payment_verified: boolean;
  contracts_posted: number;
  hire_rate: number | null;
  average_rating_given: string | null;
}

export interface User {
  id: number;
  email: string;
  handle: string;
  full_name: string;
  display_name: string;
  avatar_url: string | null;
  headline: string;
  bio: string;
  country: string;
  city: string;
  timezone_name: string;
  languages: Array<{ code: string; proficiency: string }>;
  profile_visibility: "public" | "platform" | "private";
  email_verified: boolean;
  phone_number: string;
  phone_verified: boolean;
  identity_status: VerificationStatus;
  university: University | null;
  student_verification_status: VerificationStatus;
  is_verified_student: boolean;
  admin_role: string;
  profile_complete: boolean;
  can_transact: boolean;
  missing_requirements: Array<"email" | "phone" | "identity">;
  has_two_factor: boolean;
  profile_strength: number;
  seller_profile: SellerProfile | null;
  buyer_profile: BuyerProfile | null;
  created_at: string;
  /**
   * Seconds until this *device* may transact, 0 once it may. A property of the
   * browser rather than the account — the same user reads a different value
   * from a second machine — so it rides along with the account payload instead
   * of being cached anywhere longer-lived.
   */
  device_cooloff_seconds?: number;
}

export interface Session {
  id: number;
  family: string;
  device_label: string;
  ip_address: string | null;
  last_seen_at: string;
  created_at: string;
  is_current: boolean;
}

export interface Notification {
  id: number;
  category: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

export interface LoginResult {
  user?: User;
  /** The account has an authenticator enrolled; a TOTP or recovery code is due. */
  two_factor_required?: boolean;
  /**
   * No authenticator enrolled, and this device is unrecognised — a code has
   * been emailed. Mutually exclusive with `two_factor_required`: an enrolled
   * account is never admitted by an email code.
   */
  device_verification_required?: boolean;
  /** Masked hint at where the code went, e.g. `a•••d@example.com`. */
  sent_to?: string;
  challenge?: string;
}

export const auth = {
  me: () => api.get<User>("/auth/me/"),
  updateMe: (patch: Partial<User>) => api.patch<User>("/auth/me/", patch),
  signup: (body: { email: string; password: string; full_name?: string }) =>
    api.post<{ user: User }>("/auth/signup/", body),
  login: (body: { email: string; password: string }) =>
    api.post<LoginResult>("/auth/login/", body),
  loginTwoFactor: (body: { challenge: string; code: string }) =>
    api.post<{ user: User }>("/auth/login/2fa/", body),
  loginVerifyDevice: (body: { challenge: string; code: string }) =>
    api.post<{ user: User }>("/auth/login/device/", body),
  logout: () => api.post<{ detail: string }>("/auth/logout/"),

  requestEmailVerification: () => api.post<{ detail: string }>("/auth/email/verify/"),
  confirmEmail: (body: { email: string; token: string }) =>
    api.post<{ detail: string }>("/auth/email/confirm/", body),
  setPhone: (phone_number: string) => api.post<{ detail: string }>("/auth/phone/", { phone_number }),
  verifyPhone: (code: string) => api.post<User>("/auth/phone/verify/", { code }),

  requestPasswordReset: (email: string) =>
    api.post<{ detail: string }>("/auth/password/reset/", { email }),
  confirmPasswordReset: (body: { email: string; token: string; password: string }) =>
    api.post<{ detail: string }>("/auth/password/reset/confirm/", body),
  changePassword: (body: { current_password: string; new_password: string }) =>
    api.post<{ user: User }>("/auth/password/change/", body),

  sessions: () => api.get<Session[]>("/auth/sessions/"),
  revokeSession: (family: string) => api.delete<{ revoked: number }>(`/auth/sessions/${family}/`),
  revokeAllSessions: () => api.post<{ revoked: number }>("/auth/sessions/revoke-all/"),

  // `qr_svg` is an inline `data:image/svg+xml` URI rendered by the API, so the
  // TOTP secret never reaches a QR library on the client.
  twoFactorSetup: () =>
    api.post<{ qr_svg: string; secret: string; otpauth_url: string }>("/auth/2fa/setup/"),
  twoFactorConfirm: (code: string) =>
    api.post<{ recovery_codes: string[] }>("/auth/2fa/confirm/", { code }),
  twoFactorDisable: (body: { password?: string; code?: string }) =>
    api.post<{ detail: string }>("/auth/2fa/disable/", body),

  lookupUniversity: (email: string) =>
    api.get<{ matched: boolean; university?: University }>(
      `/auth/universities/lookup/?email=${encodeURIComponent(email)}`,
    ),
};

export const notifications = {
  list: (unreadOnly = false) =>
    api.get<Notification[] | { results: Notification[] }>(
      `/notifications/${unreadOnly ? "?unread=true" : ""}`,
    ),
  markRead: (ids?: number[]) => api.post<{ updated: number }>("/notifications/read/", { ids }),
};

/** Upload a file through the server-side validation pipeline. */
export async function uploadFile(path: string, file: File, extra: Record<string, string> = {}) {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(extra)) form.append(key, value);
  return request<unknown>(path, { method: "POST", body: form });
}

/* -------------------------------------------------------------------------- */
/* Marketplace — projects, proposals, contracts                               */
/* -------------------------------------------------------------------------- */

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string;
  description: string;
  children: Array<{ id: number; name: string; slug: string }>;
}

export interface Skill {
  id: number;
  name: string;
  slug: string;
}

export type ProjectType = "fixed" | "hourly";
export type ExperienceLevel = "entry" | "intermediate" | "expert";
export type ProjectStatus = "draft" | "open" | "paused" | "closed" | "awarded";

export interface ProjectSummary {
  id: number;
  title: string;
  description: string;
  project_type: ProjectType;
  budget_display: string;
  budget_min: string | null;
  budget_max: string | null;
  rate_min: string | null;
  rate_max: string | null;
  weekly_hours: number | null;
  size: "small" | "medium" | "large";
  experience_level: ExperienceLevel;
  expected_duration_days: number | null;
  category_name: string | null;
  skills: Skill[];
  proposal_count: number;
  status: ProjectStatus;
  client_name: string;
  client_country: string;
  verified_students_only: boolean;
  visibility: string;
  published_at: string | null;
  created_at: string;
}

export interface ScreeningQuestion {
  id: number;
  text: string;
  order: number;
  is_required: boolean;
}

export interface ProjectDetail extends Omit<ProjectSummary, "category_name" | "client_name"> {
  client: PublicProfile;
  category: Category | null;
  screening_questions: ScreeningQuestion[];
  listing: "public" | "invite_only";
  preferred_country: string;
  preferred_language: string;
  min_job_success_score: number | null;
  is_owner: boolean;
  can_propose: boolean;
  propose_blocked_reason: string;
  my_proposal_id: number | null;
}

export interface PublicProfile {
  handle: string;
  display_name: string;
  avatar_url: string | null;
  headline: string;
  bio: string;
  country: string;
  city: string;
  is_verified_student: boolean;
  university_name: string | null;
  seller_profile: SellerProfile | null;
  created_at: string;
}

export type ProposalStatus =
  | "submitted"
  | "shortlisted"
  | "declined"
  | "withdrawn"
  | "accepted";

export interface Proposal {
  id: number;
  project: number;
  project_title: string;
  project_type: ProjectType;
  freelancer: PublicProfile;
  cover_letter: string;
  bid_amount: string | null;
  hourly_rate: string | null;
  estimated_days: number | null;
  proposed_milestones: Array<{ title: string; amount: string; due_date?: string }>;
  status: ProposalStatus;
  is_boosted: boolean;
  is_editable: boolean;
  client_viewed_at: string | null;
  created_at: string;
  answers: Array<{ question: number; question_text: string; answer: string }>;
}

export type MilestoneStatus =
  | "pending"
  | "funded"
  | "in_progress"
  | "delivered"
  | "approved"
  | "released"
  | "cancelled";

export interface Milestone {
  id: number;
  order: number;
  title: string;
  description: string;
  amount: string;
  due_date: string | null;
  status: MilestoneStatus;
  is_funded: boolean;
  delivery_note: string;
  deliverable_urls: Array<{ name: string; url: string }>;
  funded_at: string | null;
  delivered_at: string | null;
  released_at: string | null;
}

export type ContractStatus =
  | "pending"
  | "active"
  | "paused"
  | "delivered"
  | "completed"
  | "cancelled"
  | "disputed";

export interface ContractSummary {
  id: number;
  title: string;
  contract_type: "fixed" | "milestone" | "hourly";
  status: ContractStatus;
  total_amount: string | null;
  hourly_rate: string | null;
  funded_amount: string;
  released_amount: string;
  client_name: string;
  freelancer_name: string;
  my_role: "client" | "freelancer";
  created_at: string;
  accepted_at: string | null;
  ended_at: string | null;
}

export interface ContractDetail extends ContractSummary {
  client: PublicProfile;
  freelancer: PublicProfile;
  milestones: Milestone[];
  logged_amount: string;
  terms: Record<string, unknown>;
  weekly_hour_limit: number | null;
  project: number | null;
  project_title: string | null;
  visibility: string;
  delivered_at: string | null;
  review_deadline: string | null;
  started_at: string | null;
  my_review_id: number | null;
  counterparty_review: Review | null;
}

export interface ContractEvent {
  id: number;
  kind: "message" | "status" | "funded" | "delivered" | "released" | "time" | "review";
  body: string;
  payload: Record<string, unknown>;
  actor_id: number | null;
  actor_name: string | null;
  attachment_urls: Array<{ name: string; url: string }>;
  created_at: string;
}

export interface TimeEntry {
  id: number;
  worked_on: string;
  minutes: number;
  hours: number;
  memo: string;
  source: "tracker" | "manual";
  activity_level: number | null;
  is_protected: boolean;
  is_disputed: boolean;
  dispute_note: string;
  created_at: string;
}

export interface Review {
  id: number;
  contract: number;
  role: "client" | "freelancer";
  overall: number;
  communication: number;
  quality: number | null;
  deadline: number | null;
  value: number | null;
  clarity: number | null;
  payment_promptness: number | null;
  comment: string;
  response: string;
  is_published: boolean;
  published_at: string | null;
  author_name: string;
  author_handle: string;
  created_at: string;
}

function toQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const marketplace = {
  categories: () => api.get<Category[]>("/categories/"),
  skills: (query = "") => api.get<Skill[]>(`/skills/${toQuery({ q: query })}`),

  projects: (filters: Record<string, string | number | boolean | undefined> = {}) =>
    api.get<Paginated<ProjectSummary>>(`/projects/${toQuery(filters)}`),
  project: (id: number | string) => api.get<ProjectDetail>(`/projects/${id}/`),
  createProject: (body: Record<string, unknown>) =>
    api.post<ProjectDetail>("/projects/", body),
  updateProject: (id: number, body: Record<string, unknown>) =>
    api.patch<ProjectDetail>(`/projects/${id}/`, body),
  publishProject: (id: number) => api.post<ProjectDetail>(`/projects/${id}/publish/`),
  closeProject: (id: number) => api.post<ProjectDetail>(`/projects/${id}/close/`),
  recommended: () => api.get<ProjectSummary[]>("/projects/recommended/"),

  projectProposals: (id: number | string) => api.get<Proposal[]>(`/projects/${id}/proposals/`),
  submitProposal: (id: number | string, body: Record<string, unknown>) =>
    api.post<Proposal>(`/projects/${id}/proposals/`, body),

  myProposals: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<Proposal>>(`/proposals/${toQuery(filters)}`),
  proposal: (id: number) => api.get<Proposal>(`/proposals/${id}/`),
  withdrawProposal: (id: number) => api.post<Proposal>(`/proposals/${id}/withdraw/`),
  shortlistProposal: (id: number) => api.post<Proposal>(`/proposals/${id}/shortlist/`),
  declineProposal: (id: number) => api.post<Proposal>(`/proposals/${id}/decline/`),
  quota: () =>
    api.get<{ limit: number; outstanding: number; remaining: number }>("/proposals/quota/"),
};

export const contracts = {
  list: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<ContractSummary>>(`/contracts/${toQuery(filters)}`),
  detail: (id: number | string) => api.get<ContractDetail>(`/contracts/${id}/`),
  award: (body: {
    proposal: number;
    milestones?: Array<{ title: string; amount: string; due_date?: string | null }>;
    weekly_hour_limit?: number;
  }) => api.post<ContractDetail>("/contracts/award/", body),
  accept: (id: number) => api.post<ContractDetail>(`/contracts/${id}/accept/`),
  cancel: (id: number) => api.post<ContractDetail>(`/contracts/${id}/cancel/`),

  fund: (id: number, milestoneId: number) =>
    api.post<ContractDetail>(`/contracts/${id}/milestones/${milestoneId}/fund/`),
  release: (id: number, milestoneId: number) =>
    api.post<ContractDetail>(`/contracts/${id}/milestones/${milestoneId}/release/`),
  deliver: (id: number, milestoneId: number, note: string, files: File[] = []) => {
    const form = new FormData();
    form.append("note", note);
    files.forEach((file) => form.append("files", file));
    return request<ContractDetail>(`/contracts/${id}/milestones/${milestoneId}/deliver/`, {
      method: "POST",
      body: form,
    });
  },

  events: (id: number | string) => api.get<ContractEvent[]>(`/contracts/${id}/events/`),
  postMessage: (id: number, body: string, files: File[] = []) => {
    const form = new FormData();
    form.append("body", body);
    files.forEach((file) => form.append("files", file));
    return request<ContractEvent>(`/contracts/${id}/events/`, { method: "POST", body: form });
  },

  time: (id: number | string) => api.get<TimeEntry[]>(`/contracts/${id}/time/`),
  logTime: (id: number, body: { worked_on: string; minutes: number; memo: string }) =>
    api.post<TimeEntry>(`/contracts/${id}/time/`, body),
  disputeTime: (id: number, entryId: number, note: string) =>
    api.post<TimeEntry>(`/contracts/${id}/time/${entryId}/dispute/`, { note }),

  reviews: (id: number | string) => api.get<Review[]>(`/contracts/${id}/review/`),
  submitReview: (id: number, body: Record<string, unknown>) =>
    api.post<Review & { published: boolean; detail: string }>(`/contracts/${id}/review/`, body),
};

/* -------------------------------------------------------------------------- */
/* Gigs — Track B                                                             */
/* -------------------------------------------------------------------------- */

export type GigStatus = "draft" | "active" | "paused" | "denied";
export type Tier = "basic" | "standard" | "premium";

export interface Package {
  id: number;
  tier: Tier;
  name: string;
  description: string;
  price: string;
  delivery_days: number;
  revisions: number;
  has_unlimited_revisions: boolean;
  features: string[];
  is_active: boolean;
}

export interface GigExtra {
  id: number;
  title: string;
  price: string;
  extra_days: number;
  is_active: boolean;
}

export interface RequirementField {
  key: string;
  label: string;
  required?: boolean;
  type?: string;
}

export interface GigSummary {
  id: number;
  title: string;
  slug: string;
  category_name: string | null;
  tags: string[];
  starting_price: string | null;
  rating_average: string | null;
  rating_count: number;
  orders_count: number;
  cover_url: string | null;
  seller_name: string;
  seller_handle: string;
  seller_avatar: string | null;
  seller_is_student: boolean;
  visibility: string;
  published_at: string | null;
}

export interface GigDetail {
  id: number;
  title: string;
  slug: string;
  description: string;
  faq: Array<{ question: string; answer: string }>;
  requirements: RequirementField[];
  tags: string[];
  category: Category | null;
  skills: Skill[];
  packages: Package[];
  extras: GigExtra[];
  gallery_urls: string[];
  status: GigStatus;
  starting_price: string | null;
  rating_average: string | null;
  rating_count: number;
  orders_count: number;
  seller: PublicProfile;
  visibility: string;
  published_at: string | null;
  created_at: string;
  is_owner: boolean;
  can_order: boolean;
  order_blocked_reason: string;
}

export type OrderStatus =
  | "pending_requirements"
  | "active"
  | "delivered"
  | "revision"
  | "completed"
  | "cancelled";

export interface GigOrder {
  id: number;
  gig: number;
  gig_title: string;
  gig_slug: string;
  package: number;
  package_snapshot: Record<string, unknown>;
  extras: GigExtra[];
  buyer: number;
  buyer_name: string;
  seller: number;
  seller_name: string;
  contract: number | null;
  price: string;
  delivery_days: number;
  revisions_allowed: number;
  revisions_used: number;
  revisions_left: number;
  requirements_answers: Record<string, string>;
  requirements_form: RequirementField[];
  status: OrderStatus;
  is_late: boolean;
  missing_requirements: string[];
  started_at: string | null;
  due_at: string | null;
  delivered_at: string | null;
  accept_by: string | null;
  completed_at: string | null;
  created_at: string;
  my_role: "buyer" | "seller";
}

export const gigs = {
  list: (filters: Record<string, string | number | boolean | undefined> = {}) =>
    api.get<Paginated<GigSummary>>(`/gigs/${toQuery(filters)}`),
  detail: (id: number | string) => api.get<GigDetail>(`/gigs/${id}/`),
  create: (body: Record<string, unknown>) => api.post<GigDetail>("/gigs/", body),
  update: (id: number, body: Record<string, unknown>) =>
    api.patch<GigDetail>(`/gigs/${id}/`, body),
  publish: (id: number) => api.post<GigDetail>(`/gigs/${id}/publish/`),
  pause: (id: number) => api.post<GigDetail>(`/gigs/${id}/pause/`),
  order: (id: number, body: { package: number; extras?: number[] }) =>
    api.post<GigOrder>(`/gigs/${id}/order/`, body),
  sellerDashboard: () =>
    api.get<{
      gigs: number;
      active_gigs: number;
      impressions: number;
      clicks: number;
      orders_in_flight: number;
      orders_completed: number;
    }>("/seller/dashboard/"),
};

export const orders = {
  list: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<GigOrder>>(`/orders/${toQuery(filters)}`),
  detail: (id: number | string) => api.get<GigOrder>(`/orders/${id}/`),
  submitRequirements: (id: number, answers: Record<string, string>) =>
    api.post<GigOrder>(`/orders/${id}/requirements/`, { answers }),
  deliver: (id: number, note: string, files: File[] = []) => {
    const form = new FormData();
    form.append("note", note);
    files.forEach((file) => form.append("files", file));
    return request<GigOrder>(`/orders/${id}/deliver/`, { method: "POST", body: form });
  },
  requestRevision: (id: number, note: string) =>
    api.post<GigOrder>(`/orders/${id}/request-revision/`, { note }),
  accept: (id: number) => api.post<GigOrder>(`/orders/${id}/accept/`),
  cancel: (id: number) => api.post<GigOrder>(`/orders/${id}/cancel/`),
};

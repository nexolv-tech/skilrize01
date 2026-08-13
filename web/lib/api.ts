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

/* -------------------------------------------------------------------------- */
/* Active surface                                                             */
/* -------------------------------------------------------------------------- */

export type SurfaceKind = "global" | "university";

const SURFACE_STORAGE_KEY = "skilrize.surface";

/**
 * Which marketplace the client is currently looking at.
 *
 * Held in a module-level variable so *every* request carries it without each
 * call site remembering — the whole failure mode this defends against is one
 * forgotten header on one endpoint, which would silently serve global results
 * inside the campus portal.
 *
 * It is a request, not an instruction. The server re-derives entitlement from
 * the session on every call and returns 403 rather than trusting this, so a
 * tampered value buys nothing.
 */
let activeSurface: SurfaceKind = "global";

export function getSurface(): SurfaceKind {
  return activeSurface;
}

export function setSurface(surface: SurfaceKind): void {
  activeSurface = surface;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SURFACE_STORAGE_KEY, surface);
  }
}

/** Restore the last surface on boot. Called once by the session provider. */
export function restoreSurface(): SurfaceKind {
  if (typeof window === "undefined") return "global";
  const stored = window.localStorage.getItem(SURFACE_STORAGE_KEY);
  activeSurface = stored === "university" ? "university" : "global";
  return activeSurface;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  const isFormData = options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) headers["Content-Type"] = "application/json";

  // Sent on every request, including reads. The server decides whether the
  // caller is entitled to the surface it names.
  if (activeSurface !== "global") headers["X-Skilrize-Surface"] = activeSurface;

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
  badges: ChallengeBadge[];
  created_at: string;
  /**
   * Seconds until this *device* may transact, 0 once it may. A property of the
   * browser rather than the account — the same user reads a different value
   * from a second machine — so it rides along with the account payload instead
   * of being cached anywhere longer-lived.
   */
  device_cooloff_seconds?: number;
  /** The surfaces this account may switch to, decided server-side. */
  surfaces?: Surface[];
}

export interface Surface {
  kind: SurfaceKind;
  label: string;
  university: University | null;
}

export type StudentApplicationStatus =
  | "email_pending"
  | "awaiting_id"
  | "under_review"
  | "approved"
  | "rejected";

export interface StudentApplication {
  id: number;
  university: University;
  university_email: string;
  email_verified_at: string | null;
  status: StudentApplicationStatus;
  rejection_reason: string;
  id_card_required: boolean;
  /** What the student does next. Decided server-side so the UI never re-derives it. */
  next_step: "confirm_email" | "upload_id_card" | "wait_for_review" | "done" | "start_again";
  created_at: string;
  reviewed_at: string | null;
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

  // Student portals
  studentApplication: () =>
    api.get<{ application: StudentApplication | null }>("/auth/student/"),
  startStudentVerification: (university_email: string) =>
    api.post<{ application: StudentApplication }>("/auth/student/email/", { university_email }),
  confirmStudentEmail: (code: string) =>
    api.post<{ application: StudentApplication }>("/auth/student/email/verify/", { code }),
  uploadStudentIdCard: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return api.post<{ application: StudentApplication }>("/auth/student/id-card/", body);
  },

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

export type TrialStatus = "proposed" | "accepted" | "declined" | "converted";

export interface Trial {
  id: number;
  brief: string;
  amount: string;
  duration_days: number;
  status: TrialStatus;
  contract_id: number | null;
  contract_status: ContractStatus | null;
  converted_contract_id: number | null;
  responded_at: string | null;
  created_at: string;
}

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
  trial: Trial | null;
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

  proposeTrial: (
    proposalId: number,
    body: { brief: string; amount: string; duration_days?: number },
  ) => api.post<Trial>(`/proposals/${proposalId}/trial/`, body),
  acceptTrial: (proposalId: number) => api.post<Trial>(`/proposals/${proposalId}/trial/accept/`),
  declineTrial: (proposalId: number) => api.post<Trial>(`/proposals/${proposalId}/trial/decline/`),
  convertTrial: (proposalId: number) =>
    api.post<ContractDetail>(`/proposals/${proposalId}/trial/convert/`),
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

/* -------------------------------------------------------------------------- */
/* Communities — the social layer                                             */
/* -------------------------------------------------------------------------- */

export type CommunityKind = "open" | "request" | "closed";
export type MemberRole = "member" | "moderator" | "owner";

export interface Author {
  id: number;
  handle: string;
  display_name: string;
  avatar_url: string | null;
}

export interface Community {
  id: number;
  name: string;
  slug: string;
  tagline: string;
  description: string;
  kind: CommunityKind;
  cover_url: string | null;
  created_by: Author;
  member_count: number;
  thread_count: number;
  is_archived: boolean;
  visibility: "global" | "university";
  /** Null when the viewer has not joined. */
  my_role: MemberRole | null;
  can_post: boolean;
  created_at: string;
}

export interface CommunityThread {
  id: number;
  community?: number;
  title: string;
  body?: string;
  author: Author;
  reply_count: number;
  is_pinned: boolean;
  is_locked: boolean;
  last_activity_at: string;
  created_at: string;
}

export interface ThreadReply {
  id: number;
  author: Author;
  parent: number | null;
  body: string;
  depth: number;
  is_deleted: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  author: Author;
  body: string;
  is_deleted: boolean;
  created_at: string;
}

export interface CommunityEvent {
  id: number;
  community: number;
  title: string;
  description: string;
  created_by: Author;
  starts_at: string;
  ends_at: string | null;
  location: string;
  online_url: string;
  capacity: number;
  going_count: number;
  is_full: boolean;
  is_cancelled: boolean;
  my_rsvp: "going" | "interested" | "declined" | null;
  created_at: string;
}

export interface CommunityResource {
  id: number;
  community: number;
  title: string;
  description: string;
  kind: "file" | "link";
  url: string;
  file_url: string | null;
  tags: string[];
  uploaded_by: Author;
  download_count: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  other: Author | null;
  last_message: DirectMessage | null;
  unread_count: number;
  last_message_at: string;
}

export interface DirectMessage {
  id: number;
  sender: Author;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface FeedEntry {
  id: number;
  actor: Author;
  verb: string;
  summary: string;
  url: string;
  community: number | null;
  created_at: string;
}

export interface ModerationReport {
  id: number;
  reporter: Author;
  community: number | null;
  kind: string;
  object_id: number;
  reason: string;
  status: "open" | "upheld" | "dismissed";
  resolution_note: string;
  created_at: string;
  resolved_at: string | null;
}

export const communities = {
  list: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<Community>>(`/communities/${toQuery(filters)}`),
  detail: (id: number | string) => api.get<Community>(`/communities/${id}/`),
  create: (body: Partial<Community>) => api.post<Community>("/communities/", body),
  join: (id: number) => api.post<Community>(`/communities/${id}/join/`),
  leave: (id: number) => api.delete<void>(`/communities/${id}/leave/`),
  members: (id: number) =>
    api.get<Array<{ id: number; user: Author; role: MemberRole; status: string }>>(
      `/communities/${id}/members/`,
    ),

  threads: (communityId: number) =>
    api.get<Paginated<CommunityThread>>(`/threads/${toQuery({ community: String(communityId) })}`),
  thread: (id: number | string) => api.get<CommunityThread>(`/threads/${id}/`),
  createThread: (community: number, title: string, body: string) =>
    api.post<CommunityThread>("/threads/", { community, title, body }),
  replies: (threadId: number | string) =>
    api.get<Paginated<ThreadReply>>(`/threads/${threadId}/replies/`),
  reply: (threadId: number | string, body: string, parent?: number | null) =>
    api.post<ThreadReply>(`/threads/${threadId}/replies/`, { body, parent: parent ?? null }),
  removeReply: (id: number) => api.delete<void>(`/replies/${id}/`),
  pinThread: (id: number) => api.post<CommunityThread>(`/threads/${id}/pin/`),
  lockThread: (id: number) => api.post<CommunityThread>(`/threads/${id}/lock/`),

  chat: (communityId: number, before?: number) =>
    api.get<ChatMessage[]>(
      `/communities/${communityId}/chat/${toQuery({ before: before ? String(before) : undefined })}`,
    ),
  sendChat: (communityId: number, body: string) =>
    api.post<ChatMessage>(`/communities/${communityId}/chat/`, { body }),

  events: (communityId?: number) =>
    api.get<Paginated<CommunityEvent>>(
      `/events/${toQuery({ community: communityId ? String(communityId) : undefined })}`,
    ),
  createEvent: (body: Partial<CommunityEvent> & { community: number }) =>
    api.post<CommunityEvent>("/events/", body),
  rsvp: (id: number, status: "going" | "interested" | "declined") =>
    api.post<CommunityEvent>(`/events/${id}/rsvp/`, { status }),
  cancelEvent: (id: number) => api.post<CommunityEvent>(`/events/${id}/cancel/`),

  resources: (communityId?: number) =>
    api.get<Paginated<CommunityResource>>(
      `/resources/${toQuery({ community: communityId ? String(communityId) : undefined })}`,
    ),
  shareResource: (community: number, fields: Record<string, string>, file?: File | null) => {
    const form = new FormData();
    form.append("community", String(community));
    Object.entries(fields).forEach(([key, value]) => form.append(key, value));
    if (file) form.append("file", file);
    return request<CommunityResource>("/resources/", { method: "POST", body: form });
  },

  feed: (verb?: string) => api.get<Paginated<FeedEntry>>(`/feed/${toQuery({ verb })}`),
  report: (body: { kind: string; object_id: number; community?: number; reason: string }) =>
    api.post<ModerationReport>("/reports/", body),
  moderationQueue: () => api.get<ModerationReport[]>("/moderation/queue/"),
  resolveReport: (id: number, upheld: boolean, note = "") =>
    api.post<ModerationReport>(`/moderation/reports/${id}/resolve/`, { upheld, note }),
};

export const messages = {
  conversations: () => api.get<Paginated<Conversation>>("/conversations/"),
  start: (handle: string) => api.post<Conversation>("/conversations/start/", { handle }),
  thread: (id: number | string) => api.get<Paginated<DirectMessage>>(`/conversations/${id}/messages/`),
  send: (id: number | string, body: string) =>
    api.post<DirectMessage>(`/conversations/${id}/messages/`, { body }),
};

/* -------------------------------------------------------------------------- */
/* Discovery — search, reputation, showcase, promotion                        */
/* -------------------------------------------------------------------------- */

export type SellerLevel = "new" | "level_one" | "level_two" | "top_rated";

export const SELLER_LEVEL_LABEL: Record<SellerLevel, string> = {
  new: "New seller",
  level_one: "Level 1",
  level_two: "Level 2",
  top_rated: "Top Rated",
};

export interface SellerBadge {
  handle: string;
  display_name: string;
  avatar_url: string | null;
  level: SellerLevel;
  job_success_score: number | null;
}

export interface FacetOption {
  value: string;
  label: string;
  count: number;
}

/** Every search response carries its own facet counts, so filters stay usable. */
export interface Faceted<T> extends Paginated<T> {
  facets: Record<string, FacetOption[]>;
  query: string;
}

export interface SearchGig {
  id: number;
  title: string;
  slug: string;
  seller: SellerBadge;
  category: string | null;
  rating_average: string | null;
  rating_count: number;
  starting_price: string | null;
  /** Disclosed in the payload, not just styled in the UI. */
  is_promoted: boolean;
  score?: number;
}

export interface SearchProject {
  id: number;
  title: string;
  description: string;
  category: string | null;
  project_type: string;
  experience_level: string;
  budget_display: string;
  proposal_count: number;
  published_at: string;
  score?: number;
}

export interface SellerReputation {
  handle: string;
  display_name: string;
  level: SellerLevel;
  job_success_score: number | null;
  contracts_completed: number;
  on_time_delivery_rate: number | null;
  repeat_client_rate: number | null;
  average_rating: string | null;
  review_count: number;
  updated_at: string | null;
}

export interface ShowcasePiece {
  id: number;
  contract: number;
  title: string;
  summary: string;
  seller: SellerBadge;
  cover_url: string | null;
  category_name: string | null;
  skills: string[];
  rating_at_publication: number | null;
  seller_approved: boolean;
  client_approved: boolean;
  awaiting: "seller" | "client" | null;
  published_at: string | null;
  created_at: string;
}

export interface Promotion {
  id: number;
  gig: number;
  gig_title: string;
  daily_budget: string;
  total_budget: string;
  spent: string;
  starts_at: string;
  ends_at: string | null;
  status: string;
  impressions: number;
  clicks: number;
  click_through_rate: number;
  is_live: boolean;
  created_at: string;
}

export const discovery = {
  searchGigs: (filters: Record<string, string | undefined> = {}) =>
    api.get<Faceted<SearchGig>>(`/search/gigs/${toQuery(filters)}`),
  searchProjects: (filters: Record<string, string | undefined> = {}) =>
    api.get<Faceted<SearchProject>>(`/search/projects/${toQuery(filters)}`),
  /** Fire-and-forget: a failed click count must never break navigation. */
  recordClick: (gigId: number) =>
    api.post<void>(`/gigs/${gigId}/click/`).catch(() => undefined),

  reputation: (handle: string) => api.get<SellerReputation>(`/sellers/${handle}/reputation/`),

  showcase: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<ShowcasePiece>>(`/showcase/${toQuery(filters)}`),
  showcaseConsent: (contractId: number) =>
    api.get<ShowcasePiece>(`/showcase/contracts/${contractId}/`),
  approveShowcase: (contractId: number, body: { approved: boolean; title?: string; summary?: string }) =>
    api.post<ShowcasePiece>(`/showcase/contracts/${contractId}/`, body),

  promotions: () => api.get<Promotion[]>("/promotions/"),
  promote: (body: { gig: number; daily_budget: string; total_budget: string; ends_at?: string }) =>
    api.post<Promotion>("/promotions/", body),
  pausePromotion: (id: number) => api.post<Promotion>(`/promotions/${id}/pause/`),
};

/* -------------------------------------------------------------------------- */
/* Professional layer — subscriptions, CRM, agencies, retainers               */
/* -------------------------------------------------------------------------- */

export type PlanTier = "free" | "pro" | "elite";
export type DealStage =
  | "lead"
  | "qualified"
  | "proposed"
  | "negotiating"
  | "won"
  | "lost";

/** -1 means no ceiling. Kept as a constant so no call site invents its own. */
export const UNLIMITED = -1;

export interface SubscriptionPlan {
  id: number;
  tier: PlanTier;
  name: string;
  tagline: string;
  monthly_price: string;
  yearly_price: string;
  is_paid: boolean;
  proposal_quota: number;
  team_seats: number;
  crm_contact_limit: number;
  search_boost: boolean;
  advanced_analytics: boolean;
  can_sell_retainers: boolean;
  can_create_agency: boolean;
  priority_support: boolean;
  features: string[];
}

export interface Entitlements {
  tier: PlanTier;
  plan_name: string;
  proposal_quota: number;
  team_seats: number;
  crm_contact_limit: number;
  search_boost: boolean;
  advanced_analytics: boolean;
  can_sell_retainers: boolean;
  can_create_agency: boolean;
  priority_support: boolean;
  renews_at: string | null;
}

export interface UserSubscription {
  id: number;
  plan: SubscriptionPlan;
  interval: "monthly" | "yearly";
  status: string;
  is_live: boolean;
  started_at: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
}

export interface CrmContact {
  id: number;
  name: string;
  email: string;
  phone: string;
  company: string;
  source: string;
  tags: string[];
  notes: string;
  linked_user: number | null;
  is_archived: boolean;
  last_interaction_at: string | null;
  open_deals: number;
  pipeline_value: string;
  created_at: string;
}

export interface CrmDeal {
  id: number;
  contact: number;
  contact_name: string;
  title: string;
  value: string;
  stage: DealStage;
  is_open: boolean;
  expected_close: string | null;
  contract: number | null;
  closed_at: string | null;
  lost_reason: string;
  created_at: string;
}

export interface CrmTask {
  id: number;
  contact: number | null;
  deal: number | null;
  title: string;
  due_at: string | null;
  completed_at: string | null;
  is_overdue: boolean;
  created_at: string;
}

export interface PipelineSummary {
  stages: Array<{ stage: DealStage; count: number; value: string }>;
  open_value: string;
  won_value: string;
  /** Null until something has actually been decided. */
  win_rate: number | null;
  contacts: number;
  overdue_tasks: number;
}

export interface AgencyTeam {
  id: number;
  name: string;
  slug: string;
  tagline: string;
  description: string;
  logo_url: string | null;
  owner: number;
  seats_used: number;
  my_role: "owner" | "admin" | "member" | null;
  /** Includes a pending invite, which `my_role` deliberately does not report. */
  my_status: "invited" | "active" | null;
  is_active: boolean;
  created_at: string;
}

export interface AgencyTeamMember {
  id: number;
  user: number;
  display_name: string;
  handle: string;
  avatar_url: string | null;
  role: "owner" | "admin" | "member";
  status: "invited" | "active" | "removed";
  revenue_share: number;
  joined_at: string | null;
}

export interface SharedWorkspace {
  id: number;
  agency: number | null;
  name: string;
  description: string;
  client_contact: number | null;
  members: Array<{ id: number; user: number; display_name: string; is_client: boolean }>;
  contract_count: number;
  is_archived: boolean;
  created_at: string;
}

export interface Retainer {
  id: number;
  seller: number;
  seller_name: string;
  seller_handle: string;
  title: string;
  description: string;
  monthly_price: string;
  deliverables: string[];
  max_subscribers: number;
  minimum_months: number;
  active_subscriber_count: number;
  is_full: boolean;
  is_active: boolean;
  visibility: "global" | "university";
  created_at: string;
}

export interface RetainerEngagement {
  id: number;
  plan: number;
  plan_title: string;
  seller_name: string;
  buyer_name: string;
  buyer_handle: string;
  monthly_price: string;
  status: string;
  started_at: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  months_billed: number;
  can_cancel_now: boolean;
}

export const professional = {
  plans: () => api.get<SubscriptionPlan[]>("/plans/"),
  subscription: () =>
    api.get<{ subscription: UserSubscription | null; entitlements: Entitlements }>(
      "/subscription/",
    ),
  subscribe: (tier: PlanTier, interval: "monthly" | "yearly" = "monthly") =>
    api.post<UserSubscription>("/subscription/subscribe/", { tier, interval }),
  cancelSubscription: () => api.post<UserSubscription>("/subscription/cancel/"),

  contacts: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<CrmContact>>(`/crm/contacts/${toQuery(filters)}`),
  createContact: (body: Partial<CrmContact>) => api.post<CrmContact>("/crm/contacts/", body),
  updateContact: (id: number, body: Partial<CrmContact>) =>
    api.patch<CrmContact>(`/crm/contacts/${id}/`, body),
  interactions: (contactId: number) =>
    api.get<Array<{ id: number; kind: string; body: string; author_name: string; occurred_at: string }>>(
      `/crm/contacts/${contactId}/interactions/`,
    ),
  logInteraction: (contactId: number, body: { kind: string; body: string }) =>
    api.post(`/crm/contacts/${contactId}/interactions/`, body),

  deals: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<CrmDeal>>(`/crm/deals/${toQuery(filters)}`),
  createDeal: (body: Partial<CrmDeal>) => api.post<CrmDeal>("/crm/deals/", body),
  moveDeal: (id: number, stage: DealStage, reason = "") =>
    api.post<CrmDeal>(`/crm/deals/${id}/stage/`, { stage, reason }),
  pipeline: () => api.get<PipelineSummary>("/crm/pipeline/"),

  tasks: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<CrmTask>>(`/crm/tasks/${toQuery(filters)}`),
  createTask: (body: Partial<CrmTask>) => api.post<CrmTask>("/crm/tasks/", body),
  toggleTask: (id: number) => api.post<CrmTask>(`/crm/tasks/${id}/complete/`),

  agencies: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<AgencyTeam>>(`/agencies/${toQuery(filters)}`),
  createAgency: (body: Partial<AgencyTeam>) => api.post<AgencyTeam>("/agencies/", body),
  agencyMembers: (id: number) => api.get<AgencyTeamMember[]>(`/agencies/${id}/members/`),
  inviteToAgency: (id: number, handle: string, role = "member") =>
    api.post<AgencyTeamMember>(`/agencies/${id}/members/`, { handle, role }),
  acceptAgency: (id: number) => api.post<AgencyTeamMember>(`/agencies/${id}/accept/`),
  /** Also how a member leaves, and how an invitee declines. */
  removeMember: (agencyId: number, memberId: number) =>
    api.post<void>(`/agencies/${agencyId}/members/${memberId}/remove/`),

  workspaces: () => api.get<Paginated<SharedWorkspace>>("/workspaces/"),
  createWorkspace: (body: Partial<SharedWorkspace>) =>
    api.post<SharedWorkspace>("/workspaces/", body),
  inviteToWorkspace: (id: number, handle: string, isClient = false) =>
    api.post<SharedWorkspace>(`/workspaces/${id}/invite/`, { handle, is_client: isClient }),

  retainers: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<Retainer>>(`/retainers/${toQuery(filters)}`),
  createRetainer: (body: Partial<Retainer>) => api.post<Retainer>("/retainers/", body),
  subscribeToRetainer: (id: number) =>
    api.post<RetainerEngagement>(`/retainers/${id}/subscribe/`),
  myRetainers: () =>
    api.get<{ selling: RetainerEngagement[]; buying: RetainerEngagement[] }>("/retainers/mine/"),
  cancelRetainer: (id: number) =>
    api.post<RetainerEngagement>(`/retainers/subscriptions/${id}/cancel/`),
};

/* -------------------------------------------------------------------------- */
/* Proof-of-work challenges (Phase 13)                                        */
/* -------------------------------------------------------------------------- */

export interface Challenge {
  id: number;
  slug: string;
  title: string;
  brief: string;
  skill: number | null;
  skill_name: string | null;
  reference_file_url: string | null;
  duration_hours: number;
  automated_weight: number;
  human_weight: number;
  status: "draft" | "published" | "completed" | "cancelled";
  opens_at: string;
  closes_at: string;
  participant_count: number;
  graded_count: number;
  is_open: boolean;
  /** The caller's own attempt, if any. */
  my_participation_id: number | null;
  created_at: string;
}

export type AutomatedGradingStatus = "pending" | "running" | "complete" | "failed" | "unavailable";

export interface ChallengeParticipation {
  id: number;
  challenge: number;
  challenge_title: string;
  challenge_slug: string;
  user: number;
  user_handle: string;
  user_display_name: string;
  started_at: string;
  deadline: string;
  status: "in_progress" | "submitted" | "graded" | "expired";
  is_overdue: boolean;
  submission_url: string;
  repo_url: string;
  notes: string;
  submitted_at: string | null;
  automated_status: AutomatedGradingStatus;
  automated_score: number | null;
  /** Raw Lighthouse category scores, e.g. { performance: 92, accessibility: 88, ... }. */
  automated_report: Record<string, number>;
  automated_graded_at: string | null;
  human_score: number | null;
  human_notes: string;
  reviewed_at: string | null;
  final_score: number | null;
}

export interface ChallengeBadge {
  id: number;
  challenge: number;
  challenge_title: string;
  challenge_slug: string;
  skill_name: string | null;
  final_score: number;
  /** 8 means "Top 8%" — smaller is better. */
  top_percent: number;
  label: string;
  awarded_at: string;
}

export const challenges = {
  list: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<Challenge>>(`/challenges/${toQuery(filters)}`),
  detail: (slug: string) => api.get<Challenge>(`/challenges/${slug}/`),
  join: (slug: string) => api.post<ChallengeParticipation>(`/challenges/${slug}/join/`),
  submit: (
    slug: string,
    body: { submission_url: string; repo_url?: string; notes?: string },
  ) => api.post<ChallengeParticipation>(`/challenges/${slug}/submit/`, body),
  mine: () => api.get<ChallengeParticipation[]>("/challenges/mine/"),
};

/* -------------------------------------------------------------------------- */
/* Admin console (Phase 9)                                                    */
/* -------------------------------------------------------------------------- */

export type AdminRole =
  | ""
  | "super_admin"
  | "finance_admin"
  | "moderator"
  | "support_agent"
  | "dispute_officer"
  | "verification_officer"
  | "university_moderator";

export interface AdminVerification {
  id: number;
  applicant_handle: string;
  applicant_name: string;
  applicant_email: string;
  university_name: string;
  university_email: string;
  email_verified_at: string | null;
  id_card_url: string | null;
  status: "email_pending" | "awaiting_id" | "under_review" | "approved" | "rejected";
  rejection_reason: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface AdminUserRow {
  id: number;
  handle: string;
  email: string;
  full_name: string;
  display_name: string;
  avatar_url: string | null;
  admin_role: AdminRole;
  is_active: boolean;
  is_staff: boolean;
  email_verified: boolean;
  phone_verified: boolean;
  identity_status: string;
  is_verified_student: boolean;
  university_name: string | null;
  created_at: string;
}

export interface AdminContractRow {
  id: number;
  title: string;
  contract_type: string;
  status: ContractStatus;
  total_amount: string | null;
  hourly_rate: string | null;
  funded_amount: string;
  released_amount: string;
  client_name: string;
  freelancer_name: string;
  created_at: string;
  delivered_at: string | null;
  review_deadline: string | null;
  ended_at: string | null;
}

export interface AdminContractDetail extends AdminContractRow {
  client: PublicProfile;
  freelancer: PublicProfile;
  milestones: Milestone[];
  project: number | null;
  project_title: string | null;
  visibility: string;
  started_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  created_at: string;
  actor_name: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  justification: string;
  ip_address: string | null;
  request_id: string;
}

export const admin = {
  verifications: (verificationStatus?: string) =>
    api.get<Paginated<AdminVerification>>(
      `/auth/admin/verifications/${toQuery({ status: verificationStatus })}`,
    ),
  approveVerification: (id: number) =>
    api.post<AdminVerification>(`/auth/admin/verifications/${id}/approve/`),
  rejectVerification: (id: number, reason: string) =>
    api.post<AdminVerification>(`/auth/admin/verifications/${id}/reject/`, { reason }),

  users: (q?: string) => api.get<Paginated<AdminUserRow>>(`/auth/admin/users/${toQuery({ q })}`),
  user: (id: number) => api.get<AdminUserRow>(`/auth/admin/users/${id}/`),
  suspendUser: (id: number, reason: string) =>
    api.post<AdminUserRow>(`/auth/admin/users/${id}/suspend/`, { reason }),
  reactivateUser: (id: number) => api.post<AdminUserRow>(`/auth/admin/users/${id}/reactivate/`),

  contracts: (status?: string) =>
    api.get<Paginated<AdminContractRow>>(`/admin/contracts/${toQuery({ status })}`),
  contract: (id: number) => api.get<AdminContractDetail>(`/admin/contracts/${id}/`),
  fundMilestone: (contractId: number, milestoneId: number, reason?: string) =>
    api.post<AdminContractDetail>(
      `/admin/contracts/${contractId}/milestones/${milestoneId}/fund/`,
      { reason },
    ),

  auditLog: (filters: Record<string, string | undefined> = {}) =>
    api.get<Paginated<AuditLogEntry>>(`/auth/admin/audit-log/${toQuery(filters)}`),
};

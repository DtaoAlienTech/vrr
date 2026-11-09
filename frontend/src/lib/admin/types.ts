// The shapes the admin screens read from the staff API (backend/app/schemas/*).
export type Role = "super_admin" | "editor";

export type AdminUser = {
  id: number;
  email: string;
  name: string;
  role: Role;
  totpEnabled: boolean;
  needsTotpSetup: boolean;
};

export type SessionInfo = { user: AdminUser; csrfToken: string };

export type MediaBrief = {
  id: number;
  kind: "image" | "pdf";
  url: string;
  thumbUrl: string;
  altText: string;
  width?: number | null;
  height?: number | null;
  originalFilename: string;
};

export type MediaItem = MediaBrief & {
  mime: string;
  sizeBytes: number;
  variants: { url: string; width: number }[];
  cropBottom: boolean;
  createdAt: string;
};

export type Usage = { entity: string; id: number; label: string };

export type Dashboard = {
  counts: Record<string, number>;
  recentEnquiries: { id: number; name: string; phone: string; course?: string; status: string; createdAt: string }[];
  recentChanges: { id: number; entity: string; entityId: number; action: string; label?: string; userName?: string; createdAt: string }[];
};

export type Enquiry = {
  id: number;
  name: string;
  phone: string;
  course?: string;
  message?: string;
  status: "new" | "contacted" | "closed";
  sourcePage?: string;
  createdAt: string;
  handledBy?: number;
  handledAt?: string;
};

export type ManagedUser = {
  id: number;
  email: string;
  name: string;
  role: Role;
  isActive: boolean;
  totpEnabled: boolean;
  lastLoginAt?: string;
  lockedUntil?: string;
};

export type AuditEntry = {
  id: number;
  userId?: number;
  action: string;
  entity?: string;
  entityId?: number;
  changes?: Record<string, unknown>;
  ip?: string;
  createdAt: string;
};

export type Revision = { id: number; entity: string; entityId: number; action: string; userId?: number; userName?: string; createdAt: string };
export type RedirectItem = { id: number; fromPath: string; toPath: string; statusCode: number; createdAt: string };

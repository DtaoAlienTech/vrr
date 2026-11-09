"use client";

import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import type { ApiProblem } from "@/lib/admin/problem";

export function Heading({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="ahead">
      <div>
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions && <div className="ahead-actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, children, actions, className }: { title?: string; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={cx("acard", className)}>
      {(title || actions) && (
        <div className="acard-head">
          {title && <h3>{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "ok" | "warn"; children: ReactNode }) {
  return (
    <div className={`anotice anotice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="aloading" role="status">
      <span className="aspin" aria-hidden="true" /> {label}
    </p>
  );
}

export function ErrorState({ problem, retry }: { problem: ApiProblem; retry?: () => void }) {
  return (
    <Notice kind="error">
      <b>{problem.message}</b>
      {retry && (
        <>
          {" "}
          <button type="button" className="alink" onClick={retry}>
            Try again
          </button>
        </>
      )}
    </Notice>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="aempty">{children}</p>;
}

const STATUS: Record<string, [string, string]> = {
  published: ["ok", "Published"],
  draft: ["dr", "Draft"],
  new: ["dr", "New"],
  contacted: ["ok", "Contacted"],
  closed: ["gr", "Closed"],
  hidden: ["gr", "Hidden"],
  active: ["ok", "Active"],
  off: ["gr", "Switched off"],
};

export function StatusPill({ status, label }: { status: string; label?: string }) {
  const [kind, text] = STATUS[status] ?? ["gr", status];
  return <span className={`st ${kind}`}>{label ?? text}</span>;
}

export function Switch({ checked, onChange, label, disabled, id }: { checked: boolean; onChange: (checked: boolean) => void; label: ReactNode; disabled?: boolean; id?: string }) {
  return (
    <label className={cx("switch", disabled && "off")} htmlFor={id}>
      <span>{label}</span>
      <input id={id} type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <i aria-hidden="true" />
    </label>
  );
}

export function Field({
  label,
  htmlFor,
  required,
  help,
  error,
  count,
  children,
}: {
  label?: ReactNode;
  htmlFor?: string;
  required?: boolean;
  help?: ReactNode;
  error?: string;
  count?: { length: number; max: number };
  children: ReactNode;
}) {
  return (
    <div className={cx("afield", error && "has-error")}>
      {label && (
        <label htmlFor={htmlFor}>
          {label}
          {required && (
            <span className="req" aria-hidden="true">
              {" "}
              *
            </span>
          )}
        </label>
      )}
      {children}
      {error ? (
        <p className="ferr" role="alert">
          {error}
        </p>
      ) : (
        help && <p className="fhelp">{help}</p>
      )}
      {count && count.max <= 1000 && (
        <p className={cx("fcount", count.length > count.max && "over")}>
          {count.length} / {count.max}
        </p>
      )}
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  busy,
  small = true,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "accent"; busy?: boolean; small?: boolean }) {
  return (
    <button {...props} type={props.type ?? "button"} disabled={props.disabled || busy} className={cx("btn", `btn-${variant}`, small && "btn-sm", props.className)}>
      {busy && <span className="aspin aspin-sm" aria-hidden="true" />}
      {children}
    </button>
  );
}

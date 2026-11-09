"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import type { Role } from "@/lib/admin/types";
import { useSession, useUser } from "./session";

type NavItem = { href: string; label: string; exact?: boolean; role?: Role };

const NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", exact: true },
  { href: "/admin/news", label: "News & notices" },
  { href: "/admin/activities", label: "Activities" },
  { href: "/admin/gallery", label: "Gallery" },
  { href: "/admin/courses", label: "Courses" },
  { href: "/admin/departments", label: "Departments" },
  { href: "/admin/faculty", label: "Faculty" },
  { href: "/admin/pages", label: "Page content" },
  { href: "/admin/media", label: "Photos & files" },
  { href: "/admin/enquiries", label: "Enquiries" },
  { href: "/admin/history", label: "History & redirects" },
  { href: "/admin/settings", label: "Site settings", role: "super_admin" },
  { href: "/admin/users", label: "Users", role: "super_admin" },
  { href: "/admin/activity-log", label: "Activity log", role: "super_admin" },
  { href: "/admin/account", label: "My account" },
];

export function Shell({ children }: { children: ReactNode }) {
  const user = useUser();
  const { signOut } = useSession();
  const pathname = usePathname();
  const [signingOut, setSigningOut] = useState(false);
  const items = NAV.filter((item) => !item.role || item.role === user.role);
  const locked = user.needsTotpSetup;

  return (
    <>
      <a className="skip-link" href="#admin-main">
        Skip to content
      </a>
      <header className="adm-top">
        <Link className="brand" href="/admin">
          <img className="logo" src="/logo/vrr-mark.svg" width={44} height={51} alt="" />
          <span>
            <b>VRR Admin</b>
          </span>
        </Link>
        <span className="who">
          <a href="/" target="_blank" rel="noopener" className="viewsite">
            View website
          </a>
          <span className="whoname">
            {user.name} · {user.role === "super_admin" ? "Super admin" : "Editor"}
          </span>
          <button
            type="button"
            className="alink alink-light"
            disabled={signingOut}
            onClick={async () => {
              setSigningOut(true);
              await signOut();
            }}
          >
            Sign out
          </button>
        </span>
      </header>
      <div className="adm-body">
        <nav className="adm-side" aria-label="Admin">
          {locked && <p className="adm-lock-note">Locked until you set up two-factor login.</p>}
          {items.map((item) => {
            const active = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
            // Until two-factor login is on, a super admin can only reach "My account": show the other
            // entries as locked instead of letting a click silently bounce back.
            if (locked && item.href !== "/admin/account") {
              return (
                <span key={item.href} className="locked" aria-disabled="true" title="Set up two-factor login first">
                  {item.label}
                </span>
              );
            }
            return (
              <Link key={item.href} href={item.href} className={cx(active && "on")} aria-current={active ? "page" : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <main id="admin-main" className="adm-main">
          {children}
        </main>
      </div>
    </>
  );
}

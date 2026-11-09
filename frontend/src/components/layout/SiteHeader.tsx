import Link from "next/link";
import { Suspense } from "react";
import { LinkButton } from "@/components/ui/LinkButton";
import { Media } from "@/components/ui/Media";
import type { SiteSettings } from "@/lib/content/types";
import { ActiveNavLinks } from "./ActiveNavLinks";
import { MobileNavButton, MobileNavPanel, MobileNavProvider } from "./MobileNav";
import { NavLinks } from "./NavLinks";

const ENQUIRE = "/admissions#enquire";

export function SiteHeader({ settings }: { settings: SiteSettings }) {
  const { menu } = settings;
  // Until the browser URL is known, render the same links without the "current page" mark.
  const plainLinks = <NavLinks items={menu} />;
  return (
    <MobileNavProvider>
      <div className="util">
        <div className="wrap">
          <span>{settings.topBar}</span>
          <span>{settings.contact.address}</span>
        </div>
      </div>
      <header className="hdr">
        <div className="wrap">
          <Link className="brand" href="/">
            <Media className="logo" media={settings.logo} alt="" priority />
            <span>
              <b>{settings.name}</b>
              <small>{settings.tagline}</small>
            </span>
          </Link>
          <nav className="nav" aria-label="Main">
            <Suspense fallback={plainLinks}>
              <ActiveNavLinks items={menu} />
            </Suspense>
          </nav>
          <LinkButton href={ENQUIRE} size="sm" className="hcta">
            Enquire now
          </LinkButton>
          <MobileNavButton />
        </div>
        <MobileNavPanel>
          <Suspense fallback={plainLinks}>
            <ActiveNavLinks items={menu} />
          </Suspense>
          <LinkButton href={ENQUIRE}>Enquire now</LinkButton>
        </MobileNavPanel>
      </header>
    </MobileNavProvider>
  );
}

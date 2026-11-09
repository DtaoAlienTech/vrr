import { ActionBar } from "@/components/layout/ActionBar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { getSiteSettings } from "@/lib/content/api";

/** Frame shared by every public page. Header, footer and action bar all come from the settings. */
export default async function PublicLayout({ children }: LayoutProps<"/">) {
  const settings = await getSiteSettings();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader settings={settings} />
      <main id="main">{children}</main>
      <SiteFooter settings={settings} />
      <ActionBar contact={settings.contact} />
    </>
  );
}

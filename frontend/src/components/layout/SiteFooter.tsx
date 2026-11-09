import { Media } from "@/components/ui/Media";
import { SmartLink } from "@/components/ui/SmartLink";
import type { LinkItem, SiteSettings } from "@/lib/content/types";

function LinkList({ title, items }: { title: string; items: LinkItem[] }) {
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item.href}>
            <SmartLink href={item.href}>{item.label}</SmartLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SiteFooter({ settings }: { settings: SiteSettings }) {
  const { contact } = settings;
  return (
    <footer className="ftr">
      <div className="wrap">
        <div className="cols">
          <div>
            <Media className="logo" media={settings.logo} alt="" />
            <b className="ftr-name">{settings.name}</b>
            <p>
              {contact.address}.
              <br />
              {settings.affiliationText}
            </p>
          </div>
          <LinkList title="Explore" items={settings.menu} />
          <LinkList title="Courses" items={settings.footerCourses} />
          <div>
            <h4>Contact</h4>
            <p>
              {contact.address}
              {contact.phone && (
                <>
                  <br />
                  Phone: <SmartLink href={`tel:${contact.phone}`}>{contact.phone}</SmartLink>
                </>
              )}
              {contact.email && (
                <>
                  <br />
                  Email: <SmartLink href={`mailto:${contact.email}`}>{contact.email}</SmartLink>
                </>
              )}
              {contact.hours && (
                <>
                  <br />
                  {contact.hours}
                </>
              )}
            </p>
          </div>
        </div>
        <div className="legal">
          <span>{settings.copyright}</span>
        </div>
      </div>
    </footer>
  );
}

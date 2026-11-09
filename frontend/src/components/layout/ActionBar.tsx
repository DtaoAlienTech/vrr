import { Icon } from "@/components/ui/Icon";
import { SmartLink } from "@/components/ui/SmartLink";
import type { SiteSettings } from "@/lib/content/types";

/** Phone-only bar: Call, WhatsApp, Enquire. Buttons appear only when the number is set in settings. */
export function ActionBar({ contact }: { contact: SiteSettings["contact"] }) {
  const whatsapp = contact.whatsapp.replace(/\D/g, "");
  return (
    <nav className="mbar" aria-label="Quick actions">
      {contact.phone && (
        <SmartLink href={`tel:${contact.phone}`}>
          <Icon name="phone" />
          Call
        </SmartLink>
      )}
      {whatsapp && (
        <SmartLink href={`https://wa.me/${whatsapp}`}>
          <Icon name="chat" />
          WhatsApp
        </SmartLink>
      )}
      <SmartLink href="/admissions#enquire">
        <Icon name="mail" />
        Enquire
      </SmartLink>
    </nav>
  );
}

import { Fragment, type ReactNode } from "react";
import { DocList } from "@/components/ui/DocList";
import { JsonLd } from "@/components/ui/JsonLd";
import { KeyValueTable } from "@/components/ui/KeyValueTable";
import { LinkButton } from "@/components/ui/LinkButton";
import { Media } from "@/components/ui/Media";
import { RichText } from "@/components/ui/RichText";
import { SmartLink } from "@/components/ui/SmartLink";
import { getCourses, getSiteSettings } from "@/lib/content/api";
import type {
  ContactInfoData,
  DocListData,
  EmbeddedSection,
  EnquiryFormData,
  FaqData,
  ImageData,
  KeyValueData,
  MapData,
  PanelData,
  RichTextData,
  TimelineData,
} from "@/lib/content/types";
import { CollectionListBlock } from "./CollectionListBlock";
import { EnquiryForm } from "./EnquiryForm";

// Small blocks that live inside the two-column layout (main or aside column).

function RichTextEmbedded({ data }: { data: RichTextData }) {
  return (
    <div>
      {data.heading && <h3>{data.heading}</h3>}
      <RichText doc={data.body} />
    </div>
  );
}

function Timeline({ data }: { data: TimelineData }) {
  return (
    <ul className="tl">
      {data.items.map((item) => (
        <li key={item.label}>
          <b>{item.label}</b>
          {item.text}
        </li>
      ))}
    </ul>
  );
}

function KeyValue({ data }: { data: KeyValueData }) {
  return <KeyValueTable rows={data.rows} />;
}

function Faq({ data }: { data: FaqData }) {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: data.items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
  return (
    <div>
      <JsonLd data={structuredData} />
      {data.items.map((item) => (
        <details key={item.question} className="faq">
          <summary>{item.question}</summary>
          <p>{item.answer}</p>
        </details>
      ))}
    </div>
  );
}

function Panel({ data }: { data: PanelData }) {
  return (
    <div className="sidebox static">
      {data.title && <h3>{data.title}</h3>}
      {data.items?.map((item) => (
        <Fragment key={item.heading}>
          <h3>{item.heading}</h3>
          <p>{item.text}</p>
        </Fragment>
      ))}
      {data.list && (
        <ul className="ticks">
          {data.list.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ImageEmbedded({ data }: { data: ImageData }) {
  return (
    <div className="photo real">
      <Media media={data.media} sizes="(min-width: 900px) 33vw, 100vw" />
    </div>
  );
}

async function EnquiryFormEmbedded({ data }: { data: EnquiryFormData }) {
  const courses = await getCourses();
  return (
    <div className="formbox" id="enquire">
      <h3>{data.title}</h3>
      <EnquiryForm courses={courses.map((course) => course.name)} />
    </div>
  );
}

/** Address, phone, email and hours from the site settings. Empty details are not shown. */
async function ContactInfo({ data }: { data: ContactInfoData }) {
  const { contact } = await getSiteSettings();
  const rows: { label: string; content: ReactNode }[] = [
    { label: "Address", content: contact.address },
    ...(contact.phone
      ? [{ label: "Phone", content: <SmartLink href={`tel:${contact.phone}`}>{contact.phone}</SmartLink> }]
      : []),
    ...(contact.email
      ? [{ label: "Email", content: <SmartLink href={`mailto:${contact.email}`}>{contact.email}</SmartLink> }]
      : []),
    ...(contact.hours ? [{ label: "Office hours", content: contact.hours }] : []),
  ];
  return (
    <div>
      {data.heading && <h3>{data.heading}</h3>}
      <div className="info">
        {rows.map((row) => (
          <div key={row.label}>
            <b>{row.label}</b>
            {row.content}
          </div>
        ))}
      </div>
    </div>
  );
}

// Only Google Maps embed addresses are allowed in the iframe.
const GOOGLE_EMBED = /^https:\/\/www\.google\.com\/maps\/embed\?/;

/** An embedded map, or an "Open in Google Maps" button, or nothing if no map is set. */
async function MapEmbedded({ data }: { data: MapData }) {
  const { contact } = await getSiteSettings();
  if (GOOGLE_EMBED.test(contact.mapEmbedUrl)) {
    return (
      <div className="map-embed">
        <iframe
          src={contact.mapEmbedUrl}
          title={data.title ?? "Map"}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          allowFullScreen
        />
      </div>
    );
  }
  if (contact.mapLink) {
    return (
      <LinkButton href={contact.mapLink} variant="ghost">
        Open in Google Maps
      </LinkButton>
    );
  }
  return null;
}

function DocListEmbedded({ data }: { data: DocListData }) {
  return (
    <div>
      {data.heading && <h3>{data.heading}</h3>}
      <DocList docs={data.docs} />
    </div>
  );
}

/** Maps an embedded section's `type` to its component. TypeScript fails the build if one is missing. */
export function renderEmbedded(section: EmbeddedSection): ReactNode {
  switch (section.type) {
    case "rich_text":
      return <RichTextEmbedded data={section.data} />;
    case "timeline":
      return <Timeline data={section.data} />;
    case "key_value":
      return <KeyValue data={section.data} />;
    case "faq":
      return <Faq data={section.data} />;
    case "panel":
      return <Panel data={section.data} />;
    case "image":
      return <ImageEmbedded data={section.data} />;
    case "enquiry_form":
      return <EnquiryFormEmbedded data={section.data} />;
    case "contact_info":
      return <ContactInfo data={section.data} />;
    case "map":
      return <MapEmbedded data={section.data} />;
    case "doc_list":
      return <DocListEmbedded data={section.data} />;
    case "collection_list":
      return <CollectionListBlock data={section.data} embedded />;
    default: {
      const unhandled: never = section;
      throw new Error(`Unknown embedded section: ${JSON.stringify(unhandled)}`);
    }
  }
}

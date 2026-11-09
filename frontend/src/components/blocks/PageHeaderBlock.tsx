import { Fragment } from "react";
import { JsonLd } from "@/components/ui/JsonLd";
import { SmartLink } from "@/components/ui/SmartLink";
import type { LinkItem, PageHeaderData } from "@/lib/content/types";
import { absoluteUrl } from "@/lib/env";

/** The page title (the page's only <h1>), breadcrumbs, and the matching structured data. */
export function PageHeaderBlock({ data }: { data: PageHeaderData }) {
  const trail: LinkItem[] = [{ label: "Home", href: "/" }, ...(data.crumbs ?? [])];
  const breadcrumbs = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      ...trail.map((crumb, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: crumb.label,
        item: absoluteUrl(crumb.href),
      })),
      { "@type": "ListItem", position: trail.length + 1, name: data.title },
    ],
  };
  return (
    <section className="phero">
      <JsonLd data={breadcrumbs} />
      <div className="wrap">
        <nav className="crumbs" aria-label="Breadcrumb">
          {trail.map((crumb) => (
            <Fragment key={crumb.href}>
              <SmartLink href={crumb.href}>{crumb.label}</SmartLink>
              {" / "}
            </Fragment>
          ))}
          <span aria-current="page">{data.title}</span>
        </nav>
        <h1>{data.title}</h1>
        {data.subtitle && <p>{data.subtitle}</p>}
      </div>
    </section>
  );
}

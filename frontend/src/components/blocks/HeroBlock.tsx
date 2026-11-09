import { LinkButton } from "@/components/ui/LinkButton";
import { Media } from "@/components/ui/Media";
import type { HeroData } from "@/lib/content/types";

/** Home hero. Renders the page's only <h1>. */
export function HeroBlock({ data }: { data: HeroData }) {
  return (
    <section className="hero">
      <div className="wrap">
        <div>
          {data.label && <div className="eyebrow">{data.label}</div>}
          <h1>
            {data.headline} {data.highlight && <em>{data.highlight}</em>}
          </h1>
          <p className="lead">{data.text}</p>
          <div className="cta">
            <LinkButton href={data.primaryCta.href}>{data.primaryCta.label}</LinkButton>
            {data.secondaryCta && (
              <LinkButton href={data.secondaryCta.href} variant="ghost">
                {data.secondaryCta.label}
              </LinkButton>
            )}
          </div>
        </div>
        <div className="photo real">
          <Media media={data.image} priority sizes="(min-width: 900px) 40vw, 100vw" />
        </div>
      </div>
    </section>
  );
}

import { Icon } from "@/components/ui/Icon";
import { LinkButton } from "@/components/ui/LinkButton";
import { Media } from "@/components/ui/Media";
import { SmartLink } from "@/components/ui/SmartLink";
import type { HeroData } from "@/lib/content/types";

/**
 * Home hero: the college photo fills the first screen, the text sits on top of it.
 * The photo is a real <img> (not a CSS background) so it loads first and keeps its alt text.
 * The "Scroll down" cue tells visitors there is more below and jumps to the next section.
 * Renders the page's only <h1>.
 */
export function HeroBlock({ data }: { data: HeroData }) {
  return (
    <>
      <section className="hero hero-cover">
        <Media className="hero-bg" media={data.image} priority sizes="100vw" />
        <div className="hero-shade" aria-hidden="true" />
        <div className="wrap hero-inner">
          <div className="hero-copy">
            {data.label && <div className="eyebrow">{data.label}</div>}
            <h1>
              {data.headline} {data.highlight && <em>{data.highlight}</em>}
            </h1>
            <p className="lead">{data.text}</p>
            <div className="cta">
              <LinkButton href={data.primaryCta.href} variant="accent">
                {data.primaryCta.label}
              </LinkButton>
              {data.secondaryCta && (
                <LinkButton href={data.secondaryCta.href} variant="ghost">
                  {data.secondaryCta.label}
                </LinkButton>
              )}
            </div>
          </div>
        </div>
        <SmartLink className="scroll-cue" href="#after-hero" aria-label="Scroll down to see more">
          <span>Scroll down</span>
          <Icon name="chevron" />
        </SmartLink>
      </section>
      <span id="after-hero" className="anchor" />
    </>
  );
}

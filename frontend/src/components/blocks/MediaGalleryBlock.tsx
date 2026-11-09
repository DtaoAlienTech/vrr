import { LinkButton } from "@/components/ui/LinkButton";
import { Media } from "@/components/ui/Media";
import { Section, SectionHead } from "@/components/ui/Section";
import type { MediaGalleryData } from "@/lib/content/types";
import { cx } from "@/lib/cx";

/** Photo mosaic. The first photo is shown large. */
export function MediaGalleryBlock({ data }: { data: MediaGalleryData }) {
  return (
    <Section>
      <SectionHead title={data.heading} intro={data.intro} />
      <div className="mosaic">
        {data.items.map((item, index) => (
          <div key={item.media.url} className={cx("ph", "img", index === 0 && "big")}>
            <Media media={item.media} sizes={index === 0 ? "(min-width: 820px) 50vw, 100vw" : "(min-width: 820px) 25vw, 50vw"} />
            <span>{item.caption}</span>
          </div>
        ))}
      </div>
      {data.cta && (
        <p className="mt-20">
          <LinkButton href={data.cta.href} variant="ghost">
            {data.cta.label}
          </LinkButton>
        </p>
      )}
    </Section>
  );
}

import type { MediaRef } from "@/lib/content/types";
import { cx } from "@/lib/cx";

type Props = {
  media: MediaRef;
  /** `sizes` attribute, used together with the resized variants made at upload. */
  sizes?: string;
  /** Hero images only: load first and with high priority. */
  priority?: boolean;
  className?: string;
  /** Pass "" for purely decorative images. */
  alt?: string;
};

/**
 * The one image component. Photos are resized at upload (see plan section 10), so a plain <img>
 * with srcset is used instead of runtime optimisation. Width and height prevent layout shift.
 */
export function Media({ media, sizes, priority = false, className, alt }: Props) {
  const srcSet = media.variants?.length
    ? media.variants.map((v) => `${v.url} ${v.width}w`).join(", ")
    : undefined;
  return (
    <img
      className={cx(className, media.cropBottom && "wm") || undefined}
      src={media.url}
      srcSet={srcSet}
      sizes={srcSet ? sizes : undefined}
      width={media.width}
      height={media.height}
      alt={alt ?? media.alt}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
    />
  );
}

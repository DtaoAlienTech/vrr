/** Shown at the top of a draft preview, so nobody mistakes it for the live website. */
export function PreviewBanner({ what }: { what: string }) {
  return (
    <div className="preview-bar" role="status">
      <strong>Draft preview</strong>
      <span>
        This is how the {what} looks when it is published. Only people with this link can see it, and
        the link stops working after 30 minutes.
      </span>
    </div>
  );
}

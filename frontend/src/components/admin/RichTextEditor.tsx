"use client";

import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useState } from "react";
import { isSafeHref, LINK_HELP } from "@/lib/admin/links";
import { EMPTY_DOC, sanitizeDoc, type RichDoc } from "@/lib/admin/rich-text";
import { cx } from "@/lib/cx";
import { Modal } from "./Modal";
import { Button, Field } from "./ui";

const INACTIVE = { bold: false, italic: false, underline: false, h2: false, h3: false, bullet: false, ordered: false, quote: false, link: false, canUndo: false, canRedo: false };

type Props = { value: RichDoc | undefined; onChange: (doc: RichDoc) => void; label: string; id: string; invalid?: boolean };

// Only the formatting the server accepts and the website draws: no code, no strike-through, no
// rules. Headings are h2 and h3 (the page title is the only h1).
const EXTENSIONS = [
  StarterKit.configure({
    heading: { levels: [2, 3] },
    codeBlock: false,
    code: false,
    strike: false,
    horizontalRule: false,
    trailingNode: false,
    link: { openOnClick: false, autolink: false, linkOnPaste: true },
  }),
];

function ToolButton({ label, active, disabled, onClick, children }: { label: string; active?: boolean; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={cx("tbtn", active && "on")} aria-label={label} title={label} aria-pressed={active} disabled={disabled} onClick={onClick} onMouseDown={(event) => event.preventDefault()}>
      {children}
    </button>
  );
}

export function RichTextEditor({ value, onChange, label, id, invalid }: Props) {
  const [linkOpen, setLinkOpen] = useState(false);
  const [href, setHref] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);

  const editor = useEditor({
    extensions: EXTENSIONS,
    content: sanitizeDoc(value ?? EMPTY_DOC),
    immediatelyRender: false,
    onUpdate: ({ editor: current }) => onChange(sanitizeDoc(current.getJSON())),
    editorProps: { attributes: { id, role: "textbox", "aria-multiline": "true", "aria-label": label, class: "rte-content" } },
  });

  // If the value is replaced from outside (a restored version), show it in the editor.
  useEffect(() => {
    if (!editor) return;
    const incoming = sanitizeDoc(value ?? EMPTY_DOC);
    if (JSON.stringify(sanitizeDoc(editor.getJSON())) !== JSON.stringify(incoming)) {
      editor.commands.setContent(incoming, { emitUpdate: false });
    }
  }, [editor, value]);

  const reported = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      e
        ? {
            bold: e.isActive("bold"),
            italic: e.isActive("italic"),
            underline: e.isActive("underline"),
            h2: e.isActive("heading", { level: 2 }),
            h3: e.isActive("heading", { level: 3 }),
            bullet: e.isActive("bulletList"),
            ordered: e.isActive("orderedList"),
            quote: e.isActive("blockquote"),
            link: e.isActive("link"),
            canUndo: e.can().undo(),
            canRedo: e.can().redo(),
          }
        : null,
  });

  // The editor reports its state only once it is mounted, so it is mounted straight away and the
  // toolbar shows "nothing active" until then.
  if (!editor) return <div className="rte rte-loading">Loading the editor…</div>;
  const chain = () => editor.chain().focus();
  const state = reported ?? INACTIVE;

  function openLink() {
    setHref((editor?.getAttributes("link").href as string | undefined) ?? "");
    setLinkError(null);
    setLinkOpen(true);
  }

  function applyLink() {
    const value = href.trim();
    if (!value) {
      editor?.chain().focus().extendMarkRange("link").unsetLink().run();
    } else if (!isSafeHref(value)) {
      setLinkError(LINK_HELP);
      return;
    } else {
      editor?.chain().focus().extendMarkRange("link").setLink({ href: value }).run();
    }
    setLinkOpen(false);
  }

  return (
    <div className={cx("rte", invalid && "rte-invalid")}>
      <div className="toolbar" role="toolbar" aria-label="Formatting">
        <ToolButton label="Bold" active={state.bold} onClick={() => chain().toggleBold().run()}>
          <b>B</b>
        </ToolButton>
        <ToolButton label="Italic" active={state.italic} onClick={() => chain().toggleItalic().run()}>
          <i>I</i>
        </ToolButton>
        <ToolButton label="Underline" active={state.underline} onClick={() => chain().toggleUnderline().run()}>
          <u>U</u>
        </ToolButton>
        <span className="tsep" aria-hidden="true" />
        <ToolButton label="Heading" active={state.h2} onClick={() => chain().toggleHeading({ level: 2 }).run()}>
          H2
        </ToolButton>
        <ToolButton label="Sub-heading" active={state.h3} onClick={() => chain().toggleHeading({ level: 3 }).run()}>
          H3
        </ToolButton>
        <span className="tsep" aria-hidden="true" />
        <ToolButton label="Bulleted list" active={state.bullet} onClick={() => chain().toggleBulletList().run()}>
          •≡
        </ToolButton>
        <ToolButton label="Numbered list" active={state.ordered} onClick={() => chain().toggleOrderedList().run()}>
          1.
        </ToolButton>
        <ToolButton label="Quote" active={state.quote} onClick={() => chain().toggleBlockquote().run()}>
          ❝
        </ToolButton>
        <span className="tsep" aria-hidden="true" />
        <ToolButton label="Link" active={state.link} onClick={openLink}>
          Link
        </ToolButton>
        <ToolButton label="Undo" disabled={!state.canUndo} onClick={() => chain().undo().run()}>
          ↶
        </ToolButton>
        <ToolButton label="Redo" disabled={!state.canRedo} onClick={() => chain().redo().run()}>
          ↷
        </ToolButton>
      </div>
      <EditorContent editor={editor} />
      <Modal
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
        title="Link"
        footer={
          <>
            <Button variant="ghost" onClick={() => setLinkOpen(false)}>
              Cancel
            </Button>
            <Button onClick={applyLink}>{href.trim() ? "Apply link" : "Remove link"}</Button>
          </>
        }
      >
        <Field label="Address" htmlFor="rte-link" help="For example /admissions, https://example.com, mailto:info@college.edu or tel:+919876543210. Leave empty to remove the link." error={linkError ?? undefined}>
          <input
            id="rte-link"
            type="text"
            value={href}
            autoFocus
            onChange={(event) => setHref(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyLink();
              }
            }}
          />
        </Field>
      </Modal>
    </div>
  );
}

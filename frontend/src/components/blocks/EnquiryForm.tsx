"use client";

import { useCallback, useId, useState, type FormEvent } from "react";
import { submitEnquiry } from "@/lib/api/enquiry";
import { cx } from "@/lib/cx";
import { Turnstile } from "./Turnstile";

// Set at build time. When empty (development) the spam check widget is not shown.
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

type Status = "idle" | "sending" | "done" | "error";

/**
 * The enquiry form. "tone" only changes the button colour: "dark" on the blue band, "light" in a
 * white box. The hidden "website" field is a honeypot that real visitors never fill.
 */
export function EnquiryForm({ courses, tone = "light" }: { courses: string[]; tone?: "dark" | "light" }) {
  const uid = useId();
  const [status, setStatus] = useState<Status>("idle");
  const [note, setNote] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [widgetKey, setWidgetKey] = useState(0);
  const onToken = useCallback((value: string | null) => setToken(value), []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (TURNSTILE_SITE_KEY && !token) {
      setStatus("error");
      setNote("Please complete the spam check below.");
      return;
    }
    const data = new FormData(form);
    const field = (name: string) => String(data.get(name) ?? "");
    setStatus("sending");
    setNote("");

    const result = await submitEnquiry({
      name: field("name"),
      phone: field("phone"),
      course: field("course") || undefined,
      message: field("message") || undefined,
      website: field("website"),
      source_page: window.location.pathname,
      turnstile_token: token ?? undefined,
    });

    if (result.ok) {
      form.reset();
      setStatus("done");
      setNote("Thank you! We have received your enquiry and will call you back soon.");
    } else {
      setStatus("error");
      setNote(result.message);
    }
    if (TURNSTILE_SITE_KEY) {
      setToken(null);
      setWidgetKey((key) => key + 1); // a fresh check is needed for every submit
    }
  }

  return (
    <form className="form" onSubmit={onSubmit}>
      <div className="field">
        <label htmlFor={`${uid}-name`}>Your name</label>
        <input id={`${uid}-name`} name="name" autoComplete="name" required minLength={2} maxLength={80} placeholder="Full name" />
      </div>
      <div className="field">
        <label htmlFor={`${uid}-phone`}>Phone / WhatsApp</label>
        <input
          id={`${uid}-phone`}
          name="phone"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          required
          placeholder="10-digit mobile number"
        />
      </div>
      <div className="field">
        <label htmlFor={`${uid}-course`}>Course</label>
        <select id={`${uid}-course`} name="course">
          {courses.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${uid}-message`}>Message (optional)</label>
        <textarea id={`${uid}-message`} name="message" maxLength={500} />
      </div>
      <div className="sr" aria-hidden="true">
        <label htmlFor={`${uid}-website`}>Leave this field empty</label>
        <input id={`${uid}-website`} name="website" tabIndex={-1} autoComplete="off" />
      </div>
      {TURNSTILE_SITE_KEY && <Turnstile key={widgetKey} siteKey={TURNSTILE_SITE_KEY} onToken={onToken} />}
      <button className={cx("btn", tone === "dark" ? "btn-accent" : "btn-primary")} type="submit" disabled={status === "sending"}>
        {status === "sending" ? "Sending..." : "Send enquiry"}
      </button>
      <p className={cx("note", status === "error" && "note-error")} role="status" aria-live="polite">
        {note}
      </p>
    </form>
  );
}

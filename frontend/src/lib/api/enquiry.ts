export type EnquiryPayload = {
  name: string;
  phone: string;
  course?: string;
  message?: string;
  source_page?: string;
  /** Honeypot field: stays empty for real visitors. */
  website?: string;
  turnstile_token?: string;
};

export type EnquiryResult = { ok: true } | { ok: false; message: string };

const ENDPOINT = "/api/v1/public/enquiries";

/** Sends the enquiry form to the backend and turns every outcome into a friendly message. */
export async function submitEnquiry(payload: EnquiryPayload): Promise<EnquiryResult> {
  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.status === 201) return { ok: true };
    if (response.status === 429) {
      return { ok: false, message: "Too many enquiries from this device. Please try again in an hour or call the college." };
    }
    if (response.status === 422) {
      return { ok: false, message: "Please check your name and mobile number and try again." };
    }
    if (response.status === 400 || response.status === 403) {
      return { ok: false, message: "The spam check did not pass. Please reload the page and try again." };
    }
    return { ok: false, message: "Sorry, we could not send your enquiry. Please try again later." };
  } catch {
    return { ok: false, message: "No internet connection. Please check it and try again." };
  }
}

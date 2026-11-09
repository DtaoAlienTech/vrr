// What the backend answers when something goes wrong: {detail, code, errors?} (see
// backend/app/core/errors.py). Everything the screens need to show a friendly message.
export type FieldProblem = { field: string; message: string };

export class ApiProblem extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: FieldProblem[];
  readonly extra: Record<string, unknown>;

  constructor(status: number, code: string, detail: string, errors: FieldProblem[] = [], extra: Record<string, unknown> = {}) {
    super(detail);
    this.name = "ApiProblem";
    this.status = status;
    this.code = code;
    this.errors = errors;
    this.extra = extra;
  }

  /** The problems of each form field, by the field's path ("title", "primaryCta.href"). */
  fieldMap(): Record<string, string> {
    const map: Record<string, string> = {};
    for (const { field, message } of this.errors) if (!(field in map)) map[field] = message;
    return map;
  }
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function parseProblem(status: number, body: unknown): ApiProblem {
  if (isObject(body)) {
    const { detail, code, errors, ...extra } = body;
    const list: FieldProblem[] = Array.isArray(errors)
      ? errors.flatMap((item) =>
          isObject(item) && typeof item.field === "string" && typeof item.message === "string"
            ? [{ field: item.field, message: item.message }]
            : [],
        )
      : [];
    if (typeof detail === "string") {
      return new ApiProblem(status, typeof code === "string" ? code : "error", detail, list, extra);
    }
  }
  return new ApiProblem(status, "error", FALLBACK[status] ?? "Something went wrong. Please try again.");
}

const FALLBACK: Record<number, string> = {
  401: "Please sign in again.",
  403: "You are not allowed to do that.",
  404: "That could not be found.",
  413: "That file is too large.",
  429: "Too many requests. Please wait a moment.",
  500: "The server had a problem. Please try again.",
  502: "The server is starting or restarting. Please try again in a moment.",
  503: "The server is busy. Please try again in a moment.",
};

export const NETWORK_PROBLEM = new ApiProblem(0, "network", "No internet connection. Please check it and try again.");

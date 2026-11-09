// Built from char codes so this file contains no invisible or escaped characters.
const BACKSLASH = String.fromCharCode(92);
const LINE_SEPARATOR = String.fromCharCode(0x2028);
const PARAGRAPH_SEPARATOR = String.fromCharCode(0x2029);

/** The JSON escape for a character code, for example 0x3c becomes the six characters backslash-u-0-0-3-c. */
const jsonEscape = (code: number): string => `${BACKSLASH}u${code.toString(16).padStart(4, "0")}`;

/** Serialises structured data for a <script type="application/ld+json"> tag. "<" is escaped so no text can close the tag. */
export function jsonLdString(data: Record<string, unknown>): string {
  return JSON.stringify(data)
    .replaceAll("<", jsonEscape(0x3c))
    .replaceAll(LINE_SEPARATOR, jsonEscape(0x2028))
    .replaceAll(PARAGRAPH_SEPARATOR, jsonEscape(0x2029));
}

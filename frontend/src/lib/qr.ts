// A small QR code generator (ISO/IEC 18004), written for the two-factor setup screen so the secret
// key is drawn in the browser and never sent to an outside service. Byte mode, error correction
// level M (about 15 % can be damaged), versions 1 to 40. Pure functions, no dependencies.
//
// Checked against an independent implementation for every version and every mask pattern
// (see qr.test.ts) and by scanning the drawn picture with a real decoder.

const ECC_CODEWORDS_PER_BLOCK_M = [
  0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28,
  28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28,
];
const ERROR_CORRECTION_BLOCKS_M = [
  0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33,
  35, 37, 38, 40, 43, 45, 47, 49,
];
const FORMAT_BITS_M = 0; // the two-bit code of level M
const MIN_VERSION = 1;
const MAX_VERSION = 40;

export type QrMatrix = boolean[][]; // [row][column], true = dark

const bit = (value: number, index: number): boolean => ((value >>> index) & 1) !== 0;

// ---- Reed-Solomon over GF(2^8), polynomial 0x11D ----

function gfMultiply(x: number, y: number): number {
  let result = 0;
  for (let i = 7; i >= 0; i--) {
    result = (result << 1) ^ ((result >>> 7) * 0x11d);
    result ^= ((y >>> i) & 1) * x;
  }
  return result;
}

function reedSolomonDivisor(degree: number): number[] {
  const result: number[] = new Array<number>(degree).fill(0);
  result[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i++) {
    for (let j = 0; j < result.length; j++) {
      result[j] = gfMultiply(result[j], root);
      if (j + 1 < result.length) result[j] ^= result[j + 1];
    }
    root = gfMultiply(root, 0x02);
  }
  return result;
}

function reedSolomonRemainder(data: readonly number[], divisor: readonly number[]): number[] {
  const result: number[] = new Array<number>(divisor.length).fill(0);
  for (const byte of data) {
    const factor = byte ^ (result.shift() as number);
    result.push(0);
    divisor.forEach((coefficient, i) => {
      result[i] ^= gfMultiply(coefficient, factor);
    });
  }
  return result;
}

// ---- sizes ----

function alignmentPositions(version: number): number[] {
  if (version === 1) return [];
  const count = Math.floor(version / 7) + 2;
  const step = version === 32 ? 26 : Math.ceil((version * 4 + 4) / (count * 2 - 2)) * 2;
  const result = [6];
  for (let position = version * 4 + 10; result.length < count; position -= step) result.splice(1, 0, position);
  return result;
}

function rawDataModules(version: number): number {
  let result = (16 * version + 128) * version + 64;
  if (version >= 2) {
    const count = Math.floor(version / 7) + 2;
    result -= (25 * count - 10) * count - 55;
    if (version >= 7) result -= 36;
  }
  return result;
}

function dataCodewords(version: number): number {
  return (
    Math.floor(rawDataModules(version) / 8) - ECC_CODEWORDS_PER_BLOCK_M[version] * ERROR_CORRECTION_BLOCKS_M[version]
  );
}

/** How many bytes of text fit in a version (level M). */
export function byteCapacity(version: number): number {
  const countBits = version <= 9 ? 8 : 16;
  return Math.floor((dataCodewords(version) * 8 - 4 - countBits) / 8);
}

// ---- data ----

function encodeData(bytes: Uint8Array, version: number): number[] {
  const bits: number[] = [];
  const push = (value: number, length: number) => {
    for (let i = length - 1; i >= 0; i--) bits.push((value >>> i) & 1);
  };
  push(0b0100, 4); // byte mode
  push(bytes.length, version <= 9 ? 8 : 16);
  for (const byte of bytes) push(byte, 8);

  const capacityBits = dataCodewords(version) * 8;
  push(0, Math.min(4, capacityBits - bits.length)); // terminator
  push(0, (8 - (bits.length % 8)) % 8);
  const codewords: number[] = [];
  for (let i = 0; i < bits.length; i += 8) {
    let value = 0;
    for (let j = 0; j < 8; j++) value = (value << 1) | bits[i + j];
    codewords.push(value);
  }
  for (let pad = 0xec; codewords.length < dataCodewords(version); pad ^= 0xec ^ 0x11) codewords.push(pad);
  return codewords;
}

function addErrorCorrection(data: readonly number[], version: number): number[] {
  const blocks = ERROR_CORRECTION_BLOCKS_M[version];
  const eccLength = ECC_CODEWORDS_PER_BLOCK_M[version];
  const raw = Math.floor(rawDataModules(version) / 8);
  const shortBlocks = blocks - (raw % blocks);
  const shortLength = Math.floor(raw / blocks);

  const divisor = reedSolomonDivisor(eccLength);
  const parts: number[][] = [];
  for (let i = 0, k = 0; i < blocks; i++) {
    const chunk = data.slice(k, k + shortLength - eccLength + (i < shortBlocks ? 0 : 1));
    k += chunk.length;
    const ecc = reedSolomonRemainder(chunk, divisor);
    if (i < shortBlocks) chunk.push(0); // keeps all blocks the same length; skipped below
    parts.push(chunk.concat(ecc));
  }

  const result: number[] = [];
  for (let i = 0; i < parts[0].length; i++) {
    parts.forEach((block, j) => {
      if (i !== shortLength - eccLength || j >= shortBlocks) result.push(block[i]);
    });
  }
  return result;
}

// ---- drawing ----

class Canvas {
  readonly version: number;
  readonly size: number;
  readonly modules: boolean[][];
  readonly isFunction: boolean[][];

  constructor(version: number) {
    this.version = version;
    this.size = version * 4 + 17;
    this.modules = Array.from({ length: this.size }, () => new Array<boolean>(this.size).fill(false));
    this.isFunction = Array.from({ length: this.size }, () => new Array<boolean>(this.size).fill(false));
    this.drawFunctionPatterns();
  }

  private setFunction(x: number, y: number, dark: boolean): void {
    this.modules[y][x] = dark;
    this.isFunction[y][x] = true;
  }

  private drawFunctionPatterns(): void {
    const { size, version } = this;
    for (let i = 0; i < size; i++) {
      this.setFunction(6, i, i % 2 === 0);
      this.setFunction(i, 6, i % 2 === 0);
    }
    this.finder(3, 3);
    this.finder(size - 4, 3);
    this.finder(3, size - 4);

    const positions = alignmentPositions(version);
    const last = positions.length - 1;
    positions.forEach((y, i) =>
      positions.forEach((x, j) => {
        if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
        for (let dy = -2; dy <= 2; dy++)
          for (let dx = -2; dx <= 2; dx++) this.setFunction(x + dx, y + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
      }),
    );

    this.drawFormat(0); // reserves the places; the real value is drawn once the mask is chosen
    this.drawVersion();
  }

  private finder(x: number, y: number): void {
    for (let dy = -4; dy <= 4; dy++) {
      for (let dx = -4; dx <= 4; dx++) {
        const distance = Math.max(Math.abs(dx), Math.abs(dy));
        const xx = x + dx;
        const yy = y + dy;
        if (xx >= 0 && xx < this.size && yy >= 0 && yy < this.size) this.setFunction(xx, yy, distance !== 2 && distance !== 4);
      }
    }
  }

  drawFormat(mask: number): void {
    const data = (FORMAT_BITS_M << 3) | mask;
    let remainder = data;
    for (let i = 0; i < 10; i++) remainder = (remainder << 1) ^ ((remainder >>> 9) * 0x537);
    const bits = ((data << 10) | remainder) ^ 0x5412;

    const { size } = this;
    for (let i = 0; i <= 5; i++) this.setFunction(8, i, bit(bits, i));
    this.setFunction(8, 7, bit(bits, 6));
    this.setFunction(8, 8, bit(bits, 7));
    this.setFunction(7, 8, bit(bits, 8));
    for (let i = 9; i < 15; i++) this.setFunction(14 - i, 8, bit(bits, i));
    for (let i = 0; i < 8; i++) this.setFunction(size - 1 - i, 8, bit(bits, i));
    for (let i = 8; i < 15; i++) this.setFunction(8, size - 15 + i, bit(bits, i));
    this.setFunction(8, size - 8, true); // the one module that is always dark
  }

  private drawVersion(): void {
    if (this.version < 7) return;
    let remainder = this.version;
    for (let i = 0; i < 12; i++) remainder = (remainder << 1) ^ ((remainder >>> 11) * 0x1f25);
    const bits = (this.version << 12) | remainder;
    for (let i = 0; i < 18; i++) {
      const a = this.size - 11 + (i % 3);
      const b = Math.floor(i / 3);
      this.setFunction(a, b, bit(bits, i));
      this.setFunction(b, a, bit(bits, i));
    }
  }

  drawCodewords(data: readonly number[]): void {
    const { size } = this;
    let i = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vertical = 0; vertical < size; vertical++) {
        for (let j = 0; j < 2; j++) {
          const x = right - j;
          const upward = ((right + 1) & 2) === 0;
          const y = upward ? size - 1 - vertical : vertical;
          if (!this.isFunction[y][x] && i < data.length * 8) {
            this.modules[y][x] = bit(data[i >>> 3], 7 - (i & 7));
            i++;
          }
        }
      }
    }
  }

  applyMask(mask: number): void {
    for (let y = 0; y < this.size; y++) {
      for (let x = 0; x < this.size; x++) {
        let invert: boolean;
        switch (mask) {
          case 0: invert = (x + y) % 2 === 0; break;
          case 1: invert = y % 2 === 0; break;
          case 2: invert = x % 3 === 0; break;
          case 3: invert = (x + y) % 3 === 0; break;
          case 4: invert = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; break;
          case 5: invert = ((x * y) % 2) + ((x * y) % 3) === 0; break;
          case 6: invert = ((((x * y) % 2) + ((x * y) % 3)) % 2) === 0; break;
          default: invert = ((((x + y) % 2) + ((x * y) % 3)) % 2) === 0; break;
        }
        if (!this.isFunction[y][x] && invert) this.modules[y][x] = !this.modules[y][x];
      }
    }
  }

  // The penalty score that decides which mask is the most readable (lower is better).
  penalty(): number {
    const { size, modules } = this;
    let result = 0;

    const lineScore = (get: (index: number) => boolean): number => {
      let score = 0;
      let runColor = false;
      let runLength = 0;
      const history = [0, 0, 0, 0, 0, 0, 0];
      const addHistory = (length: number) => {
        if (history[0] === 0) length += size;
        history.pop();
        history.unshift(length);
      };
      const countPatterns = (): number => {
        const n = history[1];
        const core = n > 0 && history[2] === n && history[3] === n * 3 && history[4] === n && history[5] === n;
        return (core && history[0] >= n * 4 && history[6] >= n ? 1 : 0) + (core && history[6] >= n * 4 && history[0] >= n ? 1 : 0);
      };
      for (let i = 0; i < size; i++) {
        if (get(i) === runColor) {
          runLength++;
          if (runLength === 5) score += 3;
          else if (runLength > 5) score++;
        } else {
          addHistory(runLength);
          if (!runColor) score += countPatterns() * 40;
          runColor = get(i);
          runLength = 1;
        }
      }
      if (runColor) {
        addHistory(runLength);
        runLength = 0;
      }
      runLength += size;
      addHistory(runLength);
      return score + countPatterns() * 40;
    };

    for (let y = 0; y < size; y++) result += lineScore((x) => modules[y][x]);
    for (let x = 0; x < size; x++) result += lineScore((y) => modules[y][x]);

    for (let y = 0; y < size - 1; y++) {
      for (let x = 0; x < size - 1; x++) {
        const color = modules[y][x];
        if (color === modules[y][x + 1] && color === modules[y + 1][x] && color === modules[y + 1][x + 1]) result += 3;
      }
    }

    let dark = 0;
    for (const row of modules) for (const cell of row) if (cell) dark++;
    const total = size * size;
    result += (Math.ceil(Math.abs(dark * 20 - total * 10) / total) - 1) * 10;
    return result;
  }
}

/** The smallest version (level M) that holds this many bytes, or null if nothing does. */
export function versionFor(byteLength: number): number | null {
  for (let version = MIN_VERSION; version <= MAX_VERSION; version++) {
    if (byteLength <= byteCapacity(version)) return version;
  }
  return null;
}

/** The QR code of a text as rows of dark/light modules (without the empty border around it).
 * `mask` (0 to 7) is only for tests; normally the most readable mask is chosen. */
export function encodeQr(text: string, options: { mask?: number; version?: number } = {}): QrMatrix {
  const bytes = new TextEncoder().encode(text);
  const needed = versionFor(bytes.length);
  if (needed === null) throw new RangeError("The text is too long for a QR code.");
  const version = options.version ?? needed;
  if (version < needed || version > MAX_VERSION) throw new RangeError("That version is too small for the text.");

  const canvas = new Canvas(version);
  canvas.drawCodewords(addErrorCorrection(encodeData(bytes, version), version));

  let mask = options.mask;
  if (mask === undefined) {
    let best = Number.POSITIVE_INFINITY;
    for (let candidate = 0; candidate < 8; candidate++) {
      canvas.applyMask(candidate);
      canvas.drawFormat(candidate);
      const score = canvas.penalty();
      if (score < best) {
        best = score;
        mask = candidate;
      }
      canvas.applyMask(candidate); // undo (a mask is its own inverse)
    }
  }
  if (mask === undefined || mask < 0 || mask > 7) throw new RangeError("The mask must be 0 to 7.");
  canvas.applyMask(mask);
  canvas.drawFormat(mask);
  return canvas.modules.map((row) => row.slice());
}

/** The drawing instructions of one SVG path: a rectangle for each run of dark modules in a row.
 * The border (the "quiet zone" scanners need) is included. */
export function qrPath(matrix: QrMatrix, border = 4): { path: string; size: number } {
  const parts: string[] = [];
  matrix.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      if (!row[x]) {
        x++;
        continue;
      }
      let end = x;
      while (end < row.length && row[end]) end++;
      parts.push(`M${x + border} ${y + border}h${end - x}v1h${x - end}z`);
      x = end;
    }
  });
  return { path: parts.join(""), size: matrix.length + border * 2 };
}

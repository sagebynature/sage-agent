function isControlCharacter(codePoint: number): boolean {
  return codePoint <= 0x1f || (codePoint >= 0x7f && codePoint <= 0x9f);
}

function isWideCharacter(codePoint: number): boolean {
  return (
    (codePoint >= 0x4e00 && codePoint <= 0x9fff) ||
    (codePoint >= 0x3000 && codePoint <= 0x303f) ||
    (codePoint >= 0xff00 && codePoint <= 0xffef)
  );
}

export function getStringWidth(str: string): number {
  let width = 0;

  for (const char of str) {
    const codePoint = char.codePointAt(0);
    if (codePoint === undefined) {
      continue;
    }

    if (isControlCharacter(codePoint)) {
      continue;
    }

    width += isWideCharacter(codePoint) ? 2 : 1;
  }

  return width;
}

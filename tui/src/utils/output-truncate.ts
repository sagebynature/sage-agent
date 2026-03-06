export interface TruncatedOutput {
  text: string;
  isTruncated: boolean;
  fullSize: number;
}

function truncateByBytes(input: string, maxBytes: number): string {
  let result = "";
  let usedBytes = 0;

  for (const char of input) {
    const charBytes = Buffer.byteLength(char, "utf8");
    if (usedBytes + charBytes > maxBytes) {
      break;
    }

    result += char;
    usedBytes += charBytes;
  }

  return result;
}

export function truncateOutput(output: string, maxBytes = 10 * 1024): TruncatedOutput {
  const fullSize = Buffer.byteLength(output, "utf8");
  if (fullSize <= maxBytes) {
    return {
      text: output,
      isTruncated: false,
      fullSize,
    };
  }

  const truncatedText = truncateByBytes(output, maxBytes);
  const message = `\n...[truncated output: ${fullSize} bytes total, showing first ${maxBytes} bytes]`;

  return {
    text: `${truncatedText}${message}`,
    isTruncated: true,
    fullSize,
  };
}

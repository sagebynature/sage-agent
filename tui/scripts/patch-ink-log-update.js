#!/usr/bin/env node
/**
 * Patches Ink v6's log-update module to use line-by-line overwriting instead
 * of the default erase-all-then-rewrite approach.
 *
 * The stock behaviour calls `ansiEscapes.eraseLines(previousLineCount)` which
 * blanks every line in the dynamic area before writing new content.  Between
 * the erase and the write the terminal shows blank space — visible as flicker
 * on every re-render.
 *
 * This patch replaces the render function with one that:
 *  1. Moves the cursor to the top of the dynamic area.
 *  2. Compares each line against the previous render.
 *  3. Only erases + rewrites lines that actually changed.
 *  4. Cleans up any extra lines left from a previously taller output.
 *
 * Unchanged lines are never touched, so the terminal keeps them on screen
 * without any visible interruption.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const target = resolve(__dirname, "../node_modules/ink/build/log-update.js");

const MARKER = "[sage-patch:log-update]";

let src;
try {
  src = readFileSync(target, "utf8");
} catch {
  console.log("[sage-patch] ink log-update not found — skipping.");
  process.exit(0);
}

if (src.includes(MARKER)) {
  console.log("[sage-patch] ink log-update already patched.");
  process.exit(0);
}

// The original render function:
//   const render = (str) => {
//       ...
//       stream.write(ansiEscapes.eraseLines(previousLineCount) + output);
//       previousLineCount = output.split('\n').length;
//   };
//
// We replace the body with a line-diff approach.

const OLD_RENDER = `const render = (str) => {
        if (!showCursor && !hasHiddenCursor) {
            cliCursor.hide();
            hasHiddenCursor = true;
        }
        const output = str + '\\n';
        if (output === previousOutput) {
            return;
        }
        previousOutput = output;
        stream.write(ansiEscapes.eraseLines(previousLineCount) + output);
        previousLineCount = output.split('\\n').length;
    };`;

const NEW_RENDER = `const render = (str) => { // ${MARKER}
        if (!showCursor && !hasHiddenCursor) {
            cliCursor.hide();
            hasHiddenCursor = true;
        }
        const output = str + '\\n';
        if (output === previousOutput) {
            return;
        }
        const newLines = output.split('\\n');
        const oldLines = previousOutput ? previousOutput.split('\\n') : [];
        previousOutput = output;
        if (previousLineCount === 0) {
            stream.write(output);
            previousLineCount = newLines.length;
            return;
        }
        // Line-by-line overwrite: move cursor to the top of the dynamic area
        // and rewrite only lines that changed.  Unchanged lines stay on screen
        // untouched, eliminating the visible blank flash from eraseLines().
        let buf = '';
        if (previousLineCount > 1) {
            buf += '\\x1B[' + (previousLineCount - 1) + 'A';
        }
        buf += '\\r';
        for (let i = 0; i < newLines.length; i++) {
            if (i > 0) buf += '\\n';
            if (i >= oldLines.length || newLines[i] !== oldLines[i]) {
                buf += '\\r\\x1B[2K' + newLines[i];
            }
        }
        // Erase leftover lines from previous taller output
        const extra = previousLineCount - newLines.length;
        for (let i = 0; i < extra; i++) {
            buf += '\\n\\x1B[2K';
        }
        if (extra > 0) {
            buf += '\\x1B[' + extra + 'A';
        }
        previousLineCount = newLines.length;
        stream.write(buf);
    };`;

if (!src.includes("ansiEscapes.eraseLines(previousLineCount) + output")) {
  console.error("[sage-patch] Could not find render function in log-update — skipping.");
  process.exit(0);
}

src = src.replace(OLD_RENDER, NEW_RENDER);

writeFileSync(target, src, "utf8");
console.log("[sage-patch] ink log-update patched successfully (line-diff rendering).");

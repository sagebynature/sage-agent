#!/usr/bin/env node
/**
 * Patches Ink v6's reconciler to fix a race condition where <Static> items
 * added after initial mount can be lost due to the 32 ms onRender throttle.
 *
 * Root cause: Ink only sets `isStaticDirty` when the `<ink-box internal_static>`
 * node is *created* (createInstance).  Subsequent child additions to that node
 * go through the throttled `onRender` path.  If any other render consumed the
 * leading slot within the last 32 ms (e.g. a spinner tick), the render with new
 * static items is queued as trailing.  Then useLayoutEffect fires synchronously,
 * removing the children, and the trailing call only executes afterwards — seeing
 * an empty static tree, so the content is never written to stdout.
 *
 * Fix: Mark `isStaticDirty` whenever children are added to the static node,
 * ensuring `resetAfterCommit` calls `onImmediateRender` (unthrottled).
 */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const target = resolve(__dirname, "../node_modules/ink/build/reconciler.js");

const HELPER = `\
// [sage-patch] Mark root as staticDirty when children are added to a <Static> node
const markStaticDirtyIfNeeded = (parentNode) => {
    if (parentNode.internal_static) {
        let root = parentNode;
        while (root.parentNode)
            root = root.parentNode;
        root.isStaticDirty = true;
    }
};`;

const MARKER = "markStaticDirtyIfNeeded";

let src;
try {
  src = readFileSync(target, "utf8");
} catch {
  console.log("[sage-patch] ink reconciler not found — skipping.");
  process.exit(0);
}

if (src.includes(MARKER)) {
  console.log("[sage-patch] ink reconciler already patched.");
  process.exit(0);
}

// 1. Insert helper before the reconciler config
const configStart = "export default createReconciler({";
if (!src.includes(configStart)) {
  console.error("[sage-patch] Could not find reconciler config anchor — skipping.");
  process.exit(0);
}
src = src.replace(configStart, `${HELPER}\n${configStart}`);

// 2. Replace appendInitialChild / appendChild / insertBefore
src = src.replace(
  /appendInitialChild:\s*appendChildNode,/,
  `appendInitialChild(parentNode, childNode) {
        appendChildNode(parentNode, childNode);
        markStaticDirtyIfNeeded(parentNode);
    },`,
);

src = src.replace(
  /appendChild:\s*appendChildNode,/,
  `appendChild(parentNode, childNode) {
        appendChildNode(parentNode, childNode);
        markStaticDirtyIfNeeded(parentNode);
    },`,
);

src = src.replace(
  /insertBefore:\s*insertBeforeNode,/,
  `insertBefore(parentNode, newChildNode, beforeChildNode) {
        insertBeforeNode(parentNode, newChildNode, beforeChildNode);
        markStaticDirtyIfNeeded(parentNode);
    },`,
);

writeFileSync(target, src, "utf8");
console.log("[sage-patch] ink reconciler patched successfully.");

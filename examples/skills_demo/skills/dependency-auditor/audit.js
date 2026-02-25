#!/usr/bin/env node
/**
 * audit.js — Dependency auditor for the Apollo Agent dependency-auditor skill.
 *
 * Analyzes package.json or requirements.txt files and produces a structured
 * report about dependency health, version patterns, and potential risks.
 *
 * Usage: node audit.js <command> <filepath>
 */

const fs = require("fs");
const path = require("path");

// ── Helpers ──────────────────────────────────────────────────────────────

function readFileOrDie(filepath) {
  const resolved = path.resolve(filepath);
  if (!fs.existsSync(resolved)) {
    console.error(`Error: file not found: ${resolved}`);
    process.exit(1);
  }
  return fs.readFileSync(resolved, "utf-8");
}

function classifyVersionRange(version) {
  if (!version || typeof version !== "string") return "unknown";
  if (version.startsWith("^")) return "compatible (^)";
  if (version.startsWith("~")) return "patch-only (~)";
  if (version === "*" || version === "latest") return "wildcard (dangerous)";
  if (version.includes("git") || version.includes("://")) return "git reference";
  if (version.match(/^\d+\.\d+\.\d+$/)) return "pinned (exact)";
  if (version.includes(">=") || version.includes("<=") || version.includes("||"))
    return "range";
  return "other";
}

const SECURITY_RISK_KEYWORDS = [
  "exec",
  "eval",
  "shell",
  "admin",
  "root",
  "sudo",
  "crypto",
  "password",
  "token",
  "secret",
];

function flagPotentialRisks(name) {
  const lower = name.toLowerCase();
  return SECURITY_RISK_KEYWORDS.filter((kw) => lower.includes(kw));
}

function printSection(title) {
  console.log(`\n${"─".repeat(50)}`);
  console.log(`  ${title}`);
  console.log(`${"─".repeat(50)}`);
}

// ── Analyzers ────────────────────────────────────────────────────────────

function analyzePackageJson(filepath) {
  const raw = readFileOrDie(filepath);
  let pkg;
  try {
    pkg = JSON.parse(raw);
  } catch (e) {
    console.error(`Error: invalid JSON in ${filepath}: ${e.message}`);
    process.exit(1);
  }

  const deps = pkg.dependencies || {};
  const devDeps = pkg.devDependencies || {};
  const peerDeps = pkg.peerDependencies || {};
  const allDeps = { ...deps, ...devDeps, ...peerDeps };

  // Header
  console.log("╔══════════════════════════════════════════════╗");
  console.log("║     Dependency Audit Report (package.json)   ║");
  console.log("╚══════════════════════════════════════════════╝");
  console.log(`  File: ${path.resolve(filepath)}`);
  console.log(`  Package: ${pkg.name || "(unnamed)"} v${pkg.version || "0.0.0"}`);
  console.log(`  Analyzed: ${new Date().toISOString()}`);

  // Summary counts
  printSection("Summary");
  console.log(`  Production dependencies: ${Object.keys(deps).length}`);
  console.log(`  Dev dependencies:        ${Object.keys(devDeps).length}`);
  console.log(`  Peer dependencies:       ${Object.keys(peerDeps).length}`);
  console.log(`  Total unique:            ${Object.keys(allDeps).length}`);

  // Version range analysis
  printSection("Version Range Distribution");
  const rangeCounts = {};
  for (const [, ver] of Object.entries(allDeps)) {
    const cls = classifyVersionRange(ver);
    rangeCounts[cls] = (rangeCounts[cls] || 0) + 1;
  }
  for (const [cls, count] of Object.entries(rangeCounts).sort((a, b) => b[1] - a[1])) {
    const pct = ((count / Object.keys(allDeps).length) * 100).toFixed(1);
    const bar = "█".repeat(Math.round(pct / 5));
    console.log(`  ${cls.padEnd(25)} ${String(count).padStart(3)} (${pct}%) ${bar}`);
  }

  // Risk flags
  printSection("Security Keyword Flags");
  let riskCount = 0;
  for (const [name] of Object.entries(allDeps)) {
    const risks = flagPotentialRisks(name);
    if (risks.length > 0) {
      console.log(`  ⚠  ${name} — matches: ${risks.join(", ")}`);
      riskCount++;
    }
  }
  if (riskCount === 0) {
    console.log("  ✓  No packages match security-sensitive keywords");
  }

  // Wildcard / dangerous versions
  printSection("Warnings");
  let warnings = 0;
  for (const [name, ver] of Object.entries(allDeps)) {
    if (ver === "*" || ver === "latest") {
      console.log(`  ⚠  ${name}: uses wildcard version "${ver}" — pin to a specific range`);
      warnings++;
    }
    if (ver.includes("git") || ver.includes("://")) {
      console.log(`  ⚠  ${name}: references a git URL — not reproducible`);
      warnings++;
    }
  }
  if (warnings === 0) {
    console.log("  ✓  No version warnings found");
  }

  // Engine requirements
  if (pkg.engines) {
    printSection("Engine Requirements");
    for (const [eng, ver] of Object.entries(pkg.engines)) {
      console.log(`  ${eng}: ${ver}`);
    }
  }

  console.log(`\n${"═".repeat(50)}`);
  console.log(`  Audit complete. ${Object.keys(allDeps).length} packages analyzed.`);
  console.log(`${"═".repeat(50)}`);
}

function analyzeRequirementsTxt(filepath) {
  const raw = readFileOrDie(filepath);
  const lines = raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#") && !l.startsWith("-"));

  console.log("╔══════════════════════════════════════════════╗");
  console.log("║  Dependency Audit Report (requirements.txt)  ║");
  console.log("╚══════════════════════════════════════════════╝");
  console.log(`  File: ${path.resolve(filepath)}`);
  console.log(`  Analyzed: ${new Date().toISOString()}`);

  printSection("Summary");
  console.log(`  Total packages: ${lines.length}`);

  // Parse and categorize
  const pinned = [];
  const ranged = [];
  const unpinned = [];

  for (const line of lines) {
    if (line.includes("==")) pinned.push(line);
    else if (line.match(/[><=!]/)) ranged.push(line);
    else unpinned.push(line);
  }

  printSection("Version Pinning");
  console.log(`  Pinned (==):     ${pinned.length}`);
  console.log(`  Range (>=, etc): ${ranged.length}`);
  console.log(`  Unpinned:        ${unpinned.length}`);

  if (unpinned.length > 0) {
    printSection("Warnings: Unpinned Packages");
    for (const pkg of unpinned) {
      console.log(`  ⚠  ${pkg} — no version constraint`);
    }
  }

  printSection("Security Keyword Flags");
  let riskCount = 0;
  for (const line of lines) {
    const name = line.split(/[><=!;@\[]/)[0].trim();
    const risks = flagPotentialRisks(name);
    if (risks.length > 0) {
      console.log(`  ⚠  ${name} — matches: ${risks.join(", ")}`);
      riskCount++;
    }
  }
  if (riskCount === 0) {
    console.log("  ✓  No packages match security-sensitive keywords");
  }

  console.log(`\n${"═".repeat(50)}`);
  console.log(`  Audit complete. ${lines.length} packages analyzed.`);
  console.log(`${"═".repeat(50)}`);
}

// ── CLI ──────────────────────────────────────────────────────────────────

function usage() {
  console.log(`Usage: node audit.js <command> <filepath>

Commands:
  package <path>       Analyze a package.json file
  requirements <path>  Analyze a requirements.txt file
  scan <path>          Auto-detect and analyze

Examples:
  node audit.js package ./package.json
  node audit.js requirements ./requirements.txt
  node audit.js scan ./package.json`);
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length < 2) usage();

const [command, filepath] = args;

switch (command) {
  case "package":
    analyzePackageJson(filepath);
    break;
  case "requirements":
    analyzeRequirementsTxt(filepath);
    break;
  case "scan": {
    const basename = path.basename(filepath).toLowerCase();
    if (basename === "package.json") {
      analyzePackageJson(filepath);
    } else if (basename.includes("requirements") && basename.endsWith(".txt")) {
      analyzeRequirementsTxt(filepath);
    } else {
      // Try JSON first
      try {
        JSON.parse(readFileOrDie(filepath));
        analyzePackageJson(filepath);
      } catch {
        analyzeRequirementsTxt(filepath);
      }
    }
    break;
  }
  default:
    console.error(`Error: unknown command '${command}'`);
    usage();
}

#!/usr/bin/env node
// audit.js — Dependency auditor for package.json and requirements.txt
// Usage: node audit.js <file-path>

'use strict';

const fs = require('fs');
const path = require('path');

const filePath = process.argv[2];

if (!filePath) {
  console.error('Usage: audit.js <package.json|requirements.txt>');
  process.exit(1);
}

const resolvedPath = path.resolve(filePath);

if (!fs.existsSync(resolvedPath)) {
  console.error(`File not found: ${resolvedPath}`);
  process.exit(1);
}

const content = fs.readFileSync(resolvedPath, 'utf8');
const ext = path.extname(resolvedPath);
const basename = path.basename(resolvedPath);

function classifyNpmVersion(version) {
  if (!version || version === '*' || version === '') return 'wildcard';
  if (version.startsWith('^')) return 'caret';
  if (version.startsWith('~')) return 'tilde';
  if (/^[><=]/.test(version) || version.includes(' - ')) return 'gt/range';
  if (/^\d/.test(version)) return 'exact';
  return 'other';
}

function auditPackageJson() {
  let pkg;
  try {
    pkg = JSON.parse(content);
  } catch (e) {
    console.error('Failed to parse JSON:', e.message);
    process.exit(1);
  }

  const deps = pkg.dependencies || {};
  const devDeps = pkg.devDependencies || {};
  const peerDeps = pkg.peerDependencies || {};

  const allDeps = { ...deps };
  const allDevDeps = { ...devDeps };

  const counts = { exact: 0, caret: 0, tilde: 0, 'gt/range': 0, wildcard: 0, other: 0 };
  const devCounts = { exact: 0, caret: 0, tilde: 0, 'gt/range': 0, wildcard: 0, other: 0 };
  const warnings = [];

  for (const [name, ver] of Object.entries(allDeps)) {
    const cls = classifyNpmVersion(ver);
    counts[cls]++;
    if (cls === 'wildcard') warnings.push(`  [WARN] ${name}@${ver} — unpinned wildcard in dependencies`);
    if (cls === 'gt/range') warnings.push(`  [INFO] ${name}@${ver} — range specifier (less predictable)`);
  }

  for (const [name, ver] of Object.entries(allDevDeps)) {
    const cls = classifyNpmVersion(ver);
    devCounts[cls]++;
    if (cls === 'wildcard') warnings.push(`  [WARN] ${name}@${ver} — unpinned wildcard in devDependencies`);
  }

  console.log('╔══════════════════════════════════════════════════╗');
  console.log(`║  Dependency Audit: ${basename.padEnd(29)}║`);
  console.log('╚══════════════════════════════════════════════════╝');
  console.log('');
  console.log(`Package: ${pkg.name || 'unknown'}  v${pkg.version || '?'}`);
  console.log('');
  console.log('── Production Dependencies ──────────────────────────');
  console.log(`  Total:     ${Object.keys(allDeps).length}`);
  for (const [cls, cnt] of Object.entries(counts)) {
    if (cnt > 0) console.log(`  ${cls.padEnd(12)}: ${cnt}`);
  }
  console.log('');
  console.log('── Dev Dependencies ─────────────────────────────────');
  console.log(`  Total:     ${Object.keys(allDevDeps).length}`);
  for (const [cls, cnt] of Object.entries(devCounts)) {
    if (cnt > 0) console.log(`  ${cls.padEnd(12)}: ${cnt}`);
  }
  if (Object.keys(peerDeps).length > 0) {
    console.log('');
    console.log('── Peer Dependencies ────────────────────────────────');
    console.log(`  Total:     ${Object.keys(peerDeps).length}`);
  }
  console.log('');
  if (warnings.length > 0) {
    console.log('── Warnings & Notes ─────────────────────────────────');
    warnings.forEach(w => console.log(w));
  } else {
    console.log('── Warnings & Notes ─────────────────────────────────');
    console.log('  No critical issues detected.');
  }
  console.log('');
  console.log('── Summary ──────────────────────────────────────────');
  const totalDeps = Object.keys(allDeps).length + Object.keys(allDevDeps).length;
  const wildcards = counts.wildcard + devCounts.wildcard;
  console.log(`  Total packages: ${totalDeps}`);
  console.log(`  Unpinned (wildcard): ${wildcards}`);
  console.log(`  Carets (^): ${counts.caret + devCounts.caret} — allow minor/patch updates`);
  console.log(`  Tildes (~): ${counts.tilde + devCounts.tilde} — allow patch updates only`);
  console.log(`  Exact pins: ${counts.exact + devCounts.exact} — fully reproducible`);
  console.log('');
  const riskLevel = wildcards > 0 ? 'HIGH' : (counts.caret + devCounts.caret) > 10 ? 'MEDIUM' : 'LOW';
  console.log(`  Risk level: ${riskLevel}`);
}

function auditRequirementsTxt() {
  const lines = content.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
  const pinned = [];
  const unpinned = [];
  const ranged = [];

  for (const line of lines) {
    // Handle extras like package[extra]==version
    const cleanLine = line.split(';')[0].trim(); // strip env markers
    if (/==/.test(cleanLine)) {
      pinned.push(cleanLine);
    } else if (/[><=~!]/.test(cleanLine)) {
      ranged.push(cleanLine);
    } else {
      // bare package name or git url
      unpinned.push(cleanLine);
    }
  }

  console.log('╔══════════════════════════════════════════════════╗');
  console.log(`║  Dependency Audit: ${basename.padEnd(29)}║`);
  console.log('╚══════════════════════════════════════════════════╝');
  console.log('');
  console.log('── Python Requirements ───────────────────────────────');
  console.log(`  Total packages:    ${lines.length}`);
  console.log(`  Exact (==):        ${pinned.length}`);
  console.log(`  Range (>=,~=,...): ${ranged.length}`);
  console.log(`  Unpinned:          ${unpinned.length}`);
  console.log('');
  if (unpinned.length > 0) {
    console.log('── Unpinned Packages (no == pin) ────────────────────');
    unpinned.forEach(p => console.log(`  [WARN] ${p}`));
    console.log('');
  }
  if (ranged.length > 0) {
    console.log('── Range-Specified Packages ─────────────────────────');
    ranged.forEach(p => console.log(`  [INFO] ${p}`));
    console.log('');
  }
  console.log('── Summary ──────────────────────────────────────────');
  const riskLevel = unpinned.length > 2 ? 'HIGH' : unpinned.length > 0 ? 'MEDIUM' : 'LOW';
  console.log(`  Risk level: ${riskLevel}`);
  if (unpinned.length > 0) {
    console.log(`  Recommendation: Pin unpinned packages with == for reproducible builds.`);
  } else {
    console.log(`  All packages are pinned or range-specified.`);
  }
}

if (basename === 'package.json' || ext === '.json') {
  auditPackageJson();
} else if (basename.includes('requirements') || ext === '.txt') {
  auditRequirementsTxt();
} else {
  console.error(`Unsupported file type: ${basename}. Supported: package.json, requirements.txt`);
  process.exit(1);
}

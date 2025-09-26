#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const buildDir = path.join(repoRoot, 'libs', 'zotero-web-library', 'build', 'static', 'web-library');
const publicDir = path.join(repoRoot, 'frontend', 'public', 'zotero');

if (!fs.existsSync(buildDir)) {
  console.error('Zotero build directory not found:', buildDir);
  process.exit(1);
}

fs.rmSync(publicDir, { recursive: true, force: true });
fs.mkdirSync(publicDir, { recursive: true });

const copyRecursive = (src, dest) => {
  const stats = fs.statSync(src);
  if (stats.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    fs.copyFileSync(src, dest);
  }
};

copyRecursive(buildDir, publicDir);

console.log('Zotero assets copied to', publicDir);

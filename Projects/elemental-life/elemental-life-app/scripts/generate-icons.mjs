/**
 * Generate Android icons from SVG using Sharp.
 * Размеры: mdpi=48, hdpi=72, xhdpi=96, xxhdpi=144, xxxhdpi=192
 */
import sharp from 'sharp';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

const svgBuffer = readFileSync(resolve(root, 'public', 'icon.svg'));

const sizes = [
  { dir: 'mipmap-mdpi', size: 48 },
  { dir: 'mipmap-hdpi', size: 72 },
  { dir: 'mipmap-xhdpi', size: 96 },
  { dir: 'mipmap-xxhdpi', size: 144 },
  { dir: 'mipmap-xxxhdpi', size: 192 },
];

const resDir = resolve(root, 'android', 'app', 'src', 'main', 'res');

for (const { dir, size } of sizes) {
  const outDir = resolve(resDir, dir);
  mkdirSync(outDir, { recursive: true });

  const png = await sharp(svgBuffer)
    .resize(size, size)
    .png()
    .toBuffer();

  writeFileSync(resolve(outDir, 'ic_launcher.png'), png);
  writeFileSync(resolve(outDir, 'ic_launcher_round.png'), png);
  writeFileSync(resolve(outDir, 'ic_launcher_foreground.png'), png);
  console.log(`✅ ${dir} (${size}px)`);
}

// Also create a web favicon
const favicon = await sharp(svgBuffer).resize(64, 64).png().toBuffer();
writeFileSync(resolve(root, 'public', 'favicon.png'), favicon);
console.log('✅ favicon.png (64px)');

console.log('🎉 All icons generated!');

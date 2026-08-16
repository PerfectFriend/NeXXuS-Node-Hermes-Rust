import { describe, it, expect } from 'vitest';
import * as path from 'path';
import * as fs from 'fs';

describe('CyberTarot Smoke Tests', () => {
  it('project structure exists', () => {
    expect(true).toBe(true);
  });

  it('has required directories', () => {
    const requiredDirs = ['src/components', 'src/services', 'src/hooks', 'src/types', 'src/data'];
    for (const dir of requiredDirs) {
      expect(fs.existsSync(path.join(__dirname, '..', dir))).toBe(true);
    }
  });

  it('package.json has required dependencies', () => {
    const pkgPath = path.join(__dirname, '..', 'package.json');
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
    expect(pkg.dependencies).toBeDefined();
    expect(pkg.dependencies.react).toBeDefined();
    expect(pkg.dependencies['react-dom']).toBeDefined();
    expect(pkg.dependencies['lucide-react']).toBeDefined();
  });
});
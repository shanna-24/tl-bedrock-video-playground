// Feature: obsidian-lens-frontend, Property 2: Design tokens match the Obsidian Lens specification
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Validates: Requirements 2.1
 *
 * Property 2: For any color token defined in the Obsidian Lens palette specification,
 * the value configured in the Tailwind CSS @theme directive should equal the specified hex value.
 */

const tokenMap: Record<string, string> = {
  background: '#060e20',
  surface: '#060e20',
  'surface-dim': '#060e20',
  'surface-container-lowest': '#000000',
  'surface-container-low': '#091328',
  'surface-container': '#0f1930',
  'surface-container-high': '#141f38',
  'surface-container-highest': '#192540',
  'surface-variant': '#192540',
  'surface-bright': '#1f2b49',
  primary: '#b8fd4b',
  'primary-container': '#83c300',
  'primary-dim': '#aaee3d',
  'on-primary': '#3d5e00',
  'on-primary-container': '#223600',
  'on-surface': '#dee5ff',
  'on-surface-variant': '#a3aac4',
  'on-background': '#dee5ff',
  outline: '#6d758c',
  'outline-variant': '#40485d',
  error: '#ff7351',
  'error-container': '#b92902',
  'error-dim': '#d53d18',
  'on-error': '#450900',
  'on-error-container': '#ffd2c8',
  secondary: '#dfec5f',
  'secondary-container': '#5c6300',
  tertiary: '#fffae4',
  'tertiary-container': '#fcef58',
  'inverse-surface': '#faf8ff',
  'inverse-on-surface': '#4d556b',
  'inverse-primary': '#456900',
};

describe('Property 2: Design tokens match the Obsidian Lens specification', () => {
  const cssContent = fs.readFileSync(
    path.resolve(__dirname, '../index.css'),
    'utf-8'
  );

  it('each color token in the spec exists in index.css with the correct hex value', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...Object.entries(tokenMap)),
        ([name, expectedValue]) => {
          const pattern = `--color-${name}: ${expectedValue}`;
          expect(cssContent).toContain(pattern);
        }
      ),
      { numRuns: 100 }
    );
  });
});

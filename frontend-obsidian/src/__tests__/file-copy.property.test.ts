// Feature: obsidian-lens-frontend, Property 1: Copied files are identical to source
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Validates: Requirements 1.6
 *
 * Property 1: For any file in the set of files copied from frontend/src/ to
 * frontend-obsidian/src/, the content of the destination file should be
 * byte-identical to the source file.
 */

const copiedFiles = [
  'types/index.ts',
  'services/api.ts',
  'services/electron.ts',
  'hooks/useAuth.ts',
  'hooks/useIndexes.ts',
  'hooks/useSearch.ts',
  'hooks/useVideos.ts',
  'hooks/useWebSocket.ts',
  'contexts/AuthContext.tsx',
  'contexts/WebSocketContext.tsx',
  'components/Auth/ProtectedRoute.tsx',
];

const repoRoot = path.resolve(__dirname, '../../..');

describe('Property 1: Copied files are identical to source', () => {
  it('each copied file in frontend-obsidian/src/ is byte-identical to frontend/src/', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...copiedFiles),
        (filePath) => {
          const sourcePath = path.join(repoRoot, 'frontend', 'src', filePath);
          const destPath = path.join(repoRoot, 'frontend-obsidian', 'src', filePath);

          const sourceContent = fs.readFileSync(sourcePath);
          const destContent = fs.readFileSync(destPath);

          expect(destContent.equals(sourceContent)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});

/** Reproducible unsigned Windows folder build; optional packet-capture native bindings are not rebuilt. */
import { build, Platform, Arch } from 'electron-builder';
import * as path from 'node:path';
const appDir = path.resolve(import.meta.dirname, '../apps/roku-engineer-studio');
await build({
  projectDir: appDir,
  targets: Platform.WINDOWS.createTarget(['dir'], Arch.x64),
  config: { npmRebuild: false, afterAllArtifactBuild: path.join(appDir, 'scripts/build-hooks-entry.cjs') },
  publish: 'never',
});

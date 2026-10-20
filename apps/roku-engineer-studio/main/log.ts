/**
 * Main-process logger. Thin wrapper over the shared logger in `roku-engineer-studio-platform` so the
 * Electron main process logs the same way as the renderer and the packages. Verbose (`debug`)
 * output is gated by the unified `ROKU_ENGINEER_DEBUG` flag (or `ROKU_ENGINEER_MAIN_DEBUG=1` for just the main process).
 *
 * Writes to the global `console`, so when the user enables File → Debug Logging the existing console
 * wrapper in main.ts still mirrors every line into the debug log file.
 */

import { createNodeLogger } from 'roku-engineer-studio-platform/node';

const logger = createNodeLogger('[Main]', 'ROKU_ENGINEER_MAIN_DEBUG');

export function mainLog(...args: unknown[]): void {
  logger.log(...args);
}

export function mainWarn(...args: unknown[]): void {
  logger.warn(...args);
}

export function mainError(...args: unknown[]): void {
  logger.error(...args);
}

/** Verbose trace — only emitted when `ROKU_ENGINEER_DEBUG`/`ROKU_ENGINEER_MAIN_DEBUG` is set. */
export function mainDebug(...args: unknown[]): void {
  logger.debug(...args);
}

export function isMainDebug(): boolean {
  return logger.isDebugEnabled();
}

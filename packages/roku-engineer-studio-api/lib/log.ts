/**
 * Roku Engineer Studio API logger. Thin wrapper over the shared logger in `roku-engineer-studio-platform` so
 * the API package's diagnostics format the same way as the rest of the app. Verbose (`debug`) output
 * is gated by the unified `ROKU_ENGINEER_DEBUG` flag, or `ROKU_ENGINEER_API_DEBUG=1` for just this package.
 *
 * This is for the library's own diagnostics only — deliberate command-line output (the `rds` CLI,
 * the `examples/`) keeps writing to `console` directly so its stdout stays clean and unprefixed.
 */

import { createNodeLogger } from 'roku-engineer-studio-platform/node';

const logger = createNodeLogger('[API]', 'ROKU_ENGINEER_API_DEBUG');

export function apiLog(...args: unknown[]): void {
  logger.log(...args);
}

export function apiWarn(...args: unknown[]): void {
  logger.warn(...args);
}

export function apiError(...args: unknown[]): void {
  logger.error(...args);
}

/** Verbose trace — only emitted when `ROKU_ENGINEER_DEBUG`/`ROKU_ENGINEER_API_DEBUG` is set. */
export function apiDebug(...args: unknown[]): void {
  logger.debug(...args);
}

export function isApiDebug(): boolean {
  return logger.isDebugEnabled();
}

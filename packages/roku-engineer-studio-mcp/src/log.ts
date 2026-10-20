/**
 * MCP server logger. Wraps the shared logger in `roku-engineer-studio-platform`, but pins the sink to
 * **stderr for every level** — stdout is reserved for the MCP JSON-RPC protocol stream, so any
 * diagnostic written to stdout would corrupt the transport. Verbose (`debug`) output is gated by the
 * unified `ROKU_ENGINEER_DEBUG` flag, or `ROKU_ENGINEER_MCP_DEBUG=1` for just the MCP server.
 */

import { createLogger, type LogSink } from 'roku-engineer-studio-platform';
import { debugEnvEnabled } from 'roku-engineer-studio-platform/node';

// Everything goes to stderr; stdout belongs to the protocol.
const stderrSink: LogSink = {
  log: (...args) => console.error(...args),
  warn: (...args) => console.error(...args),
  error: (...args) => console.error(...args),
};

const logger = createLogger({
  prefix: '[roku-engineer-studio-mcp]',
  debug: () => debugEnvEnabled('ROKU_ENGINEER_MCP_DEBUG'),
  sink: stderrSink,
});

export function mcpLog(...args: unknown[]): void {
  logger.log(...args);
}

export function mcpWarn(...args: unknown[]): void {
  logger.warn(...args);
}

export function mcpError(...args: unknown[]): void {
  logger.error(...args);
}

/** Verbose trace — only emitted when `ROKU_ENGINEER_DEBUG`/`ROKU_ENGINEER_MCP_DEBUG` is set. Still stderr-only. */
export function mcpDebug(...args: unknown[]): void {
  logger.debug(...args);
}

export function isMcpDebug(): boolean {
  return logger.isDebugEnabled();
}

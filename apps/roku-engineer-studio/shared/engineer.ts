/** Public workspace contract. Secrets and unrestricted filesystem APIs never cross this bridge. */
export type ProjectFile = { path: string; size: number; sha256: string };
export type Project = { root: string; title: string; files: ProjectFile[]; revision: string };
export type Change = { path: string; before?: string; beforeSha256: string | null; content: string };
export type Proposal = { title: string; changes: Change[] };
export type AgentMessage = { role: 'user' | 'assistant'; content: string };
export type WorkspaceResult<T = Record<string, unknown>> = { ok: true; data: T } | { ok: false; error: string };
export type WorkspaceAction = 'status' | 'restore' | 'pick' | 'scaffold' | 'project' | 'read' | 'apply' | 'preview' | 'validate' | 'lint' | 'package' | 'reveal' | 'settings' | 'configure' | 'chat' | 'export-report' | 'cancel' | 'tool';
export type WorkspaceRequest = { action: WorkspaceAction; revision?: string; path?: string; changes?: Change[]; generator?: string; content?: string; name?: string; kind?: string; messages?: AgentMessage[]; model?: string; apiKey?: string; clearKey?: boolean; python?: string };
export const ENGINEER_CHANNEL = 'engineer:workspace';
export type EngineerAPI = { request<T = Record<string, unknown>>(request: WorkspaceRequest): Promise<WorkspaceResult<T>> };

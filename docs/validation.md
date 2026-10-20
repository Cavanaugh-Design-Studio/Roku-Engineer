# Validation record — 2026-10-20

This is a local development build, with separate release gates. Checks ran on Windows using Node 24.22.0, Python 3.13, and Electron 44.9.1.

| Check | Result |
| --- | --- |
| Full workspace typecheck | Passed across platform, device API, MCP, network inspector, cloud client, Electron, renderer, scripts, relay, and experimental renderer |
| Retained device / protocol unit tests | 247 passed: API 126, network inspector 75, cloud client 46 |
| New Python workspace tests | 12 passed |
| New agent / Python-child tests | 8 passed |
| Desktop bundle | Passed; main/preload, workers, 193 renderer modules, and shared resources compiled |
| Desktop maintenance checks | Passed: artifact identity, remembered connections, cloud-account pruning, documentation versions, updater error classification |
| CLI import and command help | Passed; command identity is `roku-engineer` |
| Compiled MCP stdio | 51 tools, 4 resources, 3 prompts; Action Script validation passed |
| Compiled HTTP relay | Health, missing-token rejection, configured-token acceptance passed; zero device commands sent |
| Real Electron source workflow | 12 workflow checks passed; no captured renderer errors |
| Unsigned Windows folder package | Built with native dependency rebuild disabled; packaged launch and channel creation checked |
| Native window controls | Six checks passed in both source and packaged app: workspace / lab maximize-restore, F11 fullscreen, and fullscreen exit by F11 or the restore button |

The Electron workflow exercises project creation with real Python, required-field dialog Cancel, editing and backup saves, unsaved-change cancellation, generator preview / Apply, validation, report export, ZIP building, command search, Device Lab switching, and Action Scripts / Monaco Fiddle / analysis windows. Native pickers are scripted for repeatability. Screenshots were visually inspected; this does not prove native-picker interaction or device functionality.

Resize verification uses native Electron content sizing at 900 × 600, 1024 × 720, 1280 × 800, 1480 × 980, and 1920 × 1080, across Overview, Project editor, Integrations, Readiness, and Settings: 25 combinations. Requested and measured CSS dimensions match in the recorded matrix. Checks cover horizontal overflow and the bounds of the header, content, status, assistant toggle, editor toolbar, and editor footer. Additional 125% / 150% zoom checks keep the editor footer accessible. Yuki's drawer opens / closes in compact windows and can be collapsed / reopened on wide windows. The test forces display scale 1 for consistent screenshots; zoom coverage is not a claim of testing every OS DPI / multi-monitor configuration.

The packaged application check launches `Roku Engineer Studio.exe`, verifies application identity and included engine / license resources, and creates a channel using the bundled Python sources and locally installed Python dependencies. It restores workspace preferences after testing. Python is an external prerequisite; its dependencies are not bundled into the executable.

Window-control checks use real Electron window state and native `webContents.sendInputEvent` keyboard input. Both workspace and lab return to the original 1280 × 800 bounds after maximize / restore and fullscreen exit. Fullscreen updates the restore icon, and the top-right restore button can exit fullscreen. Repeat Windows packaging now replaces the previous unpacked output rather than silently retaining a stale executable.

Evidence is generated under `artifacts/` (ignored by Git): `studio-qa/report.json`, screenshots, `transport-smoke.json`, and `packaged-smoke.json`. Representative workspace screenshots are checked in under `docs/images/`.

## Dependency gate

The first imported dependency audit reported 39 entries including four critical findings. Updating Electron, Monaco, Solid, concurrently, sharp, patchable transitive packages, DOMPurify, and the Electron downloader reduced the final audit to **7 high, 0 critical, 0 moderate, 0 low**.

The seven entries represent two advisory roots plus their dependent packages:

- `braces` stack-exhaustion denial of service, propagated through `micromatch`, `fast-glob`, `chokidar`, `roku-deploy`, and `brighterscript`: [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
- `node-forge` RSA PKCS#1 v1.5 signature-verification issue: [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv).

At the time checked, npm offered no patched release for these roots (`braces` 3.0.3 and `node-forge` 1.4.0). Dependency replacement / remediation and impact review remain a release gate. This record does not claim those advisories are unexploitable. Re-run `npm audit` before release; counts can change as advisories are published.

## External acceptance

- A real developer-mode Roku: discovery, remote controls, screenshots, sideload / delete, performance measurements, telnet, debugger, App Connector, script execution, and multi-device relay.
- Representative firmware and generated BrightScript / SceneGraph behavior. SGDEX must be installed separately. Local heuristic checks are not official certification.
- Live Anthropic / Tavily / voice services, model access and billing, and OS audio permissions. Agent tests use provider fixtures and do not prove live generation.
- Installed MCP-host configuration and tool use. QA did not modify host configs.
- Cloud-emulator credentials, lifecycle, and live video / port bridges.
- Protected remote deployment, TLS, client authentication interoperability, and live network capture / proxy rules.
- Native packet-capture drivers / privileges. The local Windows folder build skipped native binding rebuilds; capture is not accepted by this build.
- Java 21+, official analyzer download, and analysis of a real channel package.
- Signed installers, notarized macOS builds, Linux builds, platform-specific keychains, and clean-machine installation. The local artifact is an unsigned Windows app folder.

## Reproduce

Run `npm run verify` after installing npm and Python dependencies. Check window controls with `node scripts/verify-window-controls.mjs`. For the unsigned Windows folder build use `npm run build:win:unpacked`. For its runtime smoke test, run `node scripts/verify-packaged-studio.mjs "<absolute path to Roku Engineer Studio.exe>"`. Pass the same executable path to `verify-window-controls.mjs` to check packaged window controls. Regenerate the identity assets with `npm run icons:generate`.

# Capability inventory

This records implementation coverage, not universal hardware acceptance. Source inclusion, local fixtures, real Electron workflows, and live device/service behavior are separate forms of evidence.

| Capability | Location | Acceptance scope |
| --- | --- | --- |
| SceneGraph / grid / SGDEX starters and artwork | Workspace → Create | Python and Electron tests; SGDEX library external |
| File browser, editor, search, command palette | Workspace → Project editor | Real read/edit/save/navigation checked |
| Hash conflict checks and retained backups | `engineer_bridge.py` | Conflict / backup / duplicate-change tests |
| Seven generator previews and reviewed Apply | Workspace → Integrations | Every generator checked; real Apply workflow |
| Yuki project tools and proposals | `main/engineer-agent.ts` | Provider fixtures; live Anthropic untested |
| Local readiness and Markdown exports | Workspace → Readiness | Real Python checks and Electron export |
| Channel ZIP creation | Workspace → Readiness | Archive content/exclusions and repeated hash checks |
| Original voice / research / automode | `roku_engineer.py`, `system/` | Preserved; interactive services untested |
| SSDP discovery / subnet scan / manual connection | Device Lab discovery | Included; physical devices required |
| Multiple devices / saved sessions | Device Lab tabs/settings | Included; shell loaded locally |
| D-pad / media / keyboard / floating remote | Device Lab → Remote | Included; hardware pending |
| Apps / launch / deep links / device queries | Device Lab panels | Included; hardware pending |
| Screenshots / CPU and memory charts | Device Lab panels | Included; real measurements pending |
| Sideload / delete / developer auth | Device Lab → Dev App | Included; developer-mode device pending |
| Multi-device sideload relay | Settings → Sideload Relay | Included; fan-out device run pending |
| Telnet console / structured logs / export | Device Lab → Console | Included; protocol fixtures retained |
| Saved-log viewer / port terminals | File menu / main window modules | Included; live console pending |
| Socket debugger / breakpoints / steps / watches | API debugger + console sidebar | Protocol fixtures retained; hardware pending |
| RALE / App Connector calls | Device Lab → App Connector | Argument fixtures retained; device TrackerTask needed |
| Node lookup / update / registry editor | App Connector built-ins | Included; device mutations pending |
| TrackerTask guide and export | App Connector; `roku-components/` | Companion source included |
| Network proxy / request and response inspection | Network Inspector | Parser / body / search fixtures retained |
| Optional hotspot packet capture | Network Inspector platform modules | Native drivers/permissions pending |
| Mock / block / reset / throttle traffic rules | Network Inspector | Rule fixtures retained; live proxy pending |
| HAR / curl / PCAP / saved session viewer | Network Inspector and session window | Included; real capture acceptance pending |
| Action Script builder / library | File → Action Scripts | Real standalone window checked |
| Conditions / variables / waits / branches | API script engine / shared catalogs | Validator fixtures retained; device execution pending |
| Pause / resume / stop / skip / artifacts | Script executor | Included; representative device run pending |
| PDF test-run reports | Action Script exports | Included; device-derived export pending |
| Monaco BrightScript Fiddle | File → Fiddle | Real editor-load check; device execution pending |
| Official static-analysis launcher | File → Static Channel Analysis | Window checked; Java/tool download/real analysis pending |
| Headless device CLI | `roku-engineer-studio-api` | Built command help and fixtures |
| MCP tools / resources / prompts | `roku-engineer-studio-mcp` | Compiled stdio smoke; installed host/device pending |
| MCP host configuration management | Settings → MCP Server | Independent identity; host configs untouched during QA |
| HTTP / WebSocket remote relay | `roku-engineer-studio-remote-server` | Compile / health / auth smoke; deployment pending |
| Cloud-emulator accounts / lifecycle / ports | `roku-engineer-studio-rce` | API/socket fixtures retained; real account pending |
| Privacy mode / encrypted passwords / preferences | Device Lab settings | Included; OS-specific acceptance pending |
| Six device-lab languages | `shared/strings/` | Included; new workspace is English |
| Crash-report redaction | Main crash modules | Included; links target this repository |
| Windows / macOS / Linux build targets | App package scripts | Local Windows build checked separately; signing external |

See [validation.md](validation.md) for run results and remaining gates. Source provenance and license notices are maintained separately in `third_party/`.

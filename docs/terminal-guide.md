# 🚀 Roku Engineer — AI-Powered Roku Channel Builder

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Claude Sonnet 4.6](https://img.shields.io/badge/AI-Claude%20Sonnet%205.5-orange.svg)](https://www.anthropic.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Roku OS 14/15/16](https://img.shields.io/badge/Roku%20OS-14%2F15%2F16-purple.svg)](https://developer.roku.com/)
[![SGDEX](https://img.shields.io/badge/SGDEX-Supported-green.svg)](https://developer.roku.com/docs/developer-program/libraries/sgdex/sgdex-guide.md)

> **Yuki** — Your AI-powered Roku development companion. Built with Claude Sonnet 5.5 and tuned for modern Roku OS 14/15/16, SGDEX, and certification-ready channel production.

---

## 🌟 Overview

Roku Engineer transforms the Roku channel development experience. Instead of navigating boilerplate, certification docs, and architecture patterns manually, you describe what you want — Yuki builds it.

From a basic SceneGraph app to a full **SVOD/AVOD channel** with deep linking, content feed integration, and pre-roll ads, Roku Engineer handles the heavy lifting — and can talk to your Roku device directly to pull logs, screenshots, and performance stats.

---

## ✨ What's New in v2.1

| Feature | Description |
|---|---|
| 🧠 **roAppMemoryMonitor Integration** | Mandatory for certification as of **Oct 1, 2026** — new projects and the `generate_memory_monitor` tool wire up OS 15.2+ low-memory threshold alerts (80/85/90/95%) with a `roDeviceInfo` fallback |
| 🔌 **WebSockets (OS 16.0)** | `generate_websocket_handler` scaffolds an `roWebSocket` Task for bi-directional server communication |
| 📡 **Server-Sent Events (OS 16.0)** | `generate_sse_handler` scaffolds a Task consuming `roUrlTransfer.AsyncGetSSEvents()` / `roSSEvent` streams |
| 🎨 **SceneGraph Effect Node (OS 16.0)** | GPU-accelerated rounded corners, borders, and gradients on Poster/Rectangle nodes via the new `Effect` component template |
| 💳 **Roku Pay Integration** | `generate_roku_pay_integration` generates ChannelStore entitlement checks, catalog browsing, purchase flows, and the OS 16.0 `GetRokuCustomerId` command |
| 📺 **Device Interaction** | ECP device-info queries, `chanperf` performance stats (with OS 15.2+ `<proc-stat>` raw Linux CPU stats), debug console log capture (telnet 8085), and developer-mode screenshots |
| 🗂️ **Content Feed Validation** | `validate_content_feed` checks Direct Publisher JSON feeds against the published schema (HTTPS URLs, `videoType` values, ISO 8601 dates) |
| 🛡️ **Updated Static Analysis** | Project validation now detects the in-app ECP prohibition (automatic publishing blocker) and missing memory-monitor integrations |
| 🏗️ **SGDEX Project Type** | Scaffold complete `GridView`, `DetailsView`, `MediaView` channels out of the box |
| 🔗 **Deep Link Handler** | Auto-generate certification-required `contentId` / `mediaType` routing (launch args **and** runtime `roInput` events) |
| 📡 **Content Feed Handler** | HTTP Task nodes that parse JSON or MRSS into `ContentNode` trees |
| 📢 **RAF Integration** | Scaffolds Roku Advertising Framework tasks for pre/mid/post-roll ads |
| 📂 **Manifest Support** | Full `manifest` file creation — no longer blocked by extension filters |
| 🧱 **Module-Level Templates** | All SceneGraph & BrightScript templates are now accessible from any tool |

---

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Windows, macOS, or Linux
- Internet connection for AI and search features

### Quick Setup

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd Roku-Engineer
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**

   Copy `example.env` to `.env` and fill in your keys:

   ```env
   # Required
   ANTHROPIC_API_KEY=your_claude_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here

   # Optional: Text-to-Speech (ElevenLabs)
   ELEVEN_LABS_API_KEY=your_elevenlabs_api_key_here
   VOICE_ID=your_preferred_voice_id
   MODEL_ID=eleven_monolingual_v1

   # AI Model Overrides (Optional)
   MAINMODEL=claude-sonnet-5-5
   TOOLCHECKERMODEL=claude-sonnet-5-5
   CODEEDITORMODEL=claude-sonnet-5-5
   CODEEXECUTIONMODEL=claude-sonnet-5-5
   ```

4. **Launch**

   ```bash
   python roku_engineer.py
   ```

---

## 🚀 Quick Start

### Create Your First Channel

```
You: Create a new SGDEX video streaming channel called "StreamFlow"
```

Yuki will:
- Scaffold a full project directory with `components/`, `source/`, `images/`, `locale/`
- Generate a `manifest` with all required certification fields
- Create a `GridView` MainScene using SGDEX
- Wire up `Main.brs` with a proper message loop
- Generate a `ContentFeedTask` to load and parse your JSON feed
- Include the certification-mandatory `roAppMemoryMonitor` integration and deep link handling

### More Examples

```
You: Add deep linking support so my channel can launch to specific content

You: Integrate Roku ads with pre-roll before each video

You: Create an authentication screen for my SVOD channel

You: Add Roku Pay subscription support with entitlement checks

You: Add a WebSocket connection for real-time entitlement updates

You: Stream live notifications from my backend using Server-Sent Events

You: Add rounded corners and gradient borders to my grid posters

You: Set up low-memory monitoring required for certification

You: Review my BrightScript for back-button handling issues

You: Validate my content feed before I submit it to Roku

You: Pull the debug logs from my Roku device at 192.168.1.42
```

---

## 🎯 Core Capabilities

### 🏗️ Project Types

| Type | Description |
|---|---|
| `basic` | Standard SceneGraph Scene with BrightScript main loop |
| `sgdex` | SGDEX GridView as MainScene, wired for content feeds |
| `grid` | Custom RowList/grid layout with item navigation |

```
You: Create a basic Roku channel for a screensaver app
You: Create an sgdex channel for a VOD streaming service
```

### 🔗 Deep Linking (Certification Required)

Generates `deeplinkUtils.brs` in `source/` with the proper `contentId` + `mediaType` parsing pattern required for Roku Channel Store certification.

```
You: Generate a deep link handler for my project
```

### 📡 Content Feed Integration

Creates a `ContentFeedTask` component that:
- Issues authenticated HTTP requests via `roUrlTransfer`
- Parses JSON **or** XML/MRSS payloads
- Populates a `ContentNode` tree compatible with SGDEX `GridView`

```
You: Generate a JSON content feed handler for my streaming channel
```

### 📢 Roku Advertising Framework (RAF)

Scaffolds a `RafTask.brs` component using the `Roku_Ads` library with:
- `adUrl` field for dynamic ad tag injection
- Standard ad rendering loop
- Output signaling for post-ad continuation

```
You: Add RAF ad integration to my channel
```

### 🧠 Memory Monitoring (Certification Required)

As of **October 1, 2026**, every published app must integrate `roAppMemoryMonitor` — Static Analysis errors block publishing otherwise. The `generate_memory_monitor` tool creates `source/MemoryMonitor.brs` with:
- `EnableMemoryWarningEvent()` subscription and `roAppMemoryNotificationEvent` handling (OS 15.2+ threshold alerts at 80/85/90/95% of the app memory limit)
- Full coverage stats: `GetMemoryLimitPercent()`, `GetChannelAvailableMemory()`, `GetChannelMemoryLimit()`
- `roDeviceInfo.EnableLowGeneralMemoryEvent()` fallback for devices without `roAppMemoryMonitor`

```
You: Add the memory monitor integration required for certification
```

### 🔌 Real-Time Communication (Roku OS 16.0+)

- **`generate_websocket_handler`** creates a `WebSocketTask` component using the `roWebSocket` component for bi-directional server communication (live entitlements, real-time UI updates, analytics streaming)
- **`generate_sse_handler`** creates an `SSEEventsTask` consuming Server-Sent Events via `roUrlTransfer.AsyncGetSSEvents()` and `roSSEvent` messages

```
You: Add a WebSocket connection to my entitlement backend
You: Stream live notifications from my server with SSE
```

### 🎨 SceneGraph Effect Node (Roku OS 16.0+)

The new `Effect` component template generates GPU-accelerated shader effects for Poster and Rectangle nodes — rounded corners (`borderRadius`), borders (`borderWidth`/`borderColor`), and linear/radial gradients — with a `supported` check for shader-less platforms.

```
You: Add rounded corners with a purple gradient to my grid posters
```

### 💳 Roku Pay (SVOD/TVOD)

`generate_roku_pay_integration` creates `source/RokuPay.brs` with:
- Entitlement checks on every launch and resume (`getPurchases`) — certification-required for SVOD/TVOD channels
- Catalog browsing (`doBrowse`) and purchase flows (`doOrder`)
- The OS 16.0+ `GetRokuCustomerId` command for user identification without a prior purchase

```
You: Add Roku Pay subscription support with entitlement checks
```

### 📺 Device Interaction (Developer Mode)

| Tool | What it does |
|---|---|
| `get_roku_device_info` | Queries device info over ECP (model, firmware, capabilities) |
| `check_device_performance` | Pulls `chanperf` stats — includes the OS 15.2+ `<proc-stat>` raw Linux CPU/process field |
| `capture_device_logs` | Captures BrightScript debug console output (telnet port 8085) |
| `capture_device_screenshot` | Saves an on-screen screenshot from the device |

```
You: Connect to my Roku at 192.168.1.42 and capture 30 seconds of logs
```

---

## 📋 Roku OS 14/15/16 Standards

### Certification Checklist

- ✅ Extensionless `manifest` with all required fields
- ✅ **`roAppMemoryMonitor` integration (mandatory as of October 1, 2026)** — `EnableMemoryWarningEvent()` + `roAppMemoryNotificationEvent` handling, or Static Analysis blocks publishing
- ✅ **No in-app ECP commands** — apps issuing ECP requests are automatically blocked from the Streaming Store
- ✅ Back-button navigation compliance (`roSGScreenEvent.isScreenClosed()`)
- ✅ Deep linking (`contentId` / `mediaType` / `mediaStartTime`) at launch **and** at runtime via `roInput`
- ✅ Roku Pay entitlement check on every launch and resume (SVOD/TVOD)
- ✅ Accessibility compliance (screen reader support via `accessibleText`, closed captions)
- ✅ Performance benchmarks (startup < 3s, memory < 100MB base)
- ✅ HDR support detection (`roDeviceInfo.SupportsVideoMode`)
- ✅ Closed captions enabled by default (`GlobalCaptionMode`)
- ✅ RAF ad integration structure
- ✅ Secure HTTPS with `SetCertificatesFile("common:/certs/ca-bundle.crt")`

### Latest Platform Features

| Roku OS | Feature Highlights |
|---|---|
| **OS 16.0** (dev beta) | `roWebSocket` connections, Server-Sent Events (`AsyncGetSSEvents`/`roSSEvent`), SceneGraph `Effect` node (GPU rounded corners/borders/gradients), `FloatArrayFieldInterpolator`, `ChannelStore.GetRokuCustomerId`, relaxed conditional compilation, `roTextureRequest.SetDrawable()` |
| **OS 15.2** | Low-memory threshold events (80/85/90/95% of app limit), Perfetto BrightScript heap graph, `chanperf` `<proc-stat>` raw Linux CPU stats, Debug Protocol virtual variables, AES-GCM in `roEVPCipher`, remote repeat delay/rate APIs |
| **OS 15.0/15.1** | Data transfer & reference-handling APIs, `roArray.ifArraySizeInfo`, `GetUptimeMillisecondsAsLong`, HLS manifest seek mode, Perfetto app tracing |

---

## 🎛️ Interface Modes

### 💬 Text Mode (Default)

Rich terminal interface with syntax highlighting, panels, and progress tracking.

### 🗣️ Voice Mode

Hands-free development with speech recognition and ElevenLabs TTS.

```
You: Enable voice mode
```

### 🤖 Automode

Autonomous multi-step execution for complex workflows.

```
You: Automode: Build a complete AVOD channel with grid navigation, deep linking, and RAF ads
```

---

## 🛠️ Full Tool Reference

| Tool | Description |
|---|---|
| `create_folders` | Create nested directory structures |
| `create_files` | Generate files — including `manifest`, `.png`, `.txt` |
| `edit_and_apply_multiple` | AI-powered multi-file refactoring |
| `read_multiple_files` | Batch file reading with wildcard support |
| `list_files` | Directory listing |
| `scan_folder` | Full project scan into Markdown documentation |
| `tavily_search` | Real-time Roku SDK and developer info search |
| `run_shell_command` | Execute system commands safely |
| `create_roku_project` | Generate full project scaffolds (`basic`, `sgdex`, `grid`) with memory monitor + deep links built in |
| `create_roku_component` | Create typed SceneGraph + BrightScript component pairs (incl. `Effect`, `WebSocketTask`) |
| `generate_deep_link_handler` | Certification-ready deep link routing utilities (launch args + `roInput`) |
| `generate_content_feed_handler` | JSON/MRSS → ContentNode HTTP Task scaffolding |
| `generate_raf_integration` | Roku Advertising Framework Task boilerplate |
| `generate_memory_monitor` | `roAppMemoryMonitor` low-memory event integration (certification-mandatory) |
| `generate_websocket_handler` | `roWebSocket` bi-directional communication Task (OS 16.0+) |
| `generate_sse_handler` | Server-Sent Events consumer Task (OS 16.0+) |
| `generate_roku_pay_integration` | ChannelStore entitlement/purchase flows for SVOD/TVOD |
| `validate_content_feed` | Direct Publisher JSON feed schema validation |
| `get_roku_device_info` | ECP `query/device-info` device details |
| `check_device_performance` | ECP `query/chanperf` stats with OS 15.2+ `<proc-stat>` |
| `capture_device_screenshot` | Developer-mode screenshot capture |
| `capture_device_logs` | Debug console log capture (telnet 8085) |
| `package_roku_app` | Package channel into deployment-ready `.zip` |
| `create_modern_manifest` | Certification-complete `manifest` generation |
| `generate_component_registry` | Document all SceneGraph components in a project |
| `validate_roku_project` | Full certification-level project validation |
| `validate_roku_component` / `validate_scenegraph_component` | Component XML structure + accessibility validation |
| `validate_roku_manifest` | Manifest field validation |
| `lint_brightscript` | BrightScript static analysis (incl. ECP prohibition + memory monitor checks) |
| `create_accessibility_helpers` / `create_performance_monitoring` | Accessibility and performance helper code generation |

---

## 📊 Performance & Configuration

### Environment Variables

```env
ANTHROPIC_API_KEY=         # Required — Claude AI
TAVILY_API_KEY=            # Required — Web research
ELEVEN_LABS_API_KEY=       # Optional — Voice TTS
VOICE_ID=                  # Optional — ElevenLabs voice
MAINMODEL=claude-sonnet-5-5
MAX_CONTEXT_TOKENS=1000000  # 1M token context window
MAX_CONTINUATION_ITERATIONS=25
THINKING_EFFORT=high          # high (default) | medium | low
```

### Token Management

- Real-time token usage tracking per session
- Per-model cost monitoring
- Intelligent caching for large project contexts

---

## 🔐 Security & Privacy

- All file operations run locally
- API keys are loaded exclusively from `.env`
- No persistent session data is stored remotely
- Secure HTTPS enforced in all generated Roku network code

---

## 📖 Resources

- 📘 [User Guide](userguide.md) — Detailed usage walkthrough
- 🧑‍💻 [Roku Developer Docs](https://developer.roku.com/docs)
- 📺 [SGDEX GitHub](https://github.com/rokudev/SceneGraphDeveloperExtensions)
- 🔖 [Roku Certification Checklist](https://developer.roku.com/docs/developer-program/certification/certification.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Submit a pull request

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for the Roku developer community**

*Empowering developers to build amazing, certified Roku channels — faster.*

</div>

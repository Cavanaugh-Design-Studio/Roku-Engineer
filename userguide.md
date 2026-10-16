# 📚 Roku Engineer User Guide

**Complete guide to using the AI-powered Roku development assistant**

---

## 📋 Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Core Features](#core-features)
4. [Project Management](#project-management)
5. [Development Workflow](#development-workflow)
6. [Advanced Features](#advanced-features)
7. [Voice Interface](#voice-interface)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [Examples & Tutorials](#examples--tutorials)

---

## 🚀 Getting Started

### First Time Setup

1. **Install Prerequisites**

   ```bash
   # Ensure Python 3.8+ is installed
   python --version
   
   # Install required packages
   pip install -r requirements.txt
   ```

2. **Configure API Keys**

   Create a `.env` file in the project root:

   ```env
   # Required Keys
   ANTHROPIC_API_KEY=your_claude_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   
   # Optional: Voice Features
   ELEVEN_LABS_API_KEY=your_elevenlabs_key
   VOICE_ID=your_voice_id
   ```

3. **Launch the Application**

   ```bash
   python roku_engineer.py
   ```

### Understanding the AI Assistant

**Meet Yuki** - Your AI development companion:

- **Personality**: Expert Roku developer with deep BrightScript knowledge
- **Capabilities**: Project creation, code review, debugging, research, device interaction
- **Specialization**: Modern Roku OS 14/15/16 standards and certification
- **Communication**: Natural conversation with technical expertise

---

## 🖥️ Interface Overview

### Main Interface Elements

```
┌─────────────────────────────────────────────────────────────┐
│ 🚀 Roku Engineer - AI Development Assistant                │
├─────────────────────────────────────────────────────────────┤
│ [Voice: OFF] [Automode: OFF] [Tokens: 1,234]              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Yuki: Hello! I'm ready to help with your Roku project.     │
│                                                             │
│ You: _                                                      │
└─────────────────────────────────────────────────────────────┘
```

### Status Indicators

- **🟢 Green**: Success, completed operations
- **🟡 Yellow**: In progress, warnings
- **🔴 Red**: Errors, failed operations
- **🔵 Blue**: Information, guidance

### Command Types

1. **Direct Commands**: Specific requests (`create project`, `review code`)
2. **Conversational**: Natural language questions
3. **Voice Commands**: Spoken instructions (when voice mode enabled)
4. **System Commands**: Mode changes (`automode`, `voice mode`)

---

## 🎯 Core Features

### 1. Project Creation

**Create New Roku Channel**

```text
You: Create a new streaming video channel called "MovieStream"

Yuki: I'll create a complete Roku channel structure for MovieStream...
```

**What Happens:**

- Project folder structure created
- Manifest file with Roku OS 14/15/16 standards
- Main.brs entry point with memory monitoring and deep link handling
- SceneGraph components
- Accessibility compliance setup

### 2. Code Development

**Generate BrightScript Code**

```text
You: Create a video player component with HDR support

Yuki: I'll create a modern video player component with HDR capabilities...
```

**Features:**

- Modern BrightScript syntax
- SceneGraph XML components
- Performance optimization
- Error handling
- Accessibility support

### 3. Code Review & Analysis

**Review Existing Code**

```text
You: Review my main.brs file for performance issues

Yuki: I'll analyze your main.brs file for optimization opportunities...
```

**Analysis Includes:**

- Performance bottlenecks
- Memory usage optimization
- Coding standard compliance
- Security considerations
- Accessibility improvements

### 4. Research & Documentation

**Get Latest Information**

```text
You: What are the latest Roku SDK updates for 2026?

Yuki: Let me search for the latest Roku SDK information...
```

**Research Capabilities:**

- Real-time web search
- Official documentation access
- Best practice guidance
- Industry trend analysis

---

## 📁 Project Management

### Project Structure Creation

**Standard Roku Channel Structure:**

```
MyRokuChannel/
├── manifest                          # Channel configuration
├── source/
│   ├── main.brs                     # Entry point (memory monitor + deep links)
│   ├── deeplinkUtils.brs            # Deep link routing (certification required)
│   ├── MemoryMonitor.brs            # roAppMemoryMonitor integration (required)
│   ├── Utils.brs                    # Utility functions
│   └── API/
│       └── ContentAPI.brs           # Content management
├── components/
│   ├── MainScene/MainScene.xml/.brs # Main scene
│   ├── VideoPlayer/VideoPlayer.xml/.brs # Video player
│   └── GridScreen/GridScreen.xml/.brs  # Grid layout
├── images/
│   ├── splash_hd.jpg                # Splash screens
│   ├── splash_sd.jpg
│   ├── mm_icon_focus_hd.png          # Channel icons
│   └── mm_icon_focus_sd.png
└── locale/
    └── en_US/
        └── translations.ts          # Localization (TS/XLIFF format)
```

### Manifest Configuration

**Modern Manifest Features:**

```ini
title=My Roku Channel
major_version=1
minor_version=0
build_version=001

# Assets (pkg:/ paths required)
mm_icon_focus_hd=pkg:/images/mm_icon_focus_hd.png
mm_icon_focus_sd=pkg:/images/mm_icon_focus_sd.png
splash_screen_hd=pkg:/images/splash_hd.jpg
splash_screen_sd=pkg:/images/splash_sd.jpg

# Resolution + splash behavior
ui_resolutions=fhd
splash_color=#000000
splash_min_time=1500

# Launch behavior
supports_input_launch=1
```

**Additional fields you may need** (generate them with `create_modern_manifest` or ask Yuki): `supported_locales`, `channel_genre`, `parental_rating`, `content_rating`, `privacy_policy`, `terms_of_service`, `screensaver_title`, `channel_store_description`.

### File Operations

**Reading Files:**

```text
You: Read my MainScene.xml file

Yuki: I'll examine your MainScene.xml file...
```

**Editing Files:**

```text
You: Add voice remote support to my video player

Yuki: I'll modify your video player to include voice remote capabilities...
```

**Creating Files:**

```text
You: Create a settings screen component

Yuki: I'll create a modern settings screen component...
```

---

## 🔄 Development Workflow

### 1. Project Initialization

```text
Step 1: You: "Create a new channel for cooking videos"
Step 2: Yuki creates project structure
Step 3: You: "Add a recipe browsing interface"
Step 4: Yuki implements grid-based recipe browser
Step 5: You: "Integrate with my recipe API"
Step 6: Yuki creates API integration code
```

### 2. Iterative Development

**Code → Review → Improve Cycle:**

1. **Write Code**: Generate initial implementation
2. **Review**: Analyze for improvements
3. **Optimize**: Apply performance enhancements
4. **Test**: Validate functionality
5. **Refine**: Make final adjustments

### 3. Quality Assurance

**Automated Checks:**

- Code syntax validation
- Performance analysis
- Accessibility compliance
- Certification requirement verification (including the mandatory `roAppMemoryMonitor` integration and the in-app ECP command prohibition)

### 4. Deployment Preparation

**Channel Store Readiness:**

- Manifest validation
- Asset verification
- Performance benchmarks
- Accessibility testing
- Memory monitor integration confirmed

---

## 🚀 Advanced Features

### Automode Operation

**Enable Autonomous Development:**

```text
You: Automode: Create a complete news channel with categories and video playback

Yuki: Entering automode to create a comprehensive news channel...
[Automode Active - Goal 1/5: Project structure creation]
[Automode Active - Goal 2/5: Category navigation setup]
[Automode Active - Goal 3/5: Video player implementation]
[Automode Active - Goal 4/5: News feed integration]
[Automode Active - Goal 5/5: Testing and optimization]
AUTOMODE_COMPLETE
```

**Automode Capabilities:**

- Multi-step project execution
- Autonomous problem solving
- Progress tracking
- Error recovery
- Goal completion reporting

### Advanced Code Editing

**Multi-file Operations:**

```text
You: Update all my components to support the new Roku OS 14 features

Yuki: I'll update all components for Roku OS 14 compatibility...
[Processing: MainScene.xml]
[Processing: VideoPlayer.xml]
[Processing: GridScreen.xml]
[Processing: SettingsScreen.xml]
All components updated successfully!
```

**Intelligent Code Analysis:**

- Pattern recognition
- Dependency tracking
- Impact analysis
- Refactoring suggestions

### Performance Optimization

**Memory Management:**

```text
You: Optimize my channel for memory usage

Yuki: I'll analyze and optimize memory usage patterns...
```

**Startup Time Optimization:**

```text
You: My channel takes too long to start

Yuki: I'll identify and fix startup performance issues...
```

### Modern Roku OS 15/16 Features

**Memory Monitoring (Certification Required)**

Starting **October 1, 2026**, every published app must integrate `roAppMemoryMonitor` — apps without it fail Static Analysis and can't be published.

```text
You: Set up the memory monitor integration my channel needs for certification

Yuki: I'll generate source/MemoryMonitor.brs using roAppMemoryMonitor with the
OS 15.2+ threshold alerts (80/85/90/95% of your app memory limit) and wire it
into your main message loop...
```

**Real-Time Communication (Roku OS 16.0+)**

```text
You: Add a WebSocket connection to wss://api.mychannel.com for live entitlements

Yuki: I'll generate a WebSocketTask using the OS 16.0 roWebSocket API...

You: My backend pushes notifications over Server-Sent Events

Yuki: I'll generate an SSEEventsTask using roUrlTransfer.AsyncGetSSEvents()...
```

**GPU-Accelerated Effects (Roku OS 16.0+)**

```text
You: Add rounded corners with a gradient border to my grid posters

Yuki: I'll create an Effect node (OS 16.0+) with borderRadius and gradient
colors applied to your Poster nodes, with a supported check for older boxes...
```

**Roku Pay (SVOD/TVOD Channels)**

```text
You: Add subscription support with automatic entitlement checks

Yuki: I'll generate source/RokuPay.brs with ChannelStore entitlement checks
on every launch and resume, catalog browsing, and purchase flows...
```

### Working With a Roku Device

Connect Yuki to a device in developer mode to inspect logs and performance directly:

| Request | What Yuki uses |
|---|---|
| "Get the device info for 192.168.1.42" | ECP `query/device-info` |
| "Check my channel's performance on the device" | ECP `query/chanperf` (with OS 15.2+ `<proc-stat>` raw Linux stats) |
| "Capture 30 seconds of debug logs" | Debug console (telnet 8085) |
| "Take a screenshot of my channel" | Developer-mode screenshot via HTTP digest auth |

```text
You: My channel crashes on launch. The device is at 192.168.1.42 — can you grab the logs?

Yuki: I'll connect to the debug console on port 8085 and capture the startup
logs to find the crash...
```

**Before using device tools:** enable developer mode on the device (Home×3, Up×2, Right, Left, Right, Left, Right), set a developer password, and have the device IP handy (Settings > Network > About).

---

## 🗣️ Voice Interface

### Enabling Voice Mode

```text
You: Enable voice mode
Yuki: Voice mode activated. I'm listening...
[🎤 Voice Mode Active]

You: (Speaking) "Create a video grid component"
Yuki: I'll create a video grid component for you...
```

### Voice Commands

**Navigation Commands:**

- "Show main menu"
- "Go back"
- "Save current work"
- "Exit voice mode"

**Development Commands:**

- "Create new component"
- "Review current file"
- "Run code analysis"
- "Search for documentation"

**Project Commands:**

- "Build project structure"
- "Validate manifest"
- "Check certification requirements"

### Text-to-Speech

**When Enabled:**

- AI responses are spoken aloud
- Code explanations are narrated
- Error messages are vocalized
- Progress updates are announced

---

## 🛠️ Troubleshooting

### Common Issues

**1. API Key Problems**

```
Error: ANTHROPIC_API_KEY not found
Solution: Add API key to .env file
```

**2. Voice Recognition Issues**

```
Error: No speech detected
Solutions:
- Check microphone permissions
- Adjust for ambient noise
- Speak clearly and wait for prompt
```

**3. File Access Problems**

```
Error: Cannot read file
Solutions:
- Check file permissions
- Verify file path
- Ensure file exists
```

**4. Code Generation Issues**

```
Error: No edit instructions generated
Solutions:
- Provide more specific requirements
- Check project context
- Verify file content accessibility
```

### Debug Mode

**Enable Detailed Logging:**

```text
You: Enable debug mode

Yuki: Debug mode enabled. Detailed logging active.
```

**Debug Information:**

- Token usage tracking
- API call details
- File operation logs
- Error stack traces

### Recovery Procedures

**1. Reset Conversation**

```text
You: Reset conversation

Yuki: Conversation history cleared. Starting fresh.
```

**2. Reload File Contents**

```text
You: Reload all files

Yuki: Reloading all project files...
```

**3. Clear Cache**

```text
You: Clear cache

Yuki: Cache cleared. Memory freed.
```

---

## 📖 Best Practices

### Development Guidelines

**1. Project Organization**

- Use clear, descriptive file names
- Organize components logically
- Maintain consistent coding style
- Document complex functionality

**2. Performance Optimization**

- Minimize memory usage
- Optimize startup time
- Use efficient algorithms
- Implement proper cleanup

**3. Accessibility**

- Provide text alternatives
- Support voice navigation
- Implement high contrast mode
- Test with accessibility tools

**4. Certification Readiness**

- Follow Roku guidelines
- Test on multiple devices
- Validate all requirements
- Optimize for user experience

### AI Interaction Tips

**1. Be Specific**

✅ Good: "Create a video player with HDR support and accessibility features"
❌ Vague: "Make a video thing"

**2. Provide Context**

✅ Good: "Update my existing MainScene.xml to add voice remote support"
❌ Limited: "Add voice support"

**3. Iterative Refinement**

✅ Approach: Ask → Review → Refine → Perfect
❌ Avoid: Expecting perfection in one request

**4. Use Clear Language**

✅ Clear: "Implement a grid layout for movie categories"
❌ Ambiguous: "Add some grid stuff for movies"

---

## 🎓 Examples & Tutorials

### Tutorial 1: Simple Video Channel

**Step 1: Create Project**

```text
You: Create a basic video streaming channel called "SimpleStreamer"

Yuki: I'll create a basic video streaming channel structure...
```

**Step 2: Add Content Grid**

```text
You: Add a grid to display video categories

Yuki: I'll implement a category grid with modern design...
```

**Step 3: Implement Video Player**

```text
You: Create a video player component with HDR support

Yuki: I'll create an advanced video player with HDR capabilities...
```

### Tutorial 2: Advanced Features

**Voice Remote Integration**

```text
You: Add voice search to my channel

Yuki: I'll implement voice search functionality...
```

**Accessibility Enhancement**

```text
You: Make my channel fully accessible

Yuki: I'll enhance your channel for full accessibility compliance...
```

### Tutorial 3: Performance Optimization

**Memory Optimization**

```text
You: My channel uses too much memory

Yuki: I'll analyze and optimize memory usage...
```

**Startup Performance**

```text
You: Reduce channel startup time

Yuki: I'll optimize your channel's startup performance...
```

### Example Interactions

**Code Review Session**

```text
You: Review my VideoPlayer.brs for improvements

Yuki: I'll analyze your VideoPlayer.brs file...

Found optimization opportunities:
1. Memory leak in event handling
2. Inefficient video loading
3. Missing error handling

Would you like me to implement these fixes?

You: Yes, please fix all issues

Yuki: I'll apply all optimizations...
```

**Research Session**

```text
You: What are the new Roku certification requirements for 2026?

Yuki: Let me search for the latest 2026 certification requirements...

Based on current information:
1. roAppMemoryMonitor integration is now mandatory (as of October 1, 2026)
2. In-app ECP commands are prohibited - apps are blocked from publishing
3. Deep linking required at launch and at runtime for all content types
4. Roku Pay entitlement checks on every launch and resume (SVOD/TVOD)

Would you like details on any specific requirement?
```

---

## 📞 Support & Resources

### Getting Help

**Within the Application:**

```text
You: Help with voice commands

Yuki: Here are the available voice commands...
```

**External Resources:**

- [Official Roku Developer Documentation](https://developer.roku.com/)
- [BrightScript Documentation](https://developer.roku.com/docs/references/brightscript/language/brightscript-language-reference.md)
- [SceneGraph Framework](https://developer.roku.com/docs/developer-program/core-concepts/scenegraph/scenegraph-overview.md)

### Community

- GitHub Issues for bug reports
- Community discussions for best practices
- Feature requests and suggestions

---

**Happy Roku Development! 🚀**

*Let Yuki help you create amazing Roku channels with AI-powered assistance.*

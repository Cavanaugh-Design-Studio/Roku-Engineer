import os
import json
import asyncio
import base64
import io
import re
import difflib
import time
import datetime
import venv
import sys
import signal
import logging
import shutil
import subprocess
import zipfile
from typing import List, Tuple, Optional, Dict, Any, AsyncIterable

from dotenv import load_dotenv
from inquirer import Confirm
from sqlalchemy import Table
from tavily import TavilyClient
from PIL import Image
from anthropic import Anthropic, APIStatusError, APIError
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.console import Group
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
import glob
import speech_recognition as sr
import websockets
from pydub import AudioSegment
from pydub.playback import play
import mimetypes
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from system.system_prompt import BASE_SYSTEM_PROMPT, AUTOMODE_SYSTEM_PROMPT

# Configure logging
logging.basicConfig(
    level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file
load_dotenv()

# Constants
VOICE_COMMANDS = {
    "exit voice mode": "exit_voice_mode",
    "save chat": "save_chat",
    "reset conversation": "reset_conversation",
}
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")
MODEL_ID = os.getenv("MODEL_ID")
ROKU_FILE_EXTENSIONS = [
    ".brs",
    ".xml",
    ".bs",
    ".roku",
    ".zip",
    ".json",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
]
ROKU_TEXT_EXTENSIONS = [".brs", ".xml", ".bs", ".roku", ".json", ".md", ".txt"]
ROKU_COMPONENT_TYPES = [
    "Scene",
    "Group",
    "Rectangle",
    "Label",
    "Poster",
    "RowList",
    "Video",
    "Audio",
    "Animation",
    "Timer",
    "Task",
    "ContentNode",
    "ArrayGrid",
    "MarkupGrid",
    "PinPad",
    "Keyboard",
    "Dialog",
    "BusySpinner",
    "ProgressBar",
    "Slider",
    "CheckList",
    "RadioButtonList",
    "DatePicker",
]
ROKU_MANIFEST_REQUIRED_FIELDS = [
    "title",
    "major_version",
    "minor_version",
    "build_version",
    "mm_icon_focus_hd",
    "mm_icon_focus_sd",
    "splash_screen_hd",
    "splash_screen_sd",
    "ui_resolutions",
    "supported_locales",
    "channel_genre",
    "parental_rating",
    "supports_input_launch",
    "channel_store_description",
    "privacy_policy",
    "terms_of_service",
    "content_rating",
    "screensaver_title",
]
ROKU_OS_FEATURES = {
    "voice_remote_pro": True,
    "hdr_support": True,
    "dolby_vision": True,
    "dolby_atmos": True,
    "accessibility_features": True,
    "performance_monitoring": True,
    "enhanced_analytics": True,
    # Roku OS 15.2+
    "low_memory_threshold_events": True,  # roAppMemoryMonitor alerts at 80/85/90/95% of app limit
    "perfetto_heap_graph": True,  # BrightScript heap graph visualization in Perfetto
    "chanperf_proc_stat": True,  # ECP query/chanperf returns raw Linux CPU/process stats
    "debug_virtual_variables": True,  # roInputEvent/roUrlEvent/roDateTime in Debug Protocol
    "aes_gcm": True,  # roEVPCipher setTag()/getTag()
    "remote_repeat_settings": True,  # roDeviceInfo remote repeat delay/rate (EN 301 549)
    "ro_utils_has_component": True,
    # Roku OS 16.0 (developer beta)
    "websockets": True,  # roWebSocket bi-directional communication
    "server_sent_events": True,  # roUrlTransfer.AsyncGetSSEvents() + roSSEvent
    "effect_node": True,  # SceneGraph GPU-accelerated rounded corners/gradients/borders
    "float_array_field_interpolator": True,
    "roku_customer_id": True,  # ChannelStore GetRokuCustomerId command
}
ROKU_CERTIFICATION_REQUIREMENTS = {
    "accessibility_compliance": True,
    "performance_benchmarks": True,
    "memory_usage_limits": True,
    "startup_time_limits": True,
    "navigation_standards": True,
    # As of October 1, 2026, apps must integrate roAppMemoryMonitor or Static
    # Analysis blocks publishing.
    "memory_monitor_integration": True,
    # In-app ECP commands are prohibited - apps issuing ECP commands are
    # automatically blocked from the Streaming Store.
    "no_in_app_ecp_commands": True,
}
CONTINUATION_EXIT_PHRASE = "AUTOMODE_COMPLETE"
MAX_CONTINUATION_ITERATIONS = 25
MAX_CONTEXT_TOKENS = (
    1000000  # claude-sonnet5-5 supports 1M token context window (API beta)
)
MAINMODEL = os.getenv("MAINMODEL", "claude-sonnet-5-5")
TOOLCHECKERMODEL = os.getenv("TOOLCHECKERMODEL", "claude-sonnet-5-5")
CODEEDITORMODEL = os.getenv("CODEEDITORMODEL", "claude-sonnet-5-5")
CODEEXECUTIONMODEL = os.getenv("CODEEXECUTIONMODEL", "claude-sonnet-5-5")

# Adaptive thinking effort: "high" (default, always thinks), "medium", "low" (skip simple tasks)
# See: https://docs.anthropic.com/en/build-with-claude/adaptive-thinking
THINKING_EFFORT = os.getenv("THINKING_EFFORT", "high")  # high | medium | low

# Models that support adaptive thinking (claude-sonnet-5-5, claude-opus-5-5)
ADAPTIVE_THINKING_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}


def get_thinking_params(model: str, effort: str = None) -> dict:
    """
    Returns adaptive thinking kwargs for client.messages.create() if the model
    supports it, otherwise returns an empty dict (no thinking).

    effort levels:
        "high"   — Claude always thinks (default, best for agentic Roku workflows)
        "medium" — Claude may skip thinking on simple queries
        "low"    — Minimize thinking, optimise for speed

    Usage:
        response = client.messages.create(
            model=MAINMODEL,
            max_tokens=8000,
            **get_thinking_params(MAINMODEL),
            ...
        )
    """
    if model not in ADAPTIVE_THINKING_MODELS:
        return {}
    level = effort or THINKING_EFFORT
    return {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": level},
    }


# Global variables
recognizer = None
microphone = None
tts_enabled = True
use_tts = False
conversation_history = []
file_contents = {}
code_editor_memory = []
code_editor_files = set()
automode = False
running_processes = {}
main_model_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
tool_checker_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
code_editor_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
code_execution_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
USE_FUZZY_SEARCH = True

# Initialize clients
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

console = Console()


def is_installed(lib_name):
    return shutil.which(lib_name) is not None


async def text_chunker(text: str) -> AsyncIterable[str]:
    """Split text into chunks, ensuring to not break sentences."""
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""

    for char in text:
        if buffer.endswith(splitters):
            yield buffer + " "
            buffer = char
        elif char in splitters:
            yield buffer + char + " "
            buffer = ""
        else:
            buffer += char

    if buffer:
        yield buffer + " "


async def stream_audio(audio_stream):
    """Stream audio data using mpv player."""
    if not is_installed("mpv"):
        console.print(
            "mpv not found. Installing alternative audio playback...",
            style="bold yellow",
        )
        # Fall back to pydub playback if mpv is not available
        audio_data = b"".join([chunk async for chunk in audio_stream])
        audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
        play(audio)
        return

    mpv_process = subprocess.Popen(
        ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    console.print("Started streaming audio", style="bold green")
    try:
        async for chunk in audio_stream:
            if chunk:
                mpv_process.stdin.write(chunk)
                mpv_process.stdin.flush()
    except Exception as e:
        console.print(f"Error during audio streaming: {str(e)}", style="bold red")
    finally:
        if mpv_process.stdin:
            mpv_process.stdin.close()
        mpv_process.wait()


async def text_to_speech(text):
    if not ELEVEN_LABS_API_KEY:
        console.print(
            "ElevenLabs API key not found. Text-to-speech is disabled.",
            style="bold yellow",
        )
        console.print(text)
        return

    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}"

    try:
        async with websockets.connect(
            uri, extra_headers={"xi-api-key": ELEVEN_LABS_API_KEY}
        ) as websocket:
            # Send initial message
            await websocket.send(
                json.dumps(
                    {
                        "text": " ",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                        "xi_api_key": ELEVEN_LABS_API_KEY,
                    }
                )
            )

            # Set up listener for audio chunks
            async def listen():
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if data.get("audio"):
                            yield base64.b64decode(data["audio"])
                        elif data.get("isFinal"):
                            break
                    except websockets.exceptions.ConnectionClosed:
                        logging.error("WebSocket connection closed unexpectedly")
                        break
                    except Exception as e:
                        logging.error(f"Error processing audio message: {str(e)}")
                        break

            # Start audio streaming task
            stream_task = asyncio.create_task(stream_audio(listen()))

            # Send text in chunks
            async for chunk in text_chunker(text):
                try:
                    await websocket.send(
                        json.dumps({"text": chunk, "try_trigger_generation": True})
                    )
                except Exception as e:
                    logging.error(f"Error sending text chunk: {str(e)}")
                    break

            # Send closing message
            await websocket.send(json.dumps({"text": ""}))

            # Wait for streaming to complete
            await stream_task

    except websockets.exceptions.InvalidStatusCode as e:
        logging.error(f"Failed to connect to ElevenLabs API: {e}")
        console.print(f"Failed to connect to ElevenLabs API: {e}", style="bold red")
        console.print("Fallback: Printing the text instead.", style="bold yellow")
        console.print(text)
    except Exception as e:
        logging.error(f"Error in text-to-speech: {str(e)}")
        console.print(f"Error in text-to-speech: {str(e)}", style="bold red")
        console.print("Fallback: Printing the text instead.", style="bold yellow")
        console.print(text)


def initialize_speech_recognition():
    global recognizer, microphone
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    # Adjust for ambient noise
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

    logging.info("Speech recognition initialized")


async def voice_input(max_retries=3):
    global recognizer, microphone

    for attempt in range(max_retries):
        # Reinitialize speech recognition objects before each attempt
        initialize_speech_recognition()

        try:
            with microphone as source:
                console.print("Listening... Speak now.", style="bold green")
                audio = recognizer.listen(source, timeout=5)

            console.print("Processing speech...", style="bold yellow")
            text = recognizer.recognize_google(audio)
            console.print(f"You said: {text}", style="cyan")
            return text.lower()
        except sr.WaitTimeoutError:
            console.print(
                f"No speech detected. Attempt {attempt + 1} of {max_retries}.",
                style="bold red",
            )
            logging.warning(
                f"No speech detected. Attempt {attempt + 1} of {max_retries}"
            )
        except sr.UnknownValueError:
            console.print(
                f"Speech was unintelligible. Attempt {attempt + 1} of {max_retries}.",
                style="bold red",
            )
            logging.warning(
                f"Speech was unintelligible. Attempt {attempt + 1} of {max_retries}"
            )
        except sr.RequestError as e:
            console.print(
                f"Could not request results from speech recognition service; {e}",
                style="bold red",
            )
            logging.error(
                f"Could not request results from speech recognition service; {e}"
            )
            return None
        except Exception as e:
            console.print(
                f"Unexpected error in voice input: {str(e)}", style="bold red"
            )
            logging.error(f"Unexpected error in voice input: {str(e)}")
            return None

        # Add a short delay between attempts
        await asyncio.sleep(1)

    console.print(
        "Max retries reached. Returning to text input mode.", style="bold red"
    )
    logging.info("Max retries reached in voice input. Returning to text input mode.")
    return None


def cleanup_speech_recognition():
    global recognizer, microphone
    recognizer = None
    microphone = None
    logging.info("Speech recognition objects cleaned up")


def process_voice_command(command):
    if command in VOICE_COMMANDS:
        action = VOICE_COMMANDS[command]
        if action == "exit_voice_mode":
            return False, "Exiting voice mode."
        elif action == "save_chat":
            filename = save_chat()
            return True, f"Chat saved to {filename}"
        elif action == "reset_conversation":
            reset_conversation()
            return True, "Conversation has been reset."
    return True, None


async def get_user_input(prompt="You: "):
    style = Style.from_dict(
        {
            "prompt": "cyan bold",
        }
    )
    session = PromptSession(style=style)
    return await session.prompt_async(prompt, multiline=False)


def setup_virtual_environment() -> Tuple[str, str]:
    venv_name = "code_execution_env"
    venv_path = os.path.join(os.getcwd(), venv_name)
    try:
        if not os.path.exists(venv_path):
            venv.create(venv_path, with_pip=True)

        # Activate the virtual environment
        if sys.platform == "win32":
            activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
        else:
            activate_script = os.path.join(venv_path, "bin", "activate")

        return venv_path, activate_script
    except Exception as e:
        logging.error(f"Error setting up virtual environment: {str(e)}")
        raise


def update_system_prompt(
    current_iteration: Optional[int] = None, max_iterations: Optional[int] = None
) -> str:
    global file_contents
    chain_of_thought_prompt = """
    Answer the user's request using relevant tools (if they are available). Before calling a tool, do some analysis within <thinking></thinking> tags. First, think about which of the provided tools is the relevant tool to answer the user's request. Second, go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. If all of the required parameters are present or can be reasonably inferred, close the thinking tag and proceed with the tool call. BUT, if one of the values for a required parameter is missing, DO NOT invoke the function (not even with fillers for the missing params) and instead, ask the user to provide the missing parameters. DO NOT ask for more information on optional parameters if it is not provided.

    Do not reflect on the quality of the returned search results in your response.

    IMPORTANT: Before using the read_multiple_files tool, always check if the files you need are already in your context (system prompt).
    If the file contents are already available to you, use that information directly instead of calling the read_multiple_files tool.
    Only use the read_multiple_files tool for files that are not already in your context.

    When instructing to read a file, always use the full file path.
    """

    files_in_context = "\n".join(file_contents.keys())
    file_contents_prompt = (
        f"\n\nFiles already in your context:\n{files_in_context}\n\nFile Contents:\n"
    )
    for path, content in file_contents.items():
        file_contents_prompt += f"\n--- {path} ---\n{content}\n"

    if automode:
        iteration_info = ""
        if current_iteration is not None and max_iterations is not None:
            iteration_info = f"You are currently on iteration {current_iteration} out of {max_iterations} in automode."
        return (
            BASE_SYSTEM_PROMPT
            + file_contents_prompt
            + "\n\n"
            + AUTOMODE_SYSTEM_PROMPT.format(iteration_info=iteration_info)
            + "\n\n"
            + chain_of_thought_prompt
        )
    else:
        return (
            BASE_SYSTEM_PROMPT + file_contents_prompt + "\n\n" + chain_of_thought_prompt
        )


def create_folders(paths: List[str]) -> str:
    """
    Create new folders at the specified paths, including nested directories.

    Args:
        paths: A list of absolute or relative paths where folders should be created.

    Returns:
        A string containing the results of the folder creation operations.
    """
    results = []
    for path in paths:
        try:
            os.makedirs(path, exist_ok=True)
            results.append(f"Folder(s) created: {path}")
        except OSError as e:
            error_message = f"Error creating folder(s) {path}: {e.strerror}"
            logging.error(error_message)
            results.append(error_message)
        except Exception as e:
            error_message = (
                f"An unexpected error occurred while creating folder {path}: {str(e)}"
            )
            logging.error(error_message)
            results.append(error_message)
    return "\n".join(results)


def create_files(files: Any) -> str:
    """
    Create one or more new files with specified content.

    Args:
        files: A string, dictionary, or list of dictionaries specifying the files to create.

    Returns:
        A string containing the results of the file creation operations.
    """
    global file_contents
    results = []

    if isinstance(files, str):
        files = [{"path": files, "content": ""}]
    elif isinstance(files, dict):
        files = [files]
    elif not isinstance(files, list):
        return "Error: Invalid input type for create_files. Expected a string, dict, or list."

    for file_spec in files:
        try:
            if not isinstance(file_spec, dict):
                raise ValueError(f"Invalid file specification: {file_spec}")

            path = file_spec.get("path")
            content = file_spec.get("content", "")

            if not path:
                raise ValueError("Missing 'path' for file")

            valid_extensions = ROKU_FILE_EXTENSIONS
            filename = os.path.basename(path).lower()
            if (
                not any(path.lower().endswith(ext) for ext in valid_extensions)
                and filename != "manifest"
            ):
                raise ValueError(f"Invalid file extension for file: {path}")

            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                if path.lower().endswith(".brs"):
                    header = (
                        "' *****************************************************************\n"
                        "' BrightScript file\n"
                        f"' Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        "' *****************************************************************\n\n"
                    )
                    f.write(header)
                f.write(content)

            file_contents[path] = content
            results.append(f"File created and added to system prompt: {path}")

        except (ValueError, TypeError) as e:
            error_message = f"Error creating file: {str(e)}"
            logging.error(error_message)
            results.append(error_message)
        except IOError as e:
            error_message = f"I/O error creating file {path}: {e.strerror}"
            logging.error(error_message)
            results.append(error_message)
        except Exception as e:
            error_message = (
                f"An unexpected error occurred while creating file {path}: {str(e)}"
            )
            logging.error(error_message)
            results.append(error_message)

    return "\n".join(results)


async def generate_edit_instructions(
    file_path, file_content, instructions, project_context, full_file_contents
):
    global code_editor_tokens, code_editor_memory, code_editor_files
    try:
        # Prepare memory context (maintains some context between calls)
        memory_context = "\n".join(
            [f"Memory {i+1}:\n{mem}" for i, mem in enumerate(code_editor_memory)]
        )

        # Prepare full file contents context, excluding the file being edited if it's already in code_editor_files
        full_file_contents_context = "\n\n".join(
            [
                f"--- {path} ---\n{content}"
                for path, content in full_file_contents.items()
                if path != file_path or path not in code_editor_files
            ]
        )

        system_prompt = f"""
        You are an expert coding assistant specializing in BrightScript development for Roku. Review the following information carefully:
        
        1. File Content:
        {file_content}
    
        2. Edit Instructions:
        {instructions}
    
        3. Project Context:
        {project_context}
    
        4. Previous Edit Memory:
        {memory_context}
    
        5. Full Project Files Context:
        {full_file_contents_context}
    
        Follow this process to generate edit instructions:
    
        1. <CODE_REVIEW>
        Analyze the existing code thoroughly. Describe how it works, identifying key components, 
        dependencies, and potential issues. Consider the broader project context and previous edits.
        </CODE_REVIEW>
    
        2. <PLANNING>
        Construct a plan to implement the requested changes. Consider:
        - How to avoid code duplication (DRY principle)
        - Balance between maintenance and flexibility
        - Relevant frameworks or libraries
        - Security implications
        - Performance impacts
        Outline discrete changes and suggest small tests for each stage.
        </PLANNING>
    
        3. Finally, generate SEARCH/REPLACE blocks for each necessary change:
        - Use enough context to uniquely identify the code to be changed
        - Maintain correct indentation and formatting
        - Focus on specific, targeted changes
        - Ensure consistency with project context and previous edits
    
        USE THIS FORMAT FOR CHANGES:
    
        <SEARCH>
        Code to be replaced (with sufficient context)
        </SEARCH>
        <REPLACE>
        New code to insert
        </REPLACE>
    
        IMPORTANT: ONLY RETURN CODE INSIDE THE <SEARCH> AND <REPLACE> TAGS. DO NOT INCLUDE ANY PREFACING STATEMENTS OR EXPLANATIONS. FOR EXAMPLE:
    
        <SEARCH>
        def old_function():
            pass
        </SEARCH>
        <REPLACE>
        def new_function():
            print("New Functionality")
        </REPLACE>
        """

        response = client.messages.create(
            model=CODEEDITORMODEL,
            max_tokens=8000,
            **get_thinking_params(CODEEDITORMODEL, effort="low"),
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": "Generate SEARCH/REPLACE blocks for the necessary changes.",
                }
            ],
        )

        # Update token usage for code editor
        code_editor_tokens["input"] += response.usage.input_tokens
        code_editor_tokens["output"] += response.usage.output_tokens
        code_editor_tokens["cache_write"] = response.usage.cache_creation_input_tokens
        code_editor_tokens["cache_read"] = response.usage.cache_read_input_tokens

        ai_response_text = response.content[0].text  # Extract the text

        # If ai_response_text is a list, handle it
        if isinstance(ai_response_text, list):
            ai_response_text = " ".join(
                item["text"] if isinstance(item, dict) and "text" in item else str(item)
                for item in ai_response_text
            )
        elif not isinstance(ai_response_text, str):
            ai_response_text = str(ai_response_text)

        # Validate AI response
        if not validate_ai_response(ai_response_text):
            raise ValueError("AI response does not contain valid SEARCH/REPLACE blocks")

        # Parse the response to extract SEARCH/REPLACE blocks
        edit_instructions = parse_search_replace_blocks(ai_response_text)

        if not edit_instructions:
            raise ValueError("No valid edit instructions were generated")

        # Update code editor memory
        code_editor_memory.append(
            f"Edit Instructions for {file_path}:\n{ai_response_text}"
        )

        # Add the file to code_editor_files set
        code_editor_files.add(file_path)

        return edit_instructions

    except (APIError, APIStatusError) as e:
        error_message = (
            f"API error in generating edit instructions for {file_path}: {str(e)}"
        )
        logging.error(error_message)
        console.print(error_message, style="bold red")
        return []
    except ValueError as e:
        error_message = f"Validation error in generating edit instructions for {file_path}: {str(e)}"
        logging.error(error_message)
        console.print(error_message, style="bold red")
        return []
    except Exception as e:
        error_message = f"An unexpected error occurred in generating edit instructions for {file_path}: {str(e)}"
        logging.error(error_message)
        console.print(error_message, style="bold red")
        return []


def validate_ai_response(response_text: Any) -> bool:
    """
    Validate that the AI response contains valid SEARCH/REPLACE blocks.

    Args:
        response_text: The AI response to validate.

    Returns:
        True if the response is valid, otherwise raises a ValueError.
    """
    if isinstance(response_text, list):
        try:
            response_text = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in response_text
            )
        except Exception as e:
            raise ValueError(f"Invalid format in response_text list: {str(e)}") from e
    elif not isinstance(response_text, str):
        raise ValueError(
            f"Invalid type for response_text: {type(response_text)}. Expected string or list."
        )

    if not re.search(r"<SEARCH>.*?</SEARCH>", response_text, re.DOTALL):
        raise ValueError("AI response does not contain any <SEARCH> blocks.")
    if not re.search(r"<REPLACE>.*?</REPLACE>", response_text, re.DOTALL):
        raise ValueError("AI response does not contain any <REPLACE> blocks.")

    return True


def parse_search_replace_blocks(response_text, use_fuzzy=USE_FUZZY_SEARCH):
    """
    Parse the response text for SEARCH/REPLACE blocks.

    Args:
    response_text (str): The text containing SEARCH/REPLACE blocks.
    use_fuzzy (bool): Whether to use fuzzy matching for search blocks.

    Returns:
    list: A list of dictionaries, each containing 'search', 'replace', and 'similarity' keys.
    """
    blocks = []
    pattern = r"<SEARCH>\s*(.*?)\s*</SEARCH>\s*<REPLACE>\s*(.*?)\s*</REPLACE>"
    matches = re.findall(pattern, response_text, re.DOTALL)

    for search, replace in matches:
        search = search.strip()
        replace = replace.strip()
        similarity = 1.0  # Default to exact match

        if use_fuzzy and search not in response_text:
            # Extract possible search targets from the response text
            possible_search_targets = re.findall(
                r"<SEARCH>\s*(.*?)\s*</SEARCH>", response_text, re.DOTALL
            )
            possible_search_targets = [
                target.strip() for target in possible_search_targets
            ]

            best_match = difflib.get_close_matches(
                search, possible_search_targets, n=1, cutoff=0.6
            )
            if best_match:
                similarity = difflib.SequenceMatcher(
                    None, search, best_match[0]
                ).ratio()
            else:
                similarity = 0.0

        blocks.append({"search": search, "replace": replace, "similarity": similarity})

    return blocks


async def edit_and_apply_multiple(files, project_context, is_automode=False):
    global file_contents
    results = []
    console_outputs = []

    logging.debug(f"edit_and_apply_multiple called with files: {files}")
    logging.debug(f"Project context: {project_context}")

    try:
        files = validate_files_structure(files)
    except ValueError as ve:
        logging.error(f"Validation error: {ve}")
        return [], f"Error: {ve}"

    logging.info(f"Starting edit_and_apply_multiple with {len(files)} file(s)")

    for file in files:
        path = file["path"]
        instructions = file["instructions"]
        logging.info(f"Processing file: {path}")
        try:
            original_content = file_contents.get(path, "")
            if not original_content:
                logging.info(f"Reading content for file: {path}")
                with open(path, "r") as f:
                    original_content = f.read()
                file_contents[path] = original_content

            logging.info(f"Generating edit instructions for file: {path}")
            edit_instructions = await generate_edit_instructions(
                path, original_content, instructions, project_context, file_contents
            )

            logging.debug(f"AI response for {path}: {edit_instructions}")

            if not isinstance(edit_instructions, list) or not all(
                isinstance(item, dict) for item in edit_instructions
            ):
                raise ValueError(
                    "Invalid edit_instructions format. Expected a list of dictionaries."
                )

            if edit_instructions:
                console.print(
                    Panel(
                        f"File: {path}\nThe following SEARCH/REPLACE blocks have been generated:",
                        title="Edit Instructions",
                        style="cyan",
                    )
                )
                for i, block in enumerate(edit_instructions, 1):
                    console.print(f"Block {i}:")
                    console.print(
                        Panel(
                            f"SEARCH:\n{block['search']}\n\nREPLACE:\n{block['replace']}\nSimilarity: {block['similarity']:.2f}",
                            expand=False,
                        )
                    )

                logging.info(f"Applying edits to file: {path}")
                edited_content, changes_made, failed_edits, console_output = (
                    await apply_edits(path, edit_instructions, original_content)
                )

                console_outputs.append(console_output)

                if changes_made:
                    file_contents[path] = edited_content
                    console.print(
                        Panel(
                            f"File contents updated in system prompt: {path}",
                            style="green",
                        )
                    )
                    logging.info(f"Changes applied to file: {path}")

                    if failed_edits:
                        logging.warning(f"Some edits failed for file: {path}")
                        logging.debug(f"Failed edits for {path}: {failed_edits}")
                        results.append(
                            {
                                "path": path,
                                "status": "partial_success",
                                "message": f"Some changes applied to {path}, but some edits failed.",
                                "failed_edits": failed_edits,
                                "edited_content": edited_content,
                            }
                        )
                    else:
                        results.append(
                            {
                                "path": path,
                                "status": "success",
                                "message": f"All changes successfully applied to {path}",
                                "edited_content": edited_content,
                            }
                        )
                else:
                    logging.warning(f"No changes applied to file: {path}")
                    results.append(
                        {
                            "path": path,
                            "status": "no_changes",
                            "message": f"No changes could be applied to {path}. Please review the edit instructions and try again.",
                        }
                    )
            else:
                logging.warning(f"No edit instructions generated for file: {path}")
                results.append(
                    {
                        "path": path,
                        "status": "no_instructions",
                        "message": f"No edit instructions generated for {path}",
                    }
                )
        except Exception as e:
            logging.error(f"Error editing/applying to file {path}: {str(e)}")
            logging.exception("Full traceback:")
            error_message = f"Error editing/applying to file {path}: {str(e)}"
            results.append({"path": path, "status": "error", "message": error_message})
            console_outputs.append(error_message)

    logging.info("Completed edit_and_apply_multiple")
    logging.debug(f"Results: {results}")
    return results, "\n".join(console_outputs)


async def apply_edits(file_path, edit_instructions, original_content):
    changes_made = False
    edited_content = original_content
    total_edits = len(edit_instructions)
    failed_edits = []
    console_output = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        edit_task = progress.add_task("[cyan]Applying edits...", total=total_edits)

        for i, edit in enumerate(edit_instructions, 1):
            search_content = edit["search"].strip()
            replace_content = edit["replace"].strip()
            similarity = edit["similarity"]

            # Use regex to find the content, ignoring leading/trailing whitespace
            pattern = re.compile(re.escape(search_content), re.DOTALL)
            match = pattern.search(edited_content)

            if match or (USE_FUZZY_SEARCH and similarity >= 0.8):
                if not match:
                    # If using fuzzy search and no exact match, find the best match
                    best_match = difflib.get_close_matches(
                        search_content, [edited_content], n=1, cutoff=0.6
                    )
                    if best_match:
                        match = re.search(re.escape(best_match[0]), edited_content)

                if match:
                    # Replace the content using re.sub for more robust replacement
                    replace_content_cleaned = re.sub(
                        r"</?SEARCH>|</?REPLACE>", "", replace_content
                    )
                    edited_content = pattern.sub(
                        replace_content_cleaned, edited_content, count=1
                    )
                    changes_made = True

                    # Display the diff for this edit
                    diff_result = generate_diff(
                        search_content, replace_content, file_path
                    )
                    console.print(
                        Panel(
                            diff_result,
                            title=f"Changes in {file_path} ({i}/{total_edits}) - Similarity: {similarity:.2f}",
                            style="cyan",
                        )
                    )
                    console_output.append(
                        f"Edit {i}/{total_edits} applied successfully"
                    )
                else:
                    message = f"Edit {i}/{total_edits} not applied: content not found (Similarity: {similarity:.2f})"
                    console_output.append(message)
                    console.print(Panel(message, style="yellow"))
                    failed_edits.append(f"Edit {i}: {search_content}")
            else:
                message = f"Edit {i}/{total_edits} not applied: content not found (Similarity: {similarity:.2f})"
                console_output.append(message)
                console.print(Panel(message, style="yellow"))
                failed_edits.append(f"Edit {i}: {search_content}")

            progress.update(edit_task, advance=1)

    if not changes_made:
        message = "No changes were applied. The file content already matches the desired state."
        console_output.append(message)
        console.print(Panel(message, style="green"))
    else:
        # Write the changes to the file
        with open(file_path, "w") as file:
            file.write(edited_content)
        message = f"Changes have been written to {file_path}"
        console_output.append(message)
        console.print(Panel(message, style="green"))

    return edited_content, changes_made, failed_edits, "\n".join(console_output)


def highlight_diff(diff_text):
    return Syntax(diff_text, "diff", theme="monokai", line_numbers=True)


def generate_diff(original, new, path):
    diff = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
    )

    diff_text = "".join(diff)
    highlighted_diff = highlight_diff(diff_text)

    return highlighted_diff


async def execute_code(code, timeout=10):
    global running_processes

    # Input validation
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    if not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a number")

    # Generate a unique identifier for this process
    process_id = f"process_{len(running_processes)}"

    # Write the BrightScript code to a temporary file
    try:
        with open(f"{process_id}.brs", "w") as f:
            f.write(code)
    except IOError as e:
        return process_id, f"Error writing BrightScript code to file: {str(e)}"

    # For BrightScript development, we can't execute the code locally.
    # Instead, we'll return a message indicating that the code should be tested on a Roku device or emulator.
    execution_result = (
        f"Process ID: {process_id}\n\n"
        "BrightScript code created successfully.\n"
        "To execute this code, you need to deploy it to a Roku device or emulator.\n"
        "Please use the Roku developer tools to sideload and test this BrightScript component."
    )

    try:
        # Simulate a running process
        running_processes[process_id] = "BrightScript_Component"

        return process_id, execution_result
    except Exception as e:
        return process_id, f"Error processing BrightScript code: {str(e)}"
    finally:
        # Cleanup: remove the temporary file
        try:
            os.remove(f"{process_id}.brs")
        except OSError:
            pass  # Ignore errors in removing the file


# Update the read_multiple_files function to handle both single and multiple files
def read_multiple_files(paths, recursive=False):
    global file_contents
    results = []

    if isinstance(paths, str):
        paths = [paths]

    for path in paths:
        try:
            abs_path = os.path.abspath(path)
            if os.path.isdir(abs_path):
                if recursive:
                    file_paths = glob.glob(
                        os.path.join(abs_path, "**", "*"), recursive=True
                    )
                else:
                    file_paths = glob.glob(os.path.join(abs_path, "*"))
                file_paths = [
                    f
                    for f in file_paths
                    if os.path.isfile(f)
                    and (
                        f.lower().endswith(tuple(ROKU_TEXT_EXTENSIONS))
                        or os.path.basename(f).lower() == "manifest"
                    )
                ]
            else:
                file_paths = glob.glob(abs_path, recursive=recursive)

            for file_path in file_paths:
                abs_file_path = os.path.abspath(file_path)
                if os.path.isfile(abs_file_path) and (
                    abs_file_path.lower().endswith(tuple(ROKU_TEXT_EXTENSIONS))
                    or os.path.basename(abs_file_path).lower() == "manifest"
                ):
                    if abs_file_path not in file_contents:
                        with open(abs_file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        file_contents[abs_file_path] = content
                        results.append(
                            f"BrightScript file '{abs_file_path}' has been read and stored in the system prompt."
                        )
                    else:
                        results.append(
                            f"BrightScript file '{abs_file_path}' is already in the system prompt. No need to read again."
                        )
                else:
                    results.append(
                        f"Skipped '{abs_file_path}': Not a BrightScript or SceneGraph XML file."
                    )
        except Exception as e:
            results.append(f"Error reading BrightScript path '{path}': {str(e)}")

    return "\n".join(results)


def list_files(path="."):
    try:
        files = os.listdir(path)
        return "\n".join(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"


def tavily_search(query: str) -> str:
    """
    Perform a web search using the Tavily API.

    Args:
        query: The search query.

    Returns:
        The search result or an error message.
    """
    try:
        if tavily is None:
            return "Set TAVILY_API_KEY to enable web research. Local project tools remain available."
        response = tavily.qna_search(query=query, search_depth="advanced")
        return response
    except APIError as e:
        error_message = f"Tavily API error: {str(e)}"
        logging.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"An unexpected error occurred during search: {str(e)}"
        logging.error(error_message)
        return error_message


def stop_process(process_id):
    global running_processes
    if process_id in running_processes:
        process = running_processes[process_id]
        if sys.platform == "win32":
            process.terminate()
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        del running_processes[process_id]
        return f"Process {process_id} has been stopped."
    else:
        return f"No running process found with ID {process_id}."


def run_shell_command(command):
    """
    Executes a shell command.

    This function executes shell commands relevant to Roku development,
    such as installing Roku libraries, building projects, or interacting with
    Roku devices. It provides detailed output and error handling specific to
    Roku development scenarios.
    Args:
        command (str): The shell command to execute.

    Returns:
        dict: A dictionary containing the results of the command execution, including
              stdout, stderr, return code, and any errors encountered.
    """
    try:
        if isinstance(command, str):
            command = (
                command.split()
            )  # Split command string into list if string provided
        result = subprocess.run(
            command, shell=False, check=True, text=True, capture_output=True
        )

        # Check for common Roku-related errors
        if "ERROR:" in result.stderr or "WARNING:" in result.stderr:
            console.print(
                f"[bold yellow]Potential Roku issue detected:[/] {result.stderr.strip()}"
            )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
    except subprocess.CalledProcessError as e:
        error_message = str(e)

        # Provide more specific guidance for common Roku errors
        if (
            "roku-deploy" in command[0]
        ):  # Example: check if roku-deploy command was used
            error_message += "\n\n[bold red]Roku Deployment Failed.[/]\n"
            error_message += "Check that your Roku device is on the same network and developer mode is enabled.\n"
            error_message += (
                "Ensure the correct IP address, username, and password are provided.\n"
            )

        elif "bsc" in command[0]:  # Example: using BrightScript compiler
            error_message += "\n\n[bold red]BrightScript Compilation Error.[/]\n"
            error_message += (
                "Review the error messages for BrightScript syntax or logic problems."
            )

        # Add other relevant troubleshooting suggestions
        elif e.returncode == 127:
            error_message += f"\n\nCommand not found: {command[0]}. Ensure the command is installed and in your PATH."

        return {
            "stdout": e.stdout,
            "stderr": e.stderr,
            "return_code": e.returncode,
            "error": error_message,
        }
    except FileNotFoundError:
        return {
            "error": f"Command not found: {command[0]}. Check if it's installed and accessible in your PATH."
        }
    except Exception as e:
        return {"error": f"An error occurred while executing the command: {str(e)}"}


def create_modern_roku_manifest(project_name: str, version: str = "1.0.0") -> str:
    """Create a modern Roku manifest with all required fields for certification"""
    version_parts = version.split(".")
    major = version_parts[0] if len(version_parts) > 0 else "1"
    minor = version_parts[1] if len(version_parts) > 1 else "0"
    build = version_parts[2] if len(version_parts) > 2 else "0"

    manifest_content = f"""# Channel Manifest for {project_name}
title={project_name}
subtitle=A Roku Channel
major_version={major}
minor_version={minor}
build_version={build}

# Icons and Splash Screens (Required for certification)
mm_icon_focus_hd=pkg:/images/icon_focus_hd.png
mm_icon_focus_sd=pkg:/images/icon_focus_sd.png
mm_icon_side_hd=pkg:/images/icon_side_hd.png
mm_icon_side_sd=pkg:/images/icon_side_sd.png
splash_screen_hd=pkg:/images/splash_hd.jpg
splash_screen_sd=pkg:/images/splash_sd.jpg

# Resolution Support (Required)
ui_resolutions=hd,fhd

# Localization Support
supported_locales=en_US,es_ES,fr_FR,de_DE

# Channel Information (Required for store)
channel_genre=Special Purpose
channel_store_description=A modern Roku channel built with best practices
content_rating=UNRATED
parental_rating=General Audience

# Privacy and Legal (Required for certification)
privacy_policy=https://example.com/privacy
terms_of_service=https://example.com/terms

# Modern Roku Features
supports_input_launch=1
screensaver_title={project_name} Screensaver
screensaver_private=0

# Performance and Compatibility
bs_libs_required=roku_ads_lib,analytics_lib
rsg_version=1.3

# Network and Security
network_not_required=0
supports_ethernet=1
requires_internet=1

# Accessibility Support
accessibility_enabled=1
supports_closed_captions=1
supports_audio_descriptions=1

# Launch Requirements
requires_gaming_remote=0
supports_voice_remote_pro=1"""

    return manifest_content


def validate_roku_project_structure(project_dir: str) -> Tuple[bool, List[str]]:
    """Validate that a Roku project has the correct structure and required files"""
    required_files = ["manifest", "source/main.brs"]

    required_dirs = ["components", "images", "source"]

    recommended_files = [
        "images/icon_focus_hd.png",
        "images/icon_focus_sd.png",
        "images/splash_hd.jpg",
        "images/splash_sd.jpg",
    ]

    issues = []

    # Check required directories
    for dir_name in required_dirs:
        dir_path = os.path.join(project_dir, dir_name)
        if not os.path.exists(dir_path):
            issues.append(f"Missing required directory: {dir_name}")

    # Check required files
    for file_name in required_files:
        file_path = os.path.join(project_dir, file_name)
        if not os.path.exists(file_path):
            issues.append(f"Missing required file: {file_name}")

    # Check recommended files
    for file_name in recommended_files:
        file_path = os.path.join(project_dir, file_name)
        if not os.path.exists(file_path):
            issues.append(f"Missing recommended file: {file_name}")

    return len(issues) == 0, issues


def generate_roku_component_registry() -> str:
    """Generate a component registry file for better organization"""
    registry_content = """# Roku Component Registry
# This file helps organize and track custom components

[Components]
# Scene Components
MainScene=components/MainScene/MainScene.xml
HomeScene=components/HomeScene/HomeScene.xml
PlayerScene=components/PlayerScene/PlayerScene.xml

# UI Components  
CustomList=components/CustomList/CustomList.xml
VideoPlayer=components/VideoPlayer/VideoPlayer.xml
LoadingSpinner=components/LoadingSpinner/LoadingSpinner.xml

# Task Components
ContentTask=components/tasks/ContentTask/ContentTask.xml
AnalyticsTask=components/tasks/AnalyticsTask/AnalyticsTask.xml

[Assets]
# Required Images
icon_focus_hd=images/icon_focus_hd.png
icon_focus_sd=images/icon_focus_sd.png
splash_hd=images/splash_hd.jpg
splash_sd=images/splash_sd.jpg

# Background Images
main_background=images/backgrounds/main_bg.jpg
loading_background=images/backgrounds/loading_bg.jpg

[Localization]
# Supported Languages
en_US=locale/en_US/translations.xml
es_ES=locale/es_ES/translations.xml
fr_FR=locale/fr_FR/translations.xml
"""

    return registry_content


def create_accessibility_helpers() -> str:
    """Create BrightScript helper functions for accessibility"""
    accessibility_code = """' Accessibility Helper Functions
' These functions help implement Roku accessibility features

function SetAccessibleText(node as Object, text as String)
    if node <> invalid and text <> invalid
        node.accessibleText = text
        
        ' Also set for screen readers
        if node.hasField("accessibleDescription")
            node.accessibleDescription = text
        end if
    end if
end function

function AnnounceForAccessibility(text as String)
    ' Create an announcement for screen readers
    if text <> invalid and text <> ""
        ' Use Roku's accessibility API if available
        deviceInfo = CreateObject("roDeviceInfo")
        if deviceInfo.hasFeature("accessibility")
            ' Make accessibility announcement
            print "[ACCESSIBILITY] " + text
        end if
    end if
end function

function SetupKeyboardAccessibility(keyboard as Object)
    if keyboard <> invalid
        keyboard.accessibleText = "On-screen keyboard. Use directional keys to navigate."
        keyboard.accessibleDescription = "Enter text using the directional pad and OK button."
    end if
end function

function SetupListAccessibility(list as Object, itemCount as Integer)
    if list <> invalid
        list.accessibleText = "List with " + itemCount.toStr() + " items"
        list.accessibleDescription = "Use up and down arrows to navigate, OK to select"
    end if
end function

function SetupVideoAccessibility(video as Object, title as String)
    if video <> invalid
        if title <> invalid and title <> ""
            video.accessibleText = "Video player: " + title
        else
            video.accessibleText = "Video player"
        end if
        video.accessibleDescription = "Use OK to play/pause, left/right to seek"
    end if
end function

function CreateAccessibleButton(text as String, description as String) as Object
    button = CreateObject("roSGNode", "Button")
    button.text = text
    button.accessibleText = text
    if description <> invalid
        button.accessibleDescription = description
    end if
    return button
end function"""

    return accessibility_code


def create_performance_monitoring() -> str:
    """Create BrightScript code for performance monitoring"""
    performance_code = """' Performance Monitoring Utilities
' These functions help monitor app performance for optimization

function StartPerformanceTimer(timerName as String)
    if m.performanceTimers = invalid
        m.performanceTimers = {}
    end if
    
    timer = CreateObject("roTimespan")
    timer.mark()
    m.performanceTimers[timerName] = timer
end function

function EndPerformanceTimer(timerName as String) as Integer
    if m.performanceTimers <> invalid and m.performanceTimers[timerName] <> invalid
        elapsed = m.performanceTimers[timerName].totalMilliseconds()
        m.performanceTimers.delete(timerName)
        
        ' Log performance data
        print "[PERFORMANCE] " + timerName + ": " + elapsed.toStr() + "ms"
        
        ' Send to analytics if needed
        LogPerformanceMetric(timerName, elapsed)
        
        return elapsed
    end if
    return -1
end function

function LogPerformanceMetric(metricName as String, value as Integer)
    ' Log performance metrics for analysis
    if m.analytics <> invalid
        m.analytics.trackPerformance(metricName, value)
    end if
end function

function CheckMemoryUsage() as Object
    deviceInfo = CreateObject("roDeviceInfo")
    memInfo = {
        available: deviceInfo.getGeneralMemoryLevel(),
        used: 100 - deviceInfo.getGeneralMemoryLevel()
    }
    
    ' Log if memory usage is high
    if memInfo.used > 80
        print "[WARNING] High memory usage: " + memInfo.used.toStr() + "%"
    end if
    
    return memInfo
end function

function OptimizeImageMemory(poster as Object)
    ' Optimize image memory usage
    if poster <> invalid
        ' Enable image optimization features
        poster.loadDisplayMode = "scaleToFit"
        poster.observeField("loadStatus", "OnImageLoadComplete")
    end if
end function

function OnImageLoadComplete()
    ' Clean up after image loading
    CheckMemoryUsage()
end function"""

    return performance_code


def validate_files_structure(files):
    if not isinstance(files, (dict, list)):
        raise ValueError(
            "Invalid 'files' structure. Expected a dictionary or a list of dictionaries for BrightScript files."
        )

    if isinstance(files, dict):
        files = [files]

    for file in files:
        if not isinstance(file, dict):
            raise ValueError(
                "Each BrightScript file must be represented by a dictionary."
            )
        if "path" not in file or "instructions" not in file:
            raise ValueError(
                "Each BrightScript file dictionary must contain 'path' and 'instructions' keys."
            )
        if not isinstance(file["path"], str) or not isinstance(
            file["instructions"], str
        ):
            raise ValueError(
                "'path' and 'instructions' for BrightScript files must be strings."
            )
        if not (
            file["path"].lower().endswith(tuple(ROKU_TEXT_EXTENSIONS))
            or os.path.basename(file["path"]).lower() == "manifest"
        ):
            raise ValueError(
                f"Invalid file extension for BrightScript or related file: {file['path']}"
            )

    return files


def scan_folder(folder_path: str, output_file: str) -> str:
    ignored_folders = {"components", "images", "fonts"}
    markdown_content = f"# Roku Channel Scan: {folder_path}\n\n"
    total_chars = len(markdown_content)
    max_chars = 600000  # Approximating 150,000 tokens

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in ignored_folders]

        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, folder_path)

            if (
                file.lower().endswith(tuple(ROKU_TEXT_EXTENSIONS))
                or file.lower() == "manifest"
            ):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    file_content = (
                        f"## {relative_path}\n\n```brightscript\n{content}\n```\n\n"
                    )
                    if total_chars + len(file_content) > max_chars:
                        remaining_chars = max_chars - total_chars
                        if remaining_chars > 0:
                            truncated_content = file_content[:remaining_chars]
                            markdown_content += truncated_content
                            markdown_content += "\n\n... Content truncated due to size limitations ...\n"
                        else:
                            markdown_content += "\n\n... Additional BrightScript files omitted due to size limitations ...\n"
                        break
                    else:
                        markdown_content += file_content
                        total_chars += len(file_content)
                except Exception as e:
                    error_msg = f"## {relative_path}\n\nError reading BrightScript file: {str(e)}\n\n"
                    if total_chars + len(error_msg) <= max_chars:
                        markdown_content += error_msg
                        total_chars += len(error_msg)

        if total_chars >= max_chars:
            break

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return f"Roku channel scan complete. Markdown file created at: {output_file}. Total characters: {total_chars}"


def encode_image_to_base64(image_path):
    try:
        with Image.open(image_path) as img:
            max_size = (1024, 1024)
            img.thumbnail(max_size, Image.DEFAULT_STRATEGY)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="JPEG")
            return base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
    except Exception as e:
        return f"Error encoding image: {str(e)}"


async def send_to_ai_for_executing(code, execution_result):
    global code_execution_tokens

    try:
        system_prompt = f"""
        You are an AI code execution agent specializing in Roku development. Your task is to analyze the provided BrightScript code and its execution result (or the result of attempting to execute it), then provide a concise summary. Follow these steps:

        1. Review the BrightScript code:
        {code}

        2. Analyze the execution result or explanation:
        {execution_result}

        3. Provide a brief summary of:
           - What parts of the code are likely to work correctly on a Roku device
           - Any potential issues or errors specific to the Roku environment (e.g., SceneGraph limitations, BrightScript quirks)
           - Potential improvements or fixes, considering Roku best practices and coding style
           - Any important observations about the code's potential performance or resource usage on Roku
           - If applicable, explain next steps for testing on a Roku device or emulator


        Be concise and focus on Roku-specific aspects.  If the code is not BrightScript, explain that it can't be run directly on Roku.
        IMPORTANT: PROVIDE ONLY YOUR ANALYSIS AND OBSERVATIONS. DO NOT INCLUDE ANY PREFACING STATEMENTS OR EXPLANATIONS OF YOUR ROLE.
        """

        response = client.messages.create(
            model=CODEEXECUTIONMODEL,
            max_tokens=2000,
            **get_thinking_params(CODEEXECUTIONMODEL, effort="low"),
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this BrightScript code and its outcome:\n\nCode:\n{code}\n\nResult:\n{execution_result}",
                }
            ],
        )

        # Update token usage for code execution
        code_execution_tokens["input"] += response.usage.input_tokens
        code_execution_tokens["output"] += response.usage.output_tokens
        code_execution_tokens["cache_write"] = (
            response.usage.cache_creation_input_tokens
        )
        code_execution_tokens["cache_read"] = response.usage.cache_read_input_tokens

        analysis = response.content[0].text

        return analysis

    except Exception as e:
        console.print(
            f"Error in AI code execution analysis: {str(e)}", style="bold red"
        )
        return f"Error analyzing BrightScript code: {str(e)}"


def save_chat():
    # Generate filename
    now = datetime.datetime.now()
    filename = f"Chat_{now.strftime('%H%M')}.md"

    # Format conversation history
    formatted_chat = "# Claude Sonnet 4 Engineer Chat Log\n\n"
    for message in conversation_history:
        if message["role"] == "user":
            formatted_chat += f"## User\n\n{message['content']}\n\n"
        elif message["role"] == "assistant":
            if isinstance(message["content"], str):
                formatted_chat += f"## Yuki\n\n{message['content']}\n\n"
            elif isinstance(message["content"], list):
                for content in message["content"]:
                    if content["type"] == "tool_use":
                        formatted_chat += f"### Tool Use: {content['name']}\n\n```json\n{json.dumps(content['input'], indent=2)}\n```\n\n"
                    elif content["type"] == "text":
                        formatted_chat += f"## Yuki\n\n{content['text']}\n\n"
        elif message["role"] == "user" and isinstance(message["content"], list):
            for content in message["content"]:
                if content["type"] == "tool_result":
                    formatted_chat += (
                        f"### Tool Result\n\n```\n{content['content']}\n```\n\n"
                    )

    # Save to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(formatted_chat)

    return filename


tools = [
    {
        "name": "create_folders",
        "description": "Create new folders at the specified paths, including nested directories. This tool should be used when you need to create one or more directories (including nested ones) in the project structure. It will create all necessary parent directories if they don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "An array of absolute or relative paths where the folders should be created. Use forward slashes (/) for path separation, even on Windows systems. For nested directories, simply include the full path (e.g., 'parent/child/grandchild').",
                }
            },
            "required": ["paths"],
        },
    },
    {
        "name": "scan_folder",
        "description": "Scan a specified folder and create a Markdown file with the contents of all coding text files, excluding binary files and common ignored folders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "The absolute or relative path of the folder to scan. Use forward slashes (/) for path separation, even on Windows systems.",
                },
                "output_file": {
                    "type": "string",
                    "description": "The name of the output Markdown file to create with the scanned contents.",
                },
            },
            "required": ["folder_path", "output_file"],
        },
    },
    {
        "name": "create_files",
        "description": "Create one or more new files with the given contents. This tool should be used when you need to create files in the project structure. It will create all necessary parent directories if they don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "A single file path to create an empty file.",
                        },
                        {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path"],
                        },
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path"],
                            },
                        },
                    ],
                    "description": "The path(s) of the file(s) to create. Use forward slashes (/) for path separation, even on Windows systems. Supports wildcards (e.g., '*.py') and directory paths.",
                }
            },
            "required": ["files"],
        },
    },
    {
        "name": "edit_and_apply_multiple",
        "description": "Apply AI-powered improvements to multiple files based on specific instructions and detailed project context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "The absolute or relative path of the file to edit.",
                            },
                            "instructions": {
                                "type": "string",
                                "description": "Specific instructions for editing this file.",
                            },
                        },
                        "required": ["path", "instructions"],
                    },
                },
                "project_context": {
                    "type": "string",
                    "description": "Comprehensive context about the project, including recent changes, new variables or functions, interconnections between files, coding standards, and any other relevant information that might affect the edits.",
                },
            },
            "required": ["files", "project_context"],
        },
    },
    {
        "name": "execute_code",
        "description": "Return a message indicating that the code should be tested on a Roku device or emulator.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute. This should be a single, standalone BrightScript component that can be tested on a Roku device or emulator.",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "read_multiple_files",
        "description": "Read the contents of one or more existing files, supporting wildcards and recursive directory reading.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "A single file path, directory path, or wildcard pattern.",
                        },
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "An array of file paths, directory paths, or wildcard patterns.",
                        },
                    ],
                    "description": "The path(s) of the file(s) to read. Use forward slashes (/) for path separation, even on Windows systems. Supports wildcards (e.g., '*.py') and directory paths.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, read files recursively from directories. Default is false.",
                    "default": False,
                },
            },
            "required": ["paths"],
        },
    },
    {
        "name": "list_files",
        "description": "List all files and directories in the specified folder. This tool should be used when you need to see the contents of a directory. It will return a list of all files and subdirectories in the specified path. If the directory doesn't exist or can't be read, an appropriate error message will be returned.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The absolute or relative path of the folder to list. Use forward slashes (/) for path separation, even on Windows systems. If not provided, the current working directory will be used.",
                }
            },
        },
    },
    {
        "name": "tavily_search",
        "description": "Perform a web search using the Tavily API to get up-to-date information or additional context. This tool should be used when you need current information or feel a search could provide a better answer to the user's query. It will return a summary of the search results, including relevant snippets and source URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be as specific and detailed as possible to get the most relevant results.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_roku_project",
        "description": "Create a complete Roku project structure with modern standards and all required files for certification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name of the Roku project/channel",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory where the project should be created",
                    "default": ".",
                },
                "project_type": {
                    "type": "string",
                    "enum": ["basic", "sgdex", "grid"],
                    "description": "Type of Roku project to create. Use 'sgdex' for SceneGraph Developer Extensions, 'basic' for standard.",
                    "default": "basic",
                },
            },
            "required": ["project_name"],
        },
    },
    {
        "name": "create_roku_component",
        "description": "Create a new SceneGraph component with XML and BrightScript files using modern templates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "enum": [
                        "Scene",
                        "Task",
                        "CustomList",
                        "GridView",
                        "DetailsView",
                        "MediaView",
                        "ErrorView",
                        "VideoPlayer",
                        "Effect",
                        "WebSocketTask",
                    ],
                    "description": "Type of SceneGraph component to create. 'Effect' (Roku OS 16.0+) generates GPU-accelerated rounded corners/borders/gradients; 'WebSocketTask' (Roku OS 16.0+) generates an roWebSocket client Task.",
                },
                "name": {"type": "string", "description": "Name of the component"},
                "output_dir": {
                    "type": "string",
                    "description": "Directory where component should be created",
                },
                "include_accessibility": {
                    "type": "boolean",
                    "description": "Include accessibility features in generated templates",
                    "default": True,
                },
            },
            "required": ["component_type", "name", "output_dir"],
        },
    },
    {
        "name": "generate_memory_monitor",
        "description": "Generate roAppMemoryMonitor integration (source/MemoryMonitor.brs) for Roku OS 15.2+ low-memory threshold events (80/85/90/95% of app limit) with roDeviceInfo fallback. This integration is REQUIRED for certification as of October 1, 2026 - apps without it fail Static Analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_websocket_handler",
        "description": "Generate a WebSocketTask component using the roWebSocket component (Roku OS 16.0+) for bi-directional server communication.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_sse_handler",
        "description": "Generate an SSEEventsTask component that consumes Server-Sent Events via roUrlTransfer.AsyncGetSSEvents() and roSSEvent (Roku OS 16.0+).",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_roku_pay_integration",
        "description": "Generate Roku Pay integration (source/RokuPay.brs) using the ChannelStore node: entitlement checks on launch, catalog browsing, and purchase flows for SVOD/TVOD channels. Includes the Roku OS 16.0 GetRokuCustomerId command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "validate_content_feed",
        "description": "Validate a Roku Direct Publisher JSON content feed against the published schema: required fields, HTTPS URLs, videoType values (HLS/DASH/MP4/SmoothStreaming), ISO 8601 dates, and thumbnail requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The JSON content of the feed to validate",
                }
            },
            "required": ["content"],
        },
    },
    {
        "name": "get_roku_device_info",
        "description": "Fetch device information from a Roku device over ECP (GET http://<device-ip>:8060/query/device-info). Returns the raw XML with model, firmware version, and device capabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "IP address of the Roku device (find at Settings > Network > About)",
                }
            },
            "required": ["device_ip"],
        },
    },
    {
        "name": "check_device_performance",
        "description": "Query channel performance stats from a device in developer mode via the ECP query/chanperf command. Roku OS 15.2+ responses include the <proc-stat> field with raw Linux CPU/process statistics for monitoring tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "IP address of the Roku device in developer mode",
                }
            },
            "required": ["device_ip"],
        },
    },
    {
        "name": "capture_device_screenshot",
        "description": "Capture a screenshot from a Roku device in developer mode using HTTP digest auth, saving it to an image file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "IP address of the Roku device in developer mode",
                },
                "username": {
                    "type": "string",
                    "description": "Developer web server username",
                    "default": "rokudev",
                },
                "password": {
                    "type": "string",
                    "description": "Developer web server password",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path where the screenshot image should be saved",
                },
            },
            "required": ["device_ip", "password", "output_path"],
        },
    },
    {
        "name": "capture_device_logs",
        "description": "Connect to the Roku debug console (telnet port 8085) and capture BrightScript runtime logs for a fixed duration. Shows console output, crash stack traces, and runtime errors from a sideloaded channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_ip": {
                    "type": "string",
                    "description": "IP address of the Roku device in developer mode",
                },
                "duration_seconds": {
                    "type": "integer",
                    "description": "How long to capture logs (1-300 seconds)",
                    "default": 10,
                },
                "output_file": {
                    "type": "string",
                    "description": "Optional path to save the full captured log to a file",
                },
            },
            "required": ["device_ip"],
        },
    },
    {
        "name": "validate_roku_project",
        "description": "Validate a Roku project structure against certification requirements and best practices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory to validate",
                },
                "check_certification": {
                    "type": "boolean",
                    "description": "Perform certification-level validation",
                    "default": True,
                },
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_component_registry",
        "description": "Generate or update a component registry file for better project organization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                },
                "output_file": {
                    "type": "string",
                    "description": "Path for the registry file",
                    "default": "component_registry.txt",
                },
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_deep_link_handler",
        "description": "Generate boilerplates for parsing Roku deep link args in Main.brs and routing in SceneGraph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_content_feed_handler",
        "description": "Generate a Task component to parse JSON/MRSS feeds into a ContentNode tree.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                },
                "feed_type": {
                    "type": "string",
                    "enum": ["json", "xml"],
                    "description": "Type of feed to parse (json or xml)",
                    "default": "json",
                },
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "generate_raf_integration",
        "description": "Generate a Task component that integrates the Roku Advertising Framework (RAF).",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Path to the Roku project directory",
                }
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "package_roku_app",
        "description": "Package a Roku channel into a deployment-ready zip file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_dir": {
                    "type": "string",
                    "description": "Path to the Roku project source directory",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path for the output zip package",
                },
                "exclude_dev_files": {
                    "type": "boolean",
                    "description": "Exclude development files from package",
                    "default": True,
                },
            },
            "required": ["source_dir", "output_path"],
        },
    },
    {
        "name": "create_modern_manifest",
        "description": "Generate a modern Roku manifest file with all required fields for certification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name of the Roku channel",
                },
                "version": {
                    "type": "string",
                    "description": "Version number (e.g., '1.0.0')",
                    "default": "1.0.0",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path where manifest should be created",
                    "default": "./manifest",
                },
            },
            "required": ["project_name"],
        },
    },
    {
        "name": "create_accessibility_helpers",
        "description": "Generate BrightScript helper functions for accessibility compliance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Path for the accessibility helpers file",
                    "default": "./source/AccessibilityHelpers.brs",
                }
            },
        },
    },
    {
        "name": "create_performance_monitoring",
        "description": "Generate BrightScript code for performance monitoring and optimization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Path for the performance monitoring file",
                    "default": "./source/PerformanceMonitoring.brs",
                }
            },
        },
    },
    {
        "name": "validate_roku_component",
        "description": "Validate a Roku SceneGraph component's XML and BrightScript files for structure and best practices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "component_path": {
                    "type": "string",
                    "description": "Path to the XML component file to validate",
                }
            },
            "required": ["component_path"],
        },
    },
    {
        "name": "validate_scenegraph_component",
        "description": "Validate SceneGraph XML component structure and BrightScript integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "component_path": {
                    "type": "string",
                    "description": "Path to the XML component file to validate",
                },
                "check_accessibility": {
                    "type": "boolean",
                    "description": "Check for accessibility compliance",
                    "default": True,
                },
            },
            "required": ["component_path"],
        },
    },
    {
        "name": "deploy_to_roku",
        "description": "Deploy a packaged Roku channel to a development device.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package_path": {
                    "type": "string",
                    "description": "Path to the packaged zip file",
                },
                "device_ip": {
                    "type": "string",
                    "description": "IP address of the Roku device",
                },
                "username": {
                    "type": "string",
                    "description": "Roku developer username",
                    "default": "rokudev",
                },
                "password": {
                    "type": "string",
                    "description": "Roku developer password",
                },
            },
            "required": ["package_path", "device_ip", "password"],
        },
    },
    {
        "name": "validate_roku_manifest",
        "description": "Validate the contents of a Roku app manifest file. Use this to ensure the manifest meets Roku's requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content of the manifest file to validate",
                }
            },
            "required": ["content"],
        },
    },
    {
        "name": "lint_brightscript",
        "description": "Lint BrightScript code to check for common issues and adherence to best practices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The BrightScript code to lint",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "run_shell_command",
        "description": "Execute a shell command and return its output. This tool should be used when you need to run system commands or interact with the operating system. It will return the standard output, standard error, and return code of the executed command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute. Ensure the command is safe and appropriate for the current operating system.",
                }
            },
            "required": ["command"],
        },
    },
]


def validate_roku_manifest(content):
    """Enhanced manifest validation for Roku OS 12/13/14 requirements"""
    # Updated for Roku OS 12/13/14 requirements
    required_fields = [
        "title",
        "major_version",
        "minor_version",
        "build_version",
        "mm_icon_focus_hd",
        "mm_icon_focus_sd",
        "splash_screen_hd",
        "splash_screen_sd",
        "ui_resolutions",
        "supported_locales",
        "channel_genre",
        "parental_rating",
    ]

    # Additional required fields for certification
    recommended_fields = [
        "privacy_policy",
        "terms_of_service",
        "content_rating",
        "screensaver_title",
        "supports_input_launch",
        "channel_store_description",
    ]

    issues = []
    warnings = []

    # Check required fields
    for field in required_fields:
        if field not in content:
            issues.append(f"Missing required field: {field}")

    # Check recommended fields
    for field in recommended_fields:
        if field not in content:
            warnings.append(f"Missing recommended field: {field}")

    # Validate specific field formats
    if "ui_resolutions" in content:
        valid_resolutions = ["hd", "fhd", "sd"]
        if not any(res in content.lower() for res in valid_resolutions):
            issues.append("ui_resolutions must include at least one of: hd, fhd, sd")

    # Check version format
    version_fields = ["major_version", "minor_version", "build_version"]
    for field in version_fields:
        if field in content:
            try:
                int(content.split(f"{field}=")[1].split("\n")[0])
            except:
                issues.append(f"Invalid {field} format - must be numeric")

    # Build response
    response = ""
    if issues:
        response += "Manifest validation failed:\nErrors:\n" + "\n".join(
            f"  - {issue}" for issue in issues
        )

    if warnings:
        response += "\nWarnings:\n" + "\n".join(
            f"  - {warning}" for warning in warnings
        )

    if not issues and not warnings:
        response = "Manifest validation passed. All required and recommended fields are present."
    elif not issues:
        response = "Manifest validation passed with warnings. Consider adding recommended fields."

    return response


def lint_brightscript(code):
    """Enhanced BrightScript linting for modern Roku development"""
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        line_lower = line.lower().strip()

        # Legacy issues
        if "print" in line_lower:
            issues.append(
                f"Line {i}: Info: 'print' statements should be removed or gated behind "
                "a conditional compilation flag (cpu/DEBUG) before publishing"
            )

        if "goto" in line_lower:
            issues.append(
                f"Line {i}: Warning: 'goto' statements are discouraged. Use structured programming constructs"
            )

        # Memory management issues
        if line_lower.startswith("m.") and "=" in line and "invalid" not in line_lower:
            if not any(
                cleanup in code.lower()
                for cleanup in ["m.top.unobservefieldsall", "delete m."]
            ):
                issues.append(
                    f"Line {i}: Info: Consider memory cleanup for member variables"
                )

        # Performance issues
        if "for each" in line_lower and "in" in line_lower:
            if ".count()" in line_lower or ".len()" in line_lower:
                issues.append(
                    f"Line {i}: Performance: Avoid calling count()/len() in for-each loops"
                )

        # Threading best practices
        if 'createobject("rotask")' in line_lower.replace(" ", ""):
            if not any("m.top.functionname" in l.lower() for l in lines):
                issues.append(
                    f"Line {i}: Warning: Task objects should set functionName for proper execution"
                )

        # SceneGraph best practices
        if "observefield" in line_lower:
            if not any(
                "unobservefield" in l.lower() or "unobservefieldsall" in l.lower()
                for l in lines
            ):
                issues.append(
                    f"Line {i}: Warning: Consider unobserving fields to prevent memory leaks"
                )

        # Accessibility compliance
        if "label" in line_lower and "text=" in line_lower:
            if not any(
                "accessibletext" in l.lower() for l in lines[max(0, i - 3) : i + 3]
            ):
                issues.append(
                    f"Line {i}: Accessibility: Consider adding accessibleText for screen readers"
                )

        # Modern BrightScript features
        if 'createobject("roassociativearray")' in line_lower.replace(" ", ""):
            issues.append(
                f'Line {i}: Style: Use {{}} literal syntax instead of CreateObject("roAssociativeArray")'
            )

        if 'createobject("roarray")' in line_lower.replace(" ", ""):
            issues.append(
                f'Line {i}: Style: Use [] literal syntax instead of CreateObject("roArray")'
            )

    # Check for missing error handling
    if "http" in code.lower() or "url" in code.lower():
        if not any(
            error_check in code.lower()
            for error_check in ["iserror", "isfail", "error"]
        ):
            issues.append("Warning: Network operations should include error handling")

    # Certification blocker: in-app ECP commands are prohibited (Roku OS 14.1+)
    if ":8060/" in code.lower() or "/query/keypress" in code.lower():
        issues.append(
            "Error: In-app ECP commands are prohibited - apps that issue ECP "
            "commands from channel code are automatically blocked from "
            "publishing to the Streaming Store"
        )

    # Certification requirement (effective Oct 1, 2026): roAppMemoryMonitor
    if re.search(r"(sub|function)\s*main\s*\(", code, re.IGNORECASE):
        if "roappmemorymonitor" not in code.lower():
            issues.append(
                "Warning: Main.brs does not integrate roAppMemoryMonitor - this "
                "is required to pass certification as of October 1, 2026"
            )

    # Check for HDR/4K considerations
    if "video" in code.lower():
        if not any(
            hdr_check in code.lower()
            for hdr_check in ["hdr", "dolbyvision", "4k", "uhd"]
        ):
            issues.append(
                "Info: Consider adding HDR/4K support for modern Roku devices"
            )

    if not issues:
        return "BrightScript linting passed. Code follows modern Roku development practices."

    errors = [i for i in issues if i.startswith("Error")]
    warnings = [i for i in issues if i.startswith("Warning") or i.startswith("Performance")]
    infos = [i for i in issues if not (i.startswith("Error") or i.startswith("Warning") or i.startswith("Performance"))]

    response = "BrightScript linting found issues:\n"
    for label, group in (("Errors", errors), ("Warnings", warnings), ("Info", infos)):
        if group:
            response += f"{label}:\n" + "\n".join(f"  - {i}" for i in group) + "\n"
    return response


async def validate_scenegraph_component(
    component_path: str, check_accessibility: bool = True
) -> str:
    issues = []

    # Check if the component is a valid SceneGraph component
    if not os.path.exists(component_path):
        return "Error: Component path does not exist."

    # Perform accessibility checks if required (reported as warnings)
    if check_accessibility:
        accessibility_issues = await check_accessibility_compliance(component_path)
        issues.extend(accessibility_issues)

    if issues:
        return "SceneGraph component validation passed with warnings:\n" + "\n".join(
            f"  - {issue}" for issue in issues
        )
    return "SceneGraph component validation passed."


async def check_accessibility_compliance(component_path: str) -> list:
    issues = []

    try:
        with open(component_path, "r", encoding="utf-8") as f:
            content = f.read()

        # accessibleText may be set either in XML markup or in the
        # component's BrightScript Init() function - check both.
        brs_path = os.path.splitext(component_path)[0] + ".brs"
        brs_content = ""
        if os.path.exists(brs_path):
            with open(brs_path, "r", encoding="utf-8") as f:
                brs_content = f.read()

        content_lower = (content + "\n" + brs_content).lower()

        # Roku accessibility is exposed via the accessibleText field on
        # Screen Reader-readable nodes (Labels, Buttons, Posters, etc.)
        if "accessibletext" not in content_lower:
            issues.append(
                "Accessibility: No accessibleText field found - add accessibleText "
                "to interactive/text nodes so Roku's screen reader can announce them."
            )

        # Interactive nodes should be focusable for remote navigation
        # (match real SceneGraph node tags, not substrings like "buttons")
        if re.search(
            r"<(button|keyboard|rowlist|markupgrid|arraygrid)\b",
            content_lower,
        ) and 'focusable="true"' not in content_lower:
            issues.append(
                "Accessibility: Interactive elements should set focusable=\"true\" "
                "so they can receive remote-control focus."
            )

        # No ARIA roles on Roku - those are web concepts. Warn if present so
        # developers do not copy web patterns into SceneGraph XML.
        if 'role="' in content_lower:
            issues.append(
                "Accessibility: ARIA roles are a web concept - Roku uses the "
                "accessibleText field instead. Remove role=\"...\" attributes."
            )

    except Exception as e:
        issues.append(f"Error reading component file: {str(e)}")

    return issues


async def validate_roku_project(
    project_dir: str, check_certification: bool = True
) -> str:
    issues = []
    warnings = []

    # Check if the project directory exists
    if not os.path.exists(project_dir):
        return "Error: Project directory does not exist."

    # Check for required files
    required_files = ["manifest", "source", "components"]
    for file in required_files:
        if not os.path.exists(os.path.join(project_dir, file)):
            issues.append(f"Missing required directory: {file}")

    # Validate manifest file
    manifest_path = os.path.join(project_dir, "manifest")
    if not os.path.exists(manifest_path):
        issues.append("Missing manifest file.")
    else:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_content = f.read()
        manifest_validation = validate_roku_manifest(manifest_content)
        if "failed" in manifest_validation.lower():
            issues.append(manifest_validation)
        elif "warnings" in manifest_validation.lower():
            warnings.append(manifest_validation)
    # Check for SceneGraph components
    components_dir = os.path.join(project_dir, "components")
    if os.path.exists(components_dir):
        for root, _, files in os.walk(components_dir):
            for file in files:
                if file.endswith(".xml"):
                    component_path = os.path.join(root, file)
                    validation_result = await validate_scenegraph_component(
                        component_path
                    )
                    if "failed" in validation_result.lower():
                        issues.append(
                            f"Component {file} validation failed: {validation_result}"
                        )
                    elif "warnings" in validation_result.lower():
                        warnings.append(
                            f"Component {file} validation passed with warnings: {validation_result}"
                        )
                elif file.endswith(".brs"):
                    # Check for BrightScript files in components
                    brs_path = os.path.join(root, file)
                    with open(brs_path, "r", encoding="utf-8") as f:
                        brs_content = f.read()
                    lint_result = lint_brightscript(brs_content)
                    # Only linting Errors fail the project; Warnings/Info are
                    # surfaced separately below.
                    if re.search(r"^Errors:", lint_result, re.MULTILINE):
                        issues.append(
                            f"BrightScript linting for {file} found errors: {lint_result}"
                        )
                    elif "found issues" in lint_result.lower():
                        warnings.append(
                            f"BrightScript linting for {file} found warnings: {lint_result}"
                        )

    if check_certification:
        # Certification requirement (as of October 1, 2026): every app must
        # integrate roAppMemoryMonitor, or Static Analysis blocks publishing.
        memory_monitor_integrated = False
        source_dir = os.path.join(project_dir, "source")
        brs_paths = []
        for root, _, files in os.walk(project_dir):
            brs_paths.extend(
                os.path.join(root, f) for f in files if f.endswith((".brs", ".bs"))
            )
        for brs_path in brs_paths:
            try:
                with open(brs_path, "r", encoding="utf-8") as f:
                    code = f.read().lower()
                if "roappmemorymonitor" in code or "enablememorywarningevent" in code:
                    memory_monitor_integrated = True
                # In-app ECP commands are prohibited (Roku OS 14.1+): issuing
                # ECP requests from app code blocks Streaming Store publishing.
                if ":8060/" in code or "/query/keypress" in code:
                    issues.append(
                        f"{os.path.relpath(brs_path, project_dir)}: In-app ECP "
                        "commands are prohibited - Static Analysis blocks apps "
                        "that issue ECP commands from channel code."
                    )
            except (OSError, UnicodeDecodeError):
                continue
        if not memory_monitor_integrated:
            issues.append(
                "Certification blocker (effective Oct 1, 2026): no roAppMemoryMonitor "
                "integration found. All apps must call EnableMemoryWarningEvent() and "
                "handle roAppMemoryNotificationEvent, or use the "
                "generate_memory_monitor tool."
            )

    if issues:
        response = "Project validation failed:\n" + "\n".join(
            f"  - {issue}" for issue in issues
        )
        if warnings:
            response += "\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)
        return response
    if warnings:
        return (
            "Project validation passed with warnings:\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )
    return "Project validation passed. Structure, manifest, components, and certification checks are OK."


async def generate_component_registry(
    project_dir: str, output_file: str = "component_registry.txt"
) -> str:
    try:
        if not os.path.exists(project_dir):
            return "Error: Project directory does not exist."

        registry = []
        components_dir = os.path.join(project_dir, "components")

        if not os.path.exists(components_dir):
            return "Error: Components directory does not exist in the project."

        for root, _, files in os.walk(components_dir):
            for file in files:
                if file.endswith(".xml"):
                    component_path = os.path.join(root, file)
                    relative_path = os.path.relpath(component_path, project_dir)
                    registry.append(relative_path)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(registry))

        return f"Component registry generated at {output_file} with {len(registry)} components."

    except Exception as e:
        return f"Error generating component registry: {str(e)}"


async def package_roku_app(
    source_dir: str, output_path: str, exclude_dev_files: bool = True
) -> str:
    try:
        if not os.path.exists(source_dir):
            return "Error: Source directory does not exist."

        # Create a zip file for the Roku app package
        import zipfile

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    if exclude_dev_files and (
                        file.startswith(".") or file.endswith(".log")
                    ):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)

        return f"Roku app packaged successfully at {output_path}."

    except Exception as e:
        return f"Error packaging Roku app: {str(e)}"


async def create_modern_manifest(
    project_name: str, version: str = "1.0.0", output_path: str = "./manifest"
) -> str:
    try:
        # Parse semver into manifest fields (build_version must be numeric)
        version_parts = version.split(".")
        major = version_parts[0] if len(version_parts) > 0 and version_parts[0].isdigit() else "1"
        minor = version_parts[1] if len(version_parts) > 1 and version_parts[1].isdigit() else "0"
        build = version_parts[2] if len(version_parts) > 2 and version_parts[2].isdigit() else "1"
        # Clamp three-part versions: manifest build_version should stay numeric
        build = build.split("-")[0].split("+")[0]

        manifest_content = f"""title={project_name}
major_version={major}
minor_version={minor}
build_version={build}
mm_icon_focus_hd=pkg:/images/icon_hd.png
mm_icon_focus_sd=pkg:/images/icon_sd.png
splash_screen_hd=pkg:/images/splash_hd.jpg
splash_screen_sd=pkg:/images/splash_sd.jpg
splash_color=#000000
splash_min_time=1500
ui_resolutions=hd,fhd
supported_locales=en_US
channel_genre=Entertainment
parental_rating=G
privacy_policy=https://example.com/privacy
terms_of_service=https://example.com/terms
content_rating=TV-G
screensaver_title={project_name} Screensaver
supports_input_launch=true
channel_store_description=This is a modern Roku channel with all required fields for certification.
"""
        manifest_path = (
            output_path
            if os.path.splitext(os.path.basename(output_path))[1]
            or os.path.basename(output_path).lower() == "manifest"
            else os.path.join(output_path, "manifest")
        )
        manifest_dir = os.path.dirname(manifest_path)
        if manifest_dir:
            os.makedirs(manifest_dir, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_content)
        return f"Modern manifest created successfully at {manifest_path}."

    except Exception as e:
        return f"Error creating modern manifest: {str(e)}"


async def interactive_command_menu():
    from rich.prompt import Prompt, Confirm
    from rich.console import Group

    while True:
        console.clear()

        # Main menu options
        menu_options = {
            "1": ("🏗️ Create New Project", "create_project_wizard"),
            "2": ("📁 Analyze Existing Project", "analyze_project_wizard"),
            "3": ("🤖 Enter AI Automode", "automode_wizard"),
            "4": ("🛠️ Development Tools", "dev_tools_menu"),
            "5": ("⚙️ Settings & Configuration", "settings_menu"),
            "6": ("❓ Help & Documentation", "help_menu"),
            "7": ("💬 Free Chat Mode", "free_chat"),
            "0": ("🚪 Exit", "exit"),
        }

        # Display menu
        menu_table = Table(title="🚀 Roku Engineer - Main Menu", show_header=False)
        menu_table.add_column("Option", style="bold cyan", width=8)
        menu_table.add_column("Description", style="white")

        for key, (desc, _) in menu_options.items():
            menu_table.add_row(f"[{key}]", desc)

        console.print(menu_table)

        # Get user choice
        choice = Prompt.ask(
            "\n[bold]Select an option[/bold]",
            choices=list(menu_options.keys()),
            default="7",
        )

        if choice == "0":
            break
        elif choice == "1":
            await create_project_wizard()
        elif choice == "7":
            return  # Enter free chat mode
        # ... handle other options


async def create_project_wizard():
    console.print(Panel("🏗️ Project Creation Wizard", style="bold green"))

    project_name = Prompt.ask("Enter project name")
    project_type = Prompt.ask(
        "Select project type",
        choices=["basic", "video", "game", "screensaver"],
        default="basic",
    )

    include_analytics = Confirm.ask("Include analytics support?", default=True)
    include_accessibility = Confirm.ask("Include accessibility features?", default=True)

    # Create project with wizard settings
    console.print(f"Creating {project_type} project: {project_name}...")
    # Implementation here


async def decide_retry(tool_checker_response, edit_results, tool_input):
    try:
        if not edit_results:
            console.print(
                Panel(
                    "No edits were made or an error occurred. Skipping retry.",
                    title="Info",
                    style="bold yellow",
                )
            )
            return {"retry": False, "files_to_retry": []}

        files = tool_input.get("files", [])
        if isinstance(files, dict):
            files = [files]
        elif not isinstance(files, list):
            console.print(
                Panel(
                    "Error: 'files' must be a dictionary or a list of dictionaries.",
                    title="Error",
                    style="bold red",
                )
            )
            return {"retry": False, "files_to_retry": []}

        if not all(isinstance(item, dict) for item in files):
            console.print(
                Panel(
                    "Error: Each file must be a dictionary with 'path' and 'instructions'.",
                    title="Error",
                    style="bold red",
                )
            )
            return {"retry": False, "files_to_retry": []}

        valid_file_paths = set(file["path"] for file in files if file.get("path"))

        # Check if any edits failed or were partially successful
        failed_edits = any(
            result.get("status") == "partial_success"
            or result.get("status") == "no_changes"
            for result in edit_results
            if isinstance(result, dict)
        )
        retry_all = (
            "retry applying" in tool_checker_response.lower()
            or "apply the changes again" in tool_checker_response.lower()
        )

        if retry_all:
            files_to_retry = list(
                valid_file_paths
            )  # Retry all files if requested by the AI
        elif failed_edits:
            files_to_retry = [
                result["path"]
                for result in edit_results
                if isinstance(result, dict)
                and (
                    result.get("status") == "partial_success"
                    or result.get("status") == "no_changes"
                )
            ]

            # Additional Roku-specific check: if manifest was edited, always include main.brs
            if any("manifest" in path.lower() for path in files_to_retry):
                for file_path in valid_file_paths:
                    if (
                        "main.brs" in file_path.lower()
                        and file_path not in files_to_retry
                    ):
                        files_to_retry.append(file_path)
        else:
            files_to_retry = []

        retry_decision = {
            "retry": bool(files_to_retry),  # Retry only if there are files to retry
            "files_to_retry": files_to_retry,
        }

        console.print(
            Panel(
                f"Retry decision: {json.dumps(retry_decision, indent=2)}",
                title="Retry Decision",
                style="bold cyan",
            )
        )
        return retry_decision

    except Exception as e:
        console.print(
            Panel(f"Error in decide_retry: {str(e)}", title="Error", style="bold red")
        )
        return {"retry": False, "files_to_retry": []}


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = None
        is_error = False
        console_output = None

        if tool_name == "create_files":
            if isinstance(tool_input, dict) and "files" in tool_input:
                files = tool_input["files"]
            else:
                files = tool_input
            result = create_files(files)
        elif tool_name == "edit_and_apply_multiple":
            files = tool_input.get("files")
            if not files:
                result = "Error: 'files' key is missing or empty."
                is_error = True
            else:
                # Ensure 'files' is a list of dictionaries
                if isinstance(files, str):
                    try:
                        # Attempt to parse the JSON string
                        files = json.loads(files)
                        if isinstance(files, dict):
                            files = [files]
                        elif isinstance(files, list):
                            if not all(isinstance(file, dict) for file in files):
                                result = "Error: Each file must be a dictionary with 'path' and 'instructions'."
                                is_error = True
                    except json.JSONDecodeError:
                        result = "Error: 'files' must be a dictionary or a list of dictionaries, and should not be a string."
                        is_error = True
                elif isinstance(files, dict):
                    files = [files]
                elif isinstance(files, list):
                    if not all(isinstance(file, dict) for file in files):
                        result = "Error: Each file must be a dictionary with 'path' and 'instructions'."
                        is_error = True
                else:
                    result = (
                        "Error: 'files' must be a dictionary or a list of dictionaries."
                    )
                    is_error = True

                if not is_error:
                    # Validate the structure of 'files'
                    try:
                        files = validate_files_structure(files)
                    except ValueError as ve:
                        result = f"Error: {str(ve)}"
                        is_error = True

            if not is_error:
                result, console_output = await edit_and_apply_multiple(
                    files, tool_input["project_context"], is_automode=automode
                )
        elif tool_name == "create_folders":
            result = create_folders(tool_input["paths"])
        elif tool_name == "read_multiple_files":
            paths = tool_input.get("paths")
            recursive = tool_input.get("recursive", False)
            if paths is None:
                result = "Error: No file paths provided"
                is_error = True
            else:
                files_to_read = [
                    p
                    for p in (paths if isinstance(paths, list) else [paths])
                    if p not in file_contents
                ]
                if not files_to_read:
                    result = "All requested files are already in the system prompt. No need to read from disk."
                else:
                    result = read_multiple_files(files_to_read, recursive)
        elif tool_name == "list_files":
            result = list_files(tool_input.get("path", "."))
        elif tool_name == "validate_roku_manifest":
            result = validate_roku_manifest(tool_input["content"])
        elif tool_name == "lint_brightscript":
            result = lint_brightscript(tool_input["code"])
        elif tool_name == "tavily_search":
            result = tavily_search(tool_input["query"])
        elif tool_name == "execute_code":
            result = execute_code(tool_input["code"])
        elif tool_name == "scan_folder":
            result = scan_folder(tool_input["folder_path"], tool_input["output_file"])
        elif tool_name == "run_shell_command":
            result = run_shell_command(tool_input["command"])
        elif tool_name == "create_roku_project":
            result = await create_roku_project(
                tool_input["project_name"],
                tool_input.get("output_dir", "."),
                tool_input.get("project_type", "basic"),
            )
        elif tool_name == "create_roku_component":
            result = await create_roku_component(
                tool_input["component_type"],
                tool_input["name"],
                tool_input["output_dir"],
                tool_input.get("include_accessibility", True),
            )
        elif tool_name == "validate_roku_project":
            result = await validate_roku_project(
                tool_input["project_dir"], tool_input.get("check_certification", True)
            )
        elif tool_name == "generate_component_registry":
            result = await generate_component_registry(
                tool_input["project_dir"],
                tool_input.get("output_file", "component_registry.txt"),
            )
        elif tool_name == "generate_deep_link_handler":
            result = await generate_deep_link_handler(tool_input.get("project_dir", "."))
        elif tool_name == "generate_content_feed_handler":
            result = await generate_content_feed_handler(
                tool_input.get("project_dir", "."),
                tool_input.get("feed_type", "json"),
            )
        elif tool_name == "generate_raf_integration":
            result = await generate_raf_integration(tool_input.get("project_dir", "."))
        elif tool_name == "generate_memory_monitor":
            result = await generate_memory_monitor(tool_input.get("project_dir", "."))
        elif tool_name == "generate_websocket_handler":
            result = await generate_websocket_handler(tool_input.get("project_dir", "."))
        elif tool_name == "generate_sse_handler":
            result = await generate_sse_handler(tool_input.get("project_dir", "."))
        elif tool_name == "generate_roku_pay_integration":
            result = await generate_roku_pay_integration(
                tool_input.get("project_dir", ".")
            )
        elif tool_name == "validate_content_feed":
            result = validate_content_feed(tool_input["content"])
        elif tool_name == "get_roku_device_info":
            result = get_roku_device_info(tool_input["device_ip"])
        elif tool_name == "check_device_performance":
            result = check_device_performance(tool_input["device_ip"])
        elif tool_name == "capture_device_screenshot":
            result = capture_device_screenshot(
                tool_input["device_ip"],
                tool_input.get("username", "rokudev"),
                tool_input["password"],
                tool_input["output_path"],
            )
        elif tool_name == "capture_device_logs":
            result = capture_device_logs(
                tool_input["device_ip"],
                tool_input.get("duration_seconds", 10),
                tool_input.get("output_file"),
            )

        elif tool_name == "package_roku_app":
            result = await package_roku_app(
                tool_input["source_dir"],
                tool_input["output_path"],
                tool_input.get("exclude_dev_files", True),
            )
        elif tool_name == "create_modern_manifest":
            result = await create_modern_manifest(
                tool_input["project_name"],
                tool_input.get("version", "1.0.0"),
                tool_input.get("output_path", "./manifest"),
            )
        elif tool_name == "create_accessibility_helpers":
            result = create_accessibility_helpers(
                tool_input.get("output_path", "./source/AccessibilityHelpers.brs")
            )
        elif tool_name == "create_performance_monitoring":
            result = create_performance_monitoring(
                tool_input.get("output_path", "./source/PerformanceMonitoring.brs")
            )
        elif tool_name == "validate_scenegraph_component":
            result = await validate_scenegraph_component(
                tool_input["component_path"],
                tool_input.get("check_accessibility", True),
            )
        elif tool_name == "deploy_to_roku":
            result = await deploy_to_roku(
                tool_input["package_path"],
                tool_input["device_ip"],
                tool_input["password"],
                tool_input.get("username", "rokudev"),
            )
        elif tool_name == "validate_roku_component":
            result = await validate_roku_component(tool_input["component_path"])
        elif tool_name == "decide_retry":
            tool_checker_response = tool_input.get("tool_checker_response", "")
            edit_results = tool_input.get("edit_results", [])
            result = await decide_retry(tool_checker_response, edit_results, tool_input)
        else:
            is_error = True
            result = f"Unknown tool: {tool_name}"

        return {"content": result, "console_output": console_output}
    except KeyError as e:
        logging.error(f"Missing required parameter {str(e)} for tool {tool_name}")
        return {
            "content": f"Error: Missing required parameter {str(e)} for tool {tool_name}",
            "is_error": True,
            "console_output": None,
        }
    except Exception as e:
        logging.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            "content": f"Error executing tool {tool_name}: {str(e)}",
            "is_error": True,
            "console_output": None,
        }


async def chat_with_yuki(
    user_input, image_path=None, current_iteration=None, max_iterations=None
):
    global conversation_history, automode, main_model_tokens, use_tts, tts_enabled

    if client is None:
        return "Set ANTHROPIC_API_KEY to enable Yuki chat. Local project tools remain available.", False

    # Input validation
    if not isinstance(user_input, str):
        raise ValueError("user_input must be a string")
    if image_path is not None and not isinstance(image_path, str):
        raise ValueError("image_path must be a string or None")
    if current_iteration is not None and not isinstance(current_iteration, int):
        raise ValueError("current_iteration must be an integer or None")
    if max_iterations is not None and not isinstance(max_iterations, int):
        raise ValueError("max_iterations must be an integer or None")

    current_conversation = []

    if image_path:
        console.print(
            Panel(
                f"Processing image at path: {image_path}",
                title_align="left",
                title="Image Processing",
                expand=False,
                style="yellow",
            )
        )
        image_base64 = encode_image_to_base64(image_path)

        if image_base64.startswith("Error"):
            console.print(
                Panel(
                    f"Error encoding image: {image_base64}",
                    title="Error",
                    style="bold red",
                )
            )
            return (
                "I'm sorry, there was an error processing the image. Please try again.",
                False,
            )

        image_message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": f"User input for image: {user_input}"},
            ],
        }
        current_conversation.append(image_message)
        console.print(
            Panel(
                "Image message added to conversation history",
                title_align="left",
                title="Image Added",
                style="green",
            )
        )
    else:
        current_conversation.append({"role": "user", "content": user_input})

    # Filter conversation history to maintain context
    filtered_conversation_history = []
    for message in conversation_history:
        if isinstance(message["content"], list):
            filtered_content = [
                content
                for content in message["content"]
                if content.get("type") != "tool_result"
                or (
                    content.get("type") == "tool_result"
                    and not any(
                        keyword in content.get("output", "")
                        for keyword in [
                            "File contents updated in system prompt",
                            "File created and added to system prompt",
                            "has been read and stored in the system prompt",
                        ]
                    )
                )
            ]
            if filtered_content:
                filtered_conversation_history.append(
                    {**message, "content": filtered_content}
                )
        else:
            filtered_conversation_history.append(message)

    # Combine filtered history with current conversation to maintain context
    messages = filtered_conversation_history + current_conversation

    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            # MAINMODEL call with prompt caching
            response = client.messages.create(
                model=MAINMODEL,
                max_tokens=8000,
                **get_thinking_params(MAINMODEL),
                system=[
                    {
                        "type": "text",
                        "text": update_system_prompt(current_iteration, max_iterations),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": json.dumps(tools),
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
            )
            # Update token usage for MAINMODEL
            main_model_tokens["input"] += response.usage.input_tokens
            main_model_tokens["output"] += response.usage.output_tokens
            main_model_tokens["cache_write"] = (
                response.usage.cache_creation_input_tokens
            )
            main_model_tokens["cache_read"] = response.usage.cache_read_input_tokens
            break  # If successful, break out of the retry loop
        except APIStatusError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                console.print(
                    Panel(
                        f"Rate limit exceeded. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})",
                        title="API Error",
                        style="bold yellow",
                    )
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                console.print(
                    Panel(f"API Error: {str(e)}", title="API Error", style="bold red")
                )
                return (
                    "I'm sorry, there was an error communicating with the AI. Please try again.",
                    False,
                )
        except APIError as e:
            console.print(
                Panel(f"API Error: {str(e)}", title="API Error", style="bold red")
            )
            return (
                "I'm sorry, there was an error communicating with the AI. Please try again.",
                False,
            )
    else:
        console.print(
            Panel(
                "Max retries reached. Unable to communicate with the AI.",
                title="Error",
                style="bold red",
            )
        )
        return (
            "I'm sorry, there was a persistent error communicating with the AI. Please try again later.",
            False,
        )

    assistant_response = ""
    exit_continuation = False
    tool_uses = []

    for content_block in response.content:
        if content_block.type == "text":
            assistant_response += content_block.text
            if CONTINUATION_EXIT_PHRASE in content_block.text:
                exit_continuation = True
        elif content_block.type == "tool_use":
            tool_uses.append(content_block)

    console.print(
        Panel(
            Markdown(assistant_response),
            title="Yuki's Response",
            title_align="left",
            border_style="blue",
            expand=False,
        )
    )

    if tts_enabled and use_tts:
        await text_to_speech(assistant_response)

    # Display files in context
    if file_contents:
        files_in_context = "\n".join(file_contents.keys())
    else:
        files_in_context = "No files in context. Read, create, or edit files to add."
    console.print(
        Panel(
            files_in_context,
            title="Files in Context",
            title_align="left",
            border_style="white",
            expand=False,
        )
    )

    for tool_use in tool_uses:
        tool_name = tool_use.name
        tool_input = tool_use.input
        tool_use_id = tool_use.id

        console.print(Panel(f"Tool Used: {tool_name}", style="green"))
        console.print(
            Panel(f"Tool Input: {json.dumps(tool_input, indent=2)}", style="green")
        )

        # Always use execute_tool for all tools
        tool_result = await execute_tool(tool_name, tool_input)

        if isinstance(tool_result, dict) and tool_result.get("is_error"):
            console.print(
                Panel(
                    tool_result["content"],
                    title="Tool Execution Error",
                    style="bold red",
                )
            )
            edit_results = []  # Assign empty list due to error
        else:
            # Assuming tool_result["content"] is a list of results
            edit_results = tool_result.get("content", [])

        # Prepare the tool_result_content for conversation history
        tool_result_content = {
            "type": "text",
            "text": (
                json.dumps(tool_result)
                if isinstance(tool_result, (dict, list))
                else str(tool_result)
            ),
        }

        current_conversation.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": tool_name,
                        "input": tool_input,
                    }
                ],
            }
        )

        current_conversation.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": [tool_result_content],
                        "is_error": (
                            tool_result.get("is_error", False)
                            if isinstance(tool_result, dict)
                            else False
                        ),
                    }
                ],
            }
        )

        # Update the file_contents dictionary if applicable
        if tool_name in [
            "create_files",
            "edit_and_apply_multiple",
            "read_multiple_files",
        ] and not (isinstance(tool_result, dict) and tool_result.get("is_error")):
            if tool_name == "create_files":
                for file in tool_input["files"]:
                    if "File created and added to system prompt" in str(tool_result):
                        file_contents[file["path"]] = file["content"]
            elif tool_name == "edit_and_apply_multiple":
                edit_results = (
                    tool_result if isinstance(tool_result, list) else [tool_result]
                )
                for result in edit_results:
                    if isinstance(result, dict) and result.get("status") in [
                        "success",
                        "partial_success",
                    ]:
                        file_contents[result["path"]] = result.get(
                            "edited_content", file_contents.get(result["path"], "")
                        )
            elif tool_name == "read_multiple_files":
                # The file_contents dictionary is already updated in the read_multiple_files function
                pass

        messages = filtered_conversation_history + current_conversation

        try:
            tool_response = client.messages.create(
                model=TOOLCHECKERMODEL,
                max_tokens=8000,
                **get_thinking_params(TOOLCHECKERMODEL),
                system=update_system_prompt(current_iteration, max_iterations),
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
            )
            # Update token usage for tool checker
            tool_checker_tokens["input"] += tool_response.usage.input_tokens
            tool_checker_tokens["output"] += tool_response.usage.output_tokens

            tool_checker_response = ""
            for tool_content_block in tool_response.content:
                if tool_content_block.type == "text":
                    tool_checker_response += tool_content_block.text
            console.print(
                Panel(
                    Markdown(tool_checker_response),
                    title="Yuki's Response to Tool Result",
                    title_align="left",
                    border_style="blue",
                    expand=False,
                )
            )
            if use_tts:
                await text_to_speech(tool_checker_response)
            assistant_response += "\n\n" + tool_checker_response

            # If the tool was edit_and_apply_multiple, let the AI decide whether to retry
            if tool_name == "edit_and_apply_multiple":
                retry_decision = await decide_retry(
                    tool_checker_response, edit_results, tool_input
                )
                if retry_decision["retry"] and retry_decision["files_to_retry"]:
                    console.print(
                        Panel(
                            f"AI has decided to retry editing for files: {', '.join(retry_decision['files_to_retry'])}",
                            style="yellow",
                        )
                    )
                    retry_files = [
                        file
                        for file in tool_input["files"]
                        if file["path"] in retry_decision["files_to_retry"]
                    ]

                    # Ensure 'instructions' are present
                    for file in retry_files:
                        if "instructions" not in file:
                            file["instructions"] = (
                                "Please reapply the previous instructions."
                            )

                    if retry_files:
                        retry_result, retry_console_output = (
                            await edit_and_apply_multiple(
                                retry_files, tool_input["project_context"]
                            )
                        )
                        console.print(
                            Panel(
                                retry_console_output, title="Retry Result", style="cyan"
                            )
                        )
                        assistant_response += (
                            f"\n\nRetry result: {json.dumps(retry_result, indent=2)}"
                        )
                    else:
                        console.print(
                            Panel("No files to retry. Skipping retry.", style="yellow")
                        )
                else:
                    console.print(
                        Panel("Yuki has decided not to retry editing", style="green")
                    )

        except APIError as e:
            error_message = f"Error in tool response: {str(e)}"
            console.print(Panel(error_message, title="Error", style="bold red"))
            assistant_response += f"\n\n{error_message}"

    if assistant_response:
        current_conversation.append(
            {"role": "assistant", "content": assistant_response}
        )

    conversation_history = messages + [
        {"role": "assistant", "content": assistant_response}
    ]

    # Display token usage at the end
    display_token_usage()

    return assistant_response, exit_continuation


def reset_code_editor_memory():
    global code_editor_memory
    code_editor_memory = []
    console.print(
        Panel("Code editor memory has been reset.", title="Reset", style="bold green")
    )


def reset_conversation():
    global conversation_history, main_model_tokens, tool_checker_tokens, code_editor_tokens, code_execution_tokens, file_contents, code_editor_files
    conversation_history = []
    main_model_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    tool_checker_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    code_editor_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    code_execution_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    file_contents = {}
    code_editor_files = set()
    reset_code_editor_memory()
    console.print(
        Panel(
            "Conversation history, token counts, file contents, code editor memory, and code editor files have been reset.",
            title="Reset",
            style="bold green",
        )
    )
    display_token_usage()


def display_token_usage():
    from rich.table import Table
    from rich.panel import Panel
    from rich.box import ROUNDED

    table = Table(box=ROUNDED)
    table.add_column("Model", style="cyan")
    table.add_column("Input", style="magenta")
    table.add_column("Output", style="magenta")
    table.add_column("Cache Write", style="blue")
    table.add_column("Cache Read", style="blue")
    table.add_column("Total", style="green")
    table.add_column(f"% of Context ({MAX_CONTEXT_TOKENS:,})", style="yellow")
    table.add_column("Cost ($)", style="red")

    model_costs = {
        "Main Model": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
            "has_context": True,
        },
        "Tool Checker": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
            "has_context": False,
        },
        "Code Editor": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
            "has_context": True,
        },
        "Code Execution": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
            "has_context": False,
        },
    }

    total_input = 0
    total_output = 0
    total_cache_write = 0
    total_cache_read = 0
    total_cost = 0
    total_context_tokens = 0

    for model, tokens in [
        ("Main Model", main_model_tokens),
        ("Tool Checker", tool_checker_tokens),
        ("Code Editor", code_editor_tokens),
        ("Code Execution", code_execution_tokens),
    ]:
        input_tokens = tokens["input"]
        output_tokens = tokens["output"]
        cache_write_tokens = tokens["cache_write"]
        cache_read_tokens = tokens["cache_read"]
        total_tokens = (
            input_tokens + output_tokens + cache_write_tokens + cache_read_tokens
        )

        total_input += input_tokens
        total_output += output_tokens
        total_cache_write += cache_write_tokens
        total_cache_read += cache_read_tokens

        input_cost = (input_tokens / 1_000_000) * model_costs[model]["input"]
        output_cost = (output_tokens / 1_000_000) * model_costs[model]["output"]
        cache_write_cost = (cache_write_tokens / 1_000_000) * model_costs[model][
            "cache_write"
        ]
        cache_read_cost = (cache_read_tokens / 1_000_000) * model_costs[model][
            "cache_read"
        ]
        model_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
        total_cost += model_cost

        if model_costs[model]["has_context"]:
            total_context_tokens += total_tokens
            percentage = (total_tokens / MAX_CONTEXT_TOKENS) * 100
        else:
            percentage = 0

        table.add_row(
            model,
            f"{input_tokens:,}",
            f"{output_tokens:,}",
            f"{cache_write_tokens:,}",
            f"{cache_read_tokens:,}",
            f"{total_tokens:,}",
            (
                f"{percentage:.2f}%"
                if model_costs[model]["has_context"]
                else "Doesn't save context"
            ),
            f"${model_cost:.3f}",
        )

    grand_total = total_input + total_output + total_cache_write + total_cache_read
    total_percentage = (total_context_tokens / MAX_CONTEXT_TOKENS) * 100

    table.add_row(
        "Total",
        f"{total_input:,}",
        f"{total_output:,}",
        f"{total_cache_write:,}",
        f"{total_cache_read:,}",
        f"{grand_total:,}",
        f"{total_percentage:.2f}%",
        f"${total_cost:.3f}",
        style="bold",
    )

    console.print(table)


def display_smart_menu():
    from datetime import datetime
    from rich.table import Table

    roku_ascii = """
╦═╗╔═╗╦╔═╦ ╦  ╔═╗╔╗╔╔═╗╦╔╗╔╔═╗╔═╗╦═╗
╠╦╝║ ║╠╩╗║ ║  ║╣ ║║║║ ╦║║║║║╣ ║╣ ╠╦╝
╩╚═╚═╝╩ ╩╚═╝  ╚═╝╝╚╝╚═╝╩╝╚╝╚═╝╚═╝╩╚═
    """
    # Analyze current context
    has_project = any(".brs" in f or ".xml" in f for f in file_contents.keys())
    has_manifest = any("manifest" in f.lower() for f in file_contents.keys())

    # Dynamic greeting based on time
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # Context-aware welcome
    welcome_text = f"[bold cyan]{greeting}! Welcome to Roku Engineer[/bold cyan]\n"
    console.print(f"[bold magenta]{roku_ascii}[/bold magenta]")
    console.print(
        "[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]"
    )
    console.print(
        "[bold white]🎬 Professional Roku Channel Development Suite[/bold white]"
    )
    console.print(
        "[dim]Powered by Claude Sonnet 4 AI • Modern BrightScript • SceneGraph[/dim]"
    )
    console.print(
        "[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n"
    )

    if has_project:
        welcome_text += "[green]✓ Project detected in context[/green]\n"
        if has_manifest:
            welcome_text += "[green]✓ Manifest file loaded[/green]\n"
        welcome_text += f"[dim]Working with {len(file_contents)} files[/dim]"
    else:
        welcome_text += (
            "[yellow]No project in context - ready to create or import[/yellow]"
        )

    console.print(Panel(welcome_text, title="🚀 Smart Assistant", border_style="blue"))

    # Suggest next actions based on context
    if has_project:
        suggestions = [
            "💡 Validate your project structure",
            "🔍 Lint your BrightScript code",
            "📦 Package for deployment",
            "🤖 Use automode for enhancements",
        ]
    else:
        suggestions = [
            "🏗️ Create a new Roku project",
            "📁 Import existing project files",
            "📚 Browse Roku development examples",
            "❓ Ask questions about Roku development",
        ]

    suggestions_text = "\n".join(f"  {suggestion}" for suggestion in suggestions)
    console.print(Panel(suggestions_text, title="💡 Suggested Next Steps", style="dim"))

    # Quick command reference
    quick_commands = Table(
        show_header=False, show_lines=False, padding=(0, 1), box=None
    )
    quick_commands.add_column(style="cyan")
    quick_commands.add_column(style="dim")
    quick_commands.add_row("Quick start:", "Just type what you want to do naturally!")
    quick_commands.add_row("Voice mode:", "Type 'voice' for hands-free interaction")
    quick_commands.add_row("Auto mode:", "Type 'automode' for AI-driven development")
    quick_commands.add_row("Help:", "Type 'help' or '?' for detailed assistance")

    console.print(Panel(quick_commands, title="⚡ Quick Commands", style="dim"))


def help_menu():
    help_text = """
    [bold cyan]Roku Engineer Help Menu[/bold cyan]
    
    [bold]General Commands:[/bold]
    - [green]help[/green]: Show this help menu
    - [green]exit[/green]: Exit the application
    - [green]reset[/green]: Reset conversation and context
    - [green]save chat[/green]: Save current chat to a file
    
    [bold]Voice Mode:[/bold]
    - [green]voice[/green]: Enter voice input mode
    - Say "exit voice mode" to return to text input
    
    [bold]Automode:[/bold]
    - [green]automode [max_iterations][/green]: Start AI-driven development with optional max iterations
    
    [bold]Text-to-Speech:[/bold]
    - [green]11labs on[/green]: Enable text-to-speech
    - [green]11labs off[/green]: Disable text-to-speech
    
    [bold]File Operations:[/bold]
    - Drag and drop files into the console to read them
    - Use commands like "create files", "edit files", etc. for file operations
    
    For more detailed assistance, please refer to the documentation or ask specific questions.
    """

    console.print(Panel(Markdown(help_text), title="Help Menu", style="blue"))


async def test_voice_mode():
    global voice_mode
    voice_mode = True
    initialize_speech_recognition()
    console.print(
        Panel(
            "Entering voice input test mode. Say a few phrases, then say 'exit voice mode' to end the test.",
            style="bold green",
        )
    )

    while voice_mode:
        user_input = await voice_input()
        if user_input is None:
            voice_mode = False
            cleanup_speech_recognition()
            console.print(
                Panel("Exited voice input test mode due to error.", style="bold yellow")
            )
            break

        stay_in_voice_mode, command_result = process_voice_command(user_input)
        if not stay_in_voice_mode:
            voice_mode = False
            cleanup_speech_recognition()
            console.print(Panel("Exited voice input test mode.", style="bold green"))
            break
        elif command_result:
            console.print(Panel(command_result, style="cyan"))

    console.print(Panel("Voice input test completed.", style="bold green"))


async def main():
    global automode, conversation_history, use_tts, tts_enabled

    display_smart_menu()

    voice_mode = False

    while True:
        if voice_mode:
            user_input = await voice_input()
            if user_input is None:
                voice_mode = False
                cleanup_speech_recognition()
                console.print(
                    Panel(
                        "Exited voice input mode due to error. Returning to text input.",
                        style="bold yellow",
                    )
                )
                continue

            stay_in_voice_mode, command_result = process_voice_command(user_input)
            if not stay_in_voice_mode:
                voice_mode = False
                cleanup_speech_recognition()
                console.print(
                    Panel(
                        "Exited voice input mode. Returning to text input.",
                        style="bold green",
                    )
                )
                if command_result:
                    console.print(Panel(command_result, style="cyan"))
                continue
            elif command_result:
                console.print(Panel(command_result, style="cyan"))
                continue
        else:
            user_input = await get_user_input()

        if user_input.lower() == "exit":
            console.print(
                Panel(
                    "Thank you for chatting. Goodbye!",
                    title_align="left",
                    title="Goodbye",
                    style="bold green",
                )
            )
            break

        if user_input.lower() == "help" or user_input.lower() == "?":
            help_menu()
            continue

        if user_input.lower() == "display interactive menu":
            await interactive_command_menu()
            continue

        if user_input.lower() == "reset code editor":
            reset_code_editor_memory()
            continue

        if user_input.lower() == "test voice":
            await test_voice_mode()
            continue

        if user_input.lower() == "11labs on":
            use_tts = True
            tts_enabled = True
            console.print(Panel("Text-to-speech enabled.", style="bold green"))
            continue

        if user_input.lower() == "11labs off":
            use_tts = False
            tts_enabled = False
            console.print(Panel("Text-to-speech disabled.", style="bold yellow"))
            continue

        if user_input.lower() == "reset":
            reset_conversation()
            continue

        if user_input.lower() == "save chat":
            filename = save_chat()
            console.print(
                Panel(
                    f"Chat saved to {filename}", title="Chat Saved", style="bold green"
                )
            )
            continue

        if user_input.lower() == "voice":
            voice_mode = True
            initialize_speech_recognition()
            console.print(
                Panel(
                    "Entering voice input mode. Say 'exit voice mode' to return to text input.",
                    style="bold green",
                )
            )
            continue

        if user_input.lower() == "image":
            image_path = (
                (
                    await get_user_input(
                        "Drag and drop your image here, then press enter: "
                    )
                )
                .strip()
                .replace("'", "")
            )

            if os.path.isfile(image_path):
                user_input = await get_user_input("You (prompt for image): ")
                response, _ = await chat_with_yuki(user_input, image_path)
            else:
                console.print(
                    Panel(
                        "Invalid image path. Please try again.",
                        title="Error",
                        style="bold red",
                    )
                )
                continue
        elif user_input.lower().startswith("automode"):
            try:
                parts = user_input.split()
                max_iterations = (
                    int(parts[1])
                    if len(parts) > 1 and parts[1].isdigit()
                    else MAX_CONTINUATION_ITERATIONS
                )

                automode = True
                console.print(
                    Panel(
                        f"Entering automode with {max_iterations} iterations.  Please provide the initial goal.",
                        title_align="left",
                        title="Automode",
                        style="bold yellow",
                    )
                )
                console.print(
                    Panel(
                        "Press Ctrl+C at any time to exit automode.",
                        style="bold yellow",
                    )
                )
                user_input = await get_user_input()

                iteration_count = 0
                error_count = 0
                max_errors = 3

                while automode and iteration_count < max_iterations:
                    try:
                        response, exit_continuation = await chat_with_yuki(
                            user_input,
                            current_iteration=iteration_count + 1,
                            max_iterations=max_iterations,
                        )
                        error_count = 0
                    except Exception as e:
                        console.print(
                            Panel(
                                f"Error in automode iteration {iteration_count+1}: {str(e)}",
                                style="bold red",
                            )
                        )
                        error_count += 1
                        if error_count >= max_errors:
                            console.print(
                                Panel(
                                    f"Exiting automode due to {max_errors} consecutive errors.",
                                    style="bold red",
                                )
                            )
                            automode = False
                            break
                        continue

                    if exit_continuation or CONTINUATION_EXIT_PHRASE in response:
                        console.print(
                            Panel(
                                "Automode completed.",
                                title_align="left",
                                title="Automode",
                                style="green",
                            )
                        )
                        automode = False
                    else:
                        console.print(
                            Panel(
                                f"Iteration {iteration_count + 1}/{max_iterations} completed.  Provide next instructions or type 'AUTOMODE_COMPLETE' to exit.",
                                title_align="left",
                                title="Automode",
                                style="yellow",
                            )
                        )
                        user_input = (
                            await get_user_input()
                        )  # Get next instruction from user.
                    iteration_count += 1

                if iteration_count >= max_iterations:
                    console.print(
                        Panel(
                            "Max iterations reached. Exiting automode.",
                            title_align="left",
                            title="Automode",
                            style="bold red",
                        )
                    )
                    automode = False
            except KeyboardInterrupt:
                console.print(
                    Panel(
                        "\nAutomode interrupted by user. Exiting automode.",
                        title_align="left",
                        title="Automode",
                        style="bold red",
                    )
                )
                automode = False
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": "Automode interrupted. How can I assist you further?",
                        }
                    )

            console.print(
                Panel("Exited automode. Returning to regular chat.", style="green")
            )
        else:
            response, _ = await chat_with_yuki(user_input)


SCENEGRAPH_TEMPLATES = {
    "Scene": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Scene">
    <interface>
        <field id="contentReady" type="boolean" alwaysNotify="true" />
        <field id="errorMessage" type="string" alwaysNotify="true" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
    <children>
        <!-- Background -->
        <Rectangle 
            id="background"
            width="1920" 
            height="1080" 
            color="0x000000FF" />
        
        <!-- Main Content Group -->
        <Group id="mainContent" translation="[0,0]">
            <!-- Add child components here -->
        </Group>
        
        <!-- Loading Spinner -->
        <BusySpinner 
            id="loadingSpinner"
            poster="pkg:/images/loading.png"
            visible="false"
            translation="[960,540]" />
    </children>
</component>""",
    "Task": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Task">
    <interface>
        <field id="input" type="assocarray" />
        <field id="output" type="assocarray" />
        <field id="error" type="string" />
        <field id="progress" type="float" value="0.0" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
    "CustomList": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Group">
    <interface>
        <field id="itemContent" type="node" />
        <field id="focusedIndex" type="integer" value="0" />
        <field id="selectedIndex" type="integer" value="-1" alwaysNotify="true" />
        <field id="accessibleText" type="string" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
    <children>
        <RowList 
            id="rowList"
            translation="[0,0]"
            numRows="2"
            itemComponentName="CustomListItem"
            itemSize="[1920,200]"
            rowItemSize="[[440,180]]"
            showRowLabel="[true]"
            rowLabelOffset="[[0,20]]"
            rowFocusAnimationStyle="fixedFocusWrap"
            vertFocusAnimationStyle="fixedFocus" />
    </children>
</component>""",
    "GridView": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="GridPanel">
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
    "DetailsView": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="DetailsView">
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
    "MediaView": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="MediaView">
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
    "ErrorView": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="EntitlementView">
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
    "VideoPlayer": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Group">
    <interface>
        <field id="content" type="node" />
        <field id="state" type="string" alwaysNotify="true" />
        <field id="position" type="float" alwaysNotify="true" />
        <field id="duration" type="float" />
        <field id="enableCaptions" type="boolean" value="true" />
        <field id="captionMode" type="string" value="On" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
    <children>
        <Video 
            id="videoPlayer"
            width="1920"
            height="1080"
            translation="[0,0]"
            enableDebugging="false"
            disableScreenSaver="true"
            EnableCookies="true"
            setCertificatesFile="common:/certs/ca-bundle.crt" />
    </children>
</component>""",
    "Effect": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Group">
    <interface>
        <field id="effectName" type="string" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
    <children>
        <!-- Background rectangle with a rounded-corner GPU effect (Roku OS 16.0+) -->
        <Rectangle
            id="effectRect"
            width="1920"
            height="1080"
            color="0x1A1A2EFF" />
        <Poster
            id="effectPoster"
            width="440"
            height="248"
            translation="[40, 40]"
            uri="pkg:/images/splash_hd.jpg" />
    </children>
</component>""",
    "WebSocketTask": """<?xml version="1.0" encoding="utf-8" ?>
<component name="{name}" extends="Task">
    <interface>
        <field id="url" type="string" />
        <field id="message" type="string" alwaysNotify="true" />
        <field id="connected" type="boolean" />
        <field id="error" type="string" />
    </interface>
    <script type="text/brightscript" uri="{script_uri}" />
</component>""",
}

BRIGHTSCRIPT_TEMPLATES = {
    "Scene": """function Init()
    ' Initialize scene variables
    m.top.backgroundURI = "pkg:/images/background.jpg"
    m.loadingSpinner = m.top.findNode("loadingSpinner")
    m.mainContent = m.top.findNode("mainContent")
    
    ' Set up accessibility
    m.top.accessibleText = "Main application scene"
    
    SetupUI()
    SetupEventListeners()
end function

function SetupUI()
    ' Initialize UI components
    ShowLoading(true)
    
    ' Load content asynchronously
    LoadContent()
end function

function SetupEventListeners()
    ' Set up field observers
    m.top.observeField("contentReady", "OnContentReady")
    m.top.observeField("errorMessage", "OnError")
end function

function LoadContent()
    ' Create task for content loading
    m.contentTask = CreateObject("roSGNode", "ContentTask")
    m.contentTask.observeField("content", "OnContentLoaded")
    m.contentTask.control = "RUN"
end function

function OnContentLoaded()
    if m.contentTask.content <> invalid
        m.top.contentReady = true
    else
        m.top.errorMessage = "Failed to load content"
    end if
end function

function OnContentReady()
    ShowLoading(false)
    ' Handle content ready state
end function

function OnError()
    ShowLoading(false)
    ' Handle error state
    ShowErrorDialog(m.top.errorMessage)
end function

function ShowLoading(show as Boolean)
    if m.loadingSpinner <> invalid
        m.loadingSpinner.visible = show
    end if
end function

function ShowErrorDialog(message as String)
    ' Create and show error dialog
    dialog = CreateObject("roSGNode", "Dialog")
    dialog.title = "Error"
    dialog.message = message
    dialog.buttons = ["OK"]
    m.top.dialog = dialog
end function

function OnKeyEvent(key as String, press as Boolean) as Boolean
    handled = false
    
    if press
        if key = "back"
            ' Handle back key with proper cleanup
            CleanupScene()
            handled = true
        else if key = "options"
            ' Handle options/settings
            ShowOptionsMenu()
            handled = true
        end if
    end if
    
    return handled
end function

function CleanupScene()
    ' Clean up observers and tasks
    if m.contentTask <> invalid
        m.contentTask.unobserveFieldsAll()
        m.contentTask.control = "STOP"
    end if
    
    m.top.unobserveFieldsAll()
end function

function ShowOptionsMenu()
    ' Show accessibility and settings options
end function""",
    "Task": """function Init()
    ' Initialize task
    m.top.functionName = "ExecuteTask"
    m.top.observeField("input", "OnInputChanged")
end function

function OnInputChanged()
    ' Handle input parameter changes
    if m.top.input <> invalid
        ' Process input and start execution
        m.top.control = "RUN"
    end if
end function

function ExecuteTask()
    try
        ' Update progress
        m.top.progress = 0.1
        
        ' Get input parameters
        input = m.top.input
        if input = invalid
            m.top.error = "Invalid input parameters"
            return
        end if
        
        ' Perform task operations
        result = ProcessData(input)
        
        ' Update progress
        m.top.progress = 0.8
        
        ' Set output
        if result <> invalid
            m.top.output = result
            m.top.progress = 1.0
        else
            m.top.error = "Failed to process data"
        end if
        
    catch error
        ' Handle errors gracefully
        m.top.error = "Task execution failed: " + error.message
    end try
end function

function ProcessData(input as Object) as Object
    ' Add your data processing logic here
    ' This is a placeholder implementation
    
    result = {}
    result.processed = true
    result.timestamp = CreateObject("roDateTime").asSeconds()
    
    return result
end function""",
    "CustomList": """function Init()
    m.rowList = m.top.findNode("rowList")
    SetupEventListeners()
    SetupAccessibility()
end function

function SetupEventListeners()
    m.rowList.observeField("itemSelected", "OnItemSelected")
    m.rowList.observeField("itemFocused", "OnItemFocused")
    m.top.observeField("itemContent", "OnContentChanged")
end function

function SetupAccessibility()
    ' Set up accessibility features
    m.top.accessibleText = "Content list with navigation support"
    m.rowList.accessibleText = "Select items using OK button"
end function

function OnContentChanged()
    if m.top.itemContent <> invalid
        m.rowList.content = m.top.itemContent
        
        ' Update accessibility text based on content
        UpdateAccessibilityText()
    end if
end function

function OnItemFocused()
    ' Handle item focus changes
    focusedItem = m.rowList.content.getChild(m.rowList.itemFocused)
    if focusedItem <> invalid
        m.top.focusedIndex = m.rowList.itemFocused
        
        ' Update accessibility announcement
        if focusedItem.title <> invalid
            announcement = "Focused on " + focusedItem.title
            AnnounceAccessibility(announcement)
        end if
    end if
end function

function OnItemSelected()
    ' Handle item selection
    selectedItem = m.rowList.content.getChild(m.rowList.itemSelected)
    if selectedItem <> invalid
        m.top.selectedIndex = m.rowList.itemSelected
        
        ' Announce selection for accessibility
        if selectedItem.title <> invalid
            announcement = "Selected " + selectedItem.title
            AnnounceAccessibility(announcement)
        end if
    end if
end function

function UpdateAccessibilityText()
    if m.rowList.content <> invalid
        itemCount = m.rowList.content.getChildCount()
        m.top.accessibleText = "List with " + itemCount.toStr() + " items"
    end if
end function

function AnnounceAccessibility(text as String)
    ' Create accessibility announcement
    ' This would integrate with Roku's accessibility features
end function""",
    "GridView": """sub Init()
    m.top.theme = {
        global: {
            backgroundColor: "0x000000FF",
            textColor: "0xFFFFFFFF"
        }
    }
end sub""",
    "DetailsView": """sub Init()
    ' details view init
end sub""",
    "MediaView": """sub Init()
    ' media view init
end sub""",
    "ErrorView": """sub Init()
    ' error view init
end sub""",
    "VideoPlayer": """function Init()
    m.video = m.top.findNode("videoPlayer")
    SetupVideoPlayer()
    SetupEventListeners()
end function

function SetupVideoPlayer()
    ' Configure video player for modern Roku devices
    m.video.EnableCookies = true
    m.video.setCertificatesFile("common:/certs/ca-bundle.crt")
    m.video.EnableAudioGuideTrack = true
    
    ' Enable HDR if supported
    if SupportsHDR()
        m.video.MaxVideoDecodeResolution = "3840x2160x60p"
    end if
    
    ' Set up captions
    m.video.GlobalCaptionMode = m.top.captionMode
    m.video.subtitleTrack = "1" ' Enable first subtitle track
end function

function SetupEventListeners()
    m.video.observeField("state", "OnVideoStateChanged")
    m.video.observeField("position", "OnPositionChanged")
    m.top.observeField("content", "OnContentChanged")
    m.top.observeField("enableCaptions", "OnCaptionSettingChanged")
end function

function OnContentChanged()
    if m.top.content <> invalid
        m.video.content = m.top.content
        
        ' Set accessibility text
        if m.top.content.title <> invalid
            m.top.accessibleText = "Now playing: " + m.top.content.title
        end if
    end if
end function

function OnVideoStateChanged()
    state = m.video.state
    m.top.state = state
    
    if state = "error"
        HandleVideoError()
    else if state = "finished"
        HandleVideoFinished()
    end if
end function

function OnPositionChanged()
    m.top.position = m.video.position
    
    ' Update duration if not set
    if m.top.duration = 0 and m.video.duration > 0
        m.top.duration = m.video.duration
    end if
end function

function OnCaptionSettingChanged()
    if m.top.enableCaptions
        m.video.GlobalCaptionMode = "On"
    else
        m.video.GlobalCaptionMode = "Off"
    end if
end function

function HandleVideoError()
    ' Handle video playback errors
    errorCode = m.video.errorCode
    errorMsg = m.video.errorMsg
    
    ' Log error for debugging
    print "Video Error: " + errorCode.toStr() + " - " + errorMsg
    
    ' Notify parent component
    m.top.error = errorMsg
end function

function HandleVideoFinished()
    ' Handle video completion
    m.top.position = m.top.duration
end function

function SupportsHDR() as Boolean
    ' Check if device supports HDR
    deviceInfo = CreateObject("roDeviceInfo")
    return deviceInfo.SupportsVideoMode("3840x2160x60p")
end function

function Play()
    m.video.control = "play"
end function

function Pause()
    m.video.control = "pause"
end function

function Stop()
    m.video.control = "stop"
end function

function Seek(position as Float)
    m.video.seek = position
end function""",
    "Effect": """sub Init()
    rect = m.top.findNode("effectRect")
    poster = m.top.findNode("effectPoster")

    ' The Effect node applies GPU-accelerated shader effects to Poster and
    ' Rectangle nodes (Roku OS 16.0+). Check the read-only "supported" field
    ' to detect platforms without a shader-capable GPU.
    rounded = CreateObject("roSGNode", "Effect")
    if rounded.supported
        rounded.borderRadius = [24]
        rounded.borderWidth = 4.0
        rounded.borderColor = "0x662D91FF"

        ' Optional gradient fill (at least 2, at most 8 colors)
        rounded.gradientStyle = "linear"
        rounded.gradientAngle = 45.0
        rounded.gradientColors = ["0x662D91FF", "0x1A1A2EFF"]

        rect.effect = rounded
        poster.effect = rounded
    end if
end sub""",
    "WebSocketTask": """function Init()
    m.top.functionName = "RunWebSocket"
end function

' roWebSocket event type constants (roWebSocketEvent.GetType())
sub SetWSEventConstants(m_ as Object)
    m_.OpenedEvent = 1
    m_.ClosedEvent = 2
    m_.ErrorEvent = 3
    m_.MsgSentEvent = 4
    m_.TextReceivedEvent = 5
    m_.DataReceivedEvent = 6
    m_.TimerEvent = 9
end sub

function RunWebSocket()
    SetWSEventConstants(m)
    port = CreateObject("roMessagePort")
    m.top.connected = false

    websocket = CreateObject("roWebSocket")
    websocket.setMessagePort(port)
    websocket.SetUrl(m.top.url)
    ' For secure (wss) connections, configure HTTPS parameters like roUrlTransfer
    websocket.SetCertificatesFile("common:/certs/ca-bundle.crt")

    if not websocket.Open(5000)
        m.top.error = "Failed to open WebSocket connection."
        return invalid
    end if
    m.top.connected = true

    while true
        msg = wait(0, port)
        if type(msg) = "roWebSocketEvent"
            event = msg.GetType()
            if event = m.TextReceivedEvent
                m.top.message = msg.GetInfo().Text
            else if event = m.ErrorEvent
                m.top.error = msg.GetInfo().ErrorMsg
                exit while
            else if event = m.ClosedEvent
                m.top.connected = false
                exit while
            end if
        else if type(msg) = "roSGNodeEvent"
            ' Task was stopped from outside - close cleanly
            websocket.Close()
            m.top.connected = false
            exit while
        end if
    end while
end function""",
}


async def _create_file_with_header(
    path: str, content: str, is_brightscript: bool = False
):
    """Helper function to create a file with an optional BrightScript header."""
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            if is_brightscript:
                header = (
                    "' *****************************************************************\n"
                    "' BrightScript file\n"
                    f"' Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    "' *****************************************************************\n\n"
                )
                f.write(header)
            f.write(content)
        return True, f"File created: {path}"
    except IOError as e:
        return False, f"I/O error creating file {path}: {e.strerror}"
    except Exception as e:
        return (
            False,
            f"An unexpected error occurred while creating file {path}: {str(e)}",
        )


async def generate_deep_link_handler(project_dir: str) -> Tuple[bool, str]:
    """Generate deep link handling logic in Main.brs and SceneGraph."""
    try:
        deep_link_brs = """' =====================================================================
' deeplinkUtils.brs - Deep link argument handling
' Certification requires handling both contentId and mediaType on launch
' (via Main args) and at runtime (via roInput deep link events).
' Supported media types: movie, episode, live, season, series, channel
' =====================================================================

function IsValidDeepLink(args as Dynamic) as Boolean
    if args = invalid
        return false
    end if
    if args.contentId = invalid or args.contentId = ""
        return false
    end if
    if args.mediaType = invalid
        return false
    end if
    validMediaTypes = ["movie", "episode", "live", "shortForm", "season", "series", "channel"]
    for each mediaType in validMediaTypes
        if LCase(args.mediaType) = mediaType
            return true
        end if
    end for
    return false
end function

sub InitDeepLink(globalNode as Object, args as Dynamic)
    ' Store deep link args on the screen's global node so any scene
    ' component can observe m.global.deepLinkArgs and route to content.
    if globalNode = invalid or not IsValidDeepLink(args)
        return
    end if
    if not globalNode.HasField("deepLinkArgs")
        globalNode.AddField("deepLinkArgs", "assocarray", false)
    end if
    globalNode.SetFields({
        deepLinkArgs: {
            contentId: args.contentId,
            mediaType: LCase(args.mediaType),
            mediaStartTime: args.mediaStartTime
        }
    })
end sub"""
        path = os.path.join(project_dir, "source", "deeplinkUtils.brs")
        success, msg = await _create_file_with_header(
            path, deep_link_brs, is_brightscript=True
        )
        return (
            success,
            "Deep link handler generated at "
            + path
            + ". Call InitDeepLink(screen.getGlobalNode(), args) from Main(args) and "
            + "from your roInputEvent handler, then observe m.global.deepLinkArgs in "
            + "your scene to route to the content specified by contentId + mediaType.",
        )
    except Exception as e:
        return False, f"Failed to generate deep link handler: {str(e)}"


async def generate_content_feed_handler(
    project_dir: str, feed_type: str = "json"
) -> Tuple[bool, str]:
    """Generate a Task component to parse JSON/MRSS feeds into a ContentNode tree."""
    try:
        success, msg = await create_roku_component(
            "Task", "ContentFeedTask", os.path.join(project_dir, "components")
        )
        if not success:
            return False, msg

        brs_path = os.path.join(project_dir, "components", "ContentFeedTask", "ContentFeedTask.brs")
        xml_path = os.path.join(project_dir, "components", "ContentFeedTask", "ContentFeedTask.xml")
        with open(xml_path, "r", encoding="utf-8") as xml_file:
            xml_content = xml_file.read().replace('id="output" type="assocarray"', 'id="output" type="node"')
        await _create_file_with_header(xml_path, xml_content)
        if feed_type == "json":
            parse_logic = """        jsonString = response
        if jsonString <> invalid and jsonString <> ""
            jsonObj = ParseJson(jsonString)
            if jsonObj <> invalid and jsonObj.items <> invalid
                root = CreateObject("roSGNode", "ContentNode")
                for each item in jsonObj.items
                    node = root.CreateChild("ContentNode")
                    node.title = item.title
                    node.description = item.description
                    node.HDPosterUrl = item.thumbnail
                end for
                m.top.output = root
            else
                m.top.error = "Failed to parse JSON feed"
            end if
        else
            m.top.error = "Empty response from feed URL"
        end if"""
        else:
            parse_logic = """        xmlString = response
        if xmlString <> invalid and xmlString <> ""
            xmlObj = CreateObject("roXMLElement")
            if xmlObj.Parse(xmlString)
                root = CreateObject("roSGNode", "ContentNode")
                for each item in xmlObj.GetBody()
                    node = root.CreateChild("ContentNode")
                    node.title = item.title.GetText()
                end for
                m.top.output = root
            else
                m.top.error = "Failed to parse XML/MRSS feed"
            end if
        else
            m.top.error = "Empty response from feed URL"
        end if"""

        brs_code = f"""function Init()
    m.top.functionName = "LoadFeed"
end function

function LoadFeed()
    if m.top.input = invalid or m.top.input.url = invalid
        m.top.error = "Missing feed URL in input.url"
        return invalid
    end if
    request = CreateObject("roUrlTransfer")
    request.SetCertificatesFile("common:/certs/ca-bundle.crt")
    request.SetUrl(m.top.input.url)
    response = request.GetToString()
    if response = invalid
        m.top.error = "HTTP request failed for feed URL"
        return invalid
    end if
{parse_logic}
end function"""

        await _create_file_with_header(brs_path, brs_code, is_brightscript=True)
        return True, "Generated content feed handler Task component."
    except Exception as e:
        return False, f"Failed to generate feed handler: {str(e)}"


async def generate_raf_integration(project_dir: str) -> Tuple[bool, str]:
    """Generate a Task component that integrates the Roku Advertising Framework (RAF)."""
    try:
        success, msg = await create_roku_component(
            "Task", "RafTask", os.path.join(project_dir, "components")
        )
        if not success:
            return False, msg

        brs_path = os.path.join(project_dir, "components", "RafTask", "RafTask.brs")
        raf_logic = """Library "Roku_Ads.brs"

function Init()
    m.top.functionName = "PlayAds"
end function

function PlayAds()
    adIface = Roku_Ads()
    adIface.SetAdUrl(m.top.input.adUrl)
    adPods = adIface.GetAds()
    if adPods <> invalid and adPods.Count() > 0
        rendered = adIface.ShowAds(adPods)
        m.top.output = { success: rendered <> invalid }
    else
        m.top.output = { success: true }
    end if
end function"""
        await _create_file_with_header(brs_path, raf_logic, is_brightscript=True)
        return True, "Generated RAF Integration Task component."
    except Exception as e:
        return False, f"Failed to generate RAF integration: {str(e)}"


async def generate_memory_monitor(project_dir: str) -> Tuple[bool, str]:
    """Generate roAppMemoryMonitor integration (required for certification
    as of October 1, 2026) including the OS 15.2 threshold-based low-memory
    event handling with roDeviceInfo fallback."""
    try:
        memory_monitor_brs = """' =====================================================================
' MemoryMonitor.brs - roAppMemoryMonitor integration (Roku OS 15.2+)
' REQUIRED FOR CERTIFICATION as of October 1, 2026: all apps must
' integrate the ifAppMemoryMonitor functions or Static Analysis blocks
' publishing.
' =====================================================================

sub StartMemoryMonitor(port as Object)
    ' roAppMemoryMonitor (OS 15.2+): threshold-based alerts at 80%, 85%,
    ' 90%, and 95% of the per-app memory limit when enabled.
    monitor = CreateObject("roAppMemoryMonitor")
    if monitor <> invalid
        monitor.SetMessagePort(port)
        if monitor.EnableMemoryWarningEvent(true)
            m.memoryMonitor = monitor
            print "[MEMORY] roAppMemoryMonitor enabled (thresholds: 80/85/90/95%)"
            return
        end if
    end if

    ' Fallback for devices that do not support roAppMemoryMonitor
    ' (Liberty, Austin, Mustang, Littlefield models).
    deviceInfo = CreateObject("roDeviceInfo")
    if deviceInfo <> invalid
        deviceInfo.SetMessagePort(port)
        deviceInfo.EnableLowGeneralMemoryEvent(true)
        m.memoryDeviceInfo = deviceInfo
        print "[MEMORY] roDeviceInfo low-memory events enabled (fallback)"
    end if
end sub

function HandleMemoryEvent(msg as Object) as Boolean
    ' Returns true when the event was a memory notification.
    msgType = type(msg)

    if msgType = "roAppMemoryNotificationEvent"
        info = msg.GetInfo()
        usagePercent = info.Lookup("MemoryUsagePercent")
        print "[MEMORY] Low-memory alert: " + StrI(usagePercent) + "% of app limit"
        OnLowMemoryWarning(usagePercent)
        return true

    else if msgType = "roDeviceInfoEvent"
        info = msg.GetInfo()
        memoryLevel = info.Lookup("generalMemoryLevel")
        print "[MEMORY] General memory level: " + memoryLevel
        OnLowMemoryWarning(100)
        return true
    end if

    return false
end function

sub OnLowMemoryWarning(usagePercent as Integer)
    ' React to memory pressure: release caches, prune ContentNode trees,
    ' unobserve fields that are no longer needed, and free large bitmaps.
    ReleaseMemory()
end sub

sub ReleaseMemory()
    ' Clear cached images/posts and detach finished tasks.
    if m.contentCache <> invalid
        m.contentCache.Clear()
    end if
    if m.contentTask <> invalid and m.contentTask.state <> "DONE"
        m.contentTask.control = "STOP"
    end if
    print "[MEMORY] Available memory (Kb): " + StrI(GetAvailableMemory())
end sub

function GetMemoryStats() as Object
    monitor = GetMemoryMonitor()
    stats = { usagePercent: invalid, availableKb: invalid, limits: invalid }
    if monitor <> invalid
        stats.usagePercent = monitor.GetMemoryLimitPercent()
        stats.availableKb = monitor.GetChannelAvailableMemory()
        stats.limits = monitor.GetChannelMemoryLimit()
    end if
    return stats
end function

function GetAvailableMemory() as Integer
    monitor = GetMemoryMonitor()
    if monitor <> invalid
        return monitor.GetChannelAvailableMemory()
    end if
    return -1
end function

function GetMemoryMonitor() as Object
    if m.memoryMonitor <> invalid
        return m.memoryMonitor
    end if
    candidate = CreateObject("roAppMemoryMonitor")
    if candidate <> invalid and candidate.EnableMemoryWarningEvent(true)
        m.memoryMonitor = candidate
        return candidate
    end if
    return invalid
end function"""

        path = os.path.join(project_dir, "source", "MemoryMonitor.brs")
        success, msg = await _create_file_with_header(
            path, memory_monitor_brs, is_brightscript=True
        )
        if not success:
            return False, msg
        return (
            True,
            "roAppMemoryMonitor integration generated at "
            + path
            + ". Call StartMemoryMonitor(port) from your main message loop and route "
            + "roAppMemoryNotificationEvent / roDeviceInfoEvent messages through "
            + "HandleMemoryEvent(msg). This integration is mandatory for certification "
            + "as of October 1, 2026 (Static Analysis error otherwise).",
        )
    except Exception as e:
        return False, f"Failed to generate memory monitor: {str(e)}"


async def generate_websocket_handler(project_dir: str) -> Tuple[bool, str]:
    """Generate an roWebSocket Task component (Roku OS 16.0+, requires the
    16.0 developer beta or later) for bi-directional communication."""
    try:
        success, msg = await create_roku_component(
            "WebSocketTask", "WebSocketTask", os.path.join(project_dir, "components")
        )
        if not success:
            return False, msg
        return (
            True,
            "Generated WebSocketTask component in "
            + os.path.join(project_dir, "components", "WebSocketTask")
            + " using the OS 16.0 roWebSocket component. Set the url field to a "
            + "wss:// endpoint, control = \"RUN\" to start the task, and observe the "
            + "message field for received text events.",
        )
    except Exception as e:
        return False, f"Failed to generate WebSocket handler: {str(e)}"


async def generate_sse_handler(project_dir: str) -> Tuple[bool, str]:
    """Generate a Task component using roUrlTransfer.AsyncGetSSEvents()
    to consume Server-Sent Events (roSSEvent, Roku OS 16.0+)."""
    try:
        success, msg = await create_roku_component(
            "Task", "SSEEventsTask", os.path.join(project_dir, "components")
        )
        if not success:
            return False, msg

        brs_path = os.path.join(
            project_dir, "components", "SSEEventsTask", "SSEEventsTask.brs"
        )
        sse_code = """' =====================================================================
' SSEEventsTask - Server-Sent Events consumer (Roku OS 16.0+)
' Uses roUrlTransfer.AsyncGetSSEvents() and handles roSSEvent messages.
' =====================================================================

' roUrlEvent types received during an SSE transfer
const SSE_TRANSFER_COMPLETED = 1
const SSE_TRANSFER_STARTED = 2

function Init()
    m.top.functionName = "RunSSEEvents"
end function

function RunSSEEvents()
    if m.top.input = invalid or m.top.input.url = invalid
        m.top.error = "Missing SSE stream url in m.top.input.url"
        return invalid
    end if

    port = CreateObject("roMessagePort")
    transfer = CreateObject("roUrlTransfer")
    transfer.SetMessagePort(port)
    transfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
    transfer.SetUrl(m.top.input.url)

    if transfer.AsyncGetSSEvents()
        while true
            msg = wait(0, port)

            if type(msg) = "roUrlEvent"
                event = msg.GetInt()
                if event = SSE_TRANSFER_STARTED
                    print "[SSE] Transfer started, response code: "; msg.GetResponseCode()
                else if event = SSE_TRANSFER_COMPLETED
                    print "[SSE] Transfer completed, response code: "; msg.GetResponseCode()
                    exit while
                end if
            else if type(msg) = "roSSEvent"
                eventPayload = {
                    event: msg.GetEvent(),
                    id: msg.GetId(),
                    data: msg.GetData(),
                    retry: msg.GetRetry()
                }
                m.top.output = eventPayload
            else if type(msg) = "roSGNodeEvent"
                ' Task was stopped externally - terminate the transfer
                transfer.AsyncCancel()
                exit while
            end if
        end while
    else
        m.top.error = "AsyncGetSSEvents() failed to start"
    end if
end function"""

        await _create_file_with_header(brs_path, sse_code, is_brightscript=True)
        return (
            True,
            "Generated SSEEventsTask component using roUrlTransfer.AsyncGetSSEvents() "
            + "(Roku OS 16.0+). Set input.url to your SSE endpoint, observe the "
            + "output field for parsed roSSEvent payloads.",
        )
    except Exception as e:
        return False, f"Failed to generate SSE handler: {str(e)}"


async def generate_roku_pay_integration(project_dir: str) -> Tuple[bool, str]:
    """Generate Roku Pay integration (ChannelStore node): entitlement checks,
    catalog ordering, and in-channel purchase flows for SVOD/TVOD channels.
    Includes the OS 16.0 GetRokuCustomerId command (opt-in via enable_customer_id)."""
    try:
        roku_pay_brs = """' =====================================================================
' RokuPay.brs - ChannelStore node integration for Roku Pay
' Provides entitlement checks (getPurchases), catalog browsing, and
' in-channel purchase flows required for SVOD/TVOD channels.
' =====================================================================

' ------------------------------------------------------------------
' Check whether the customer already owns an entitlement (all launches)
' ------------------------------------------------------------------
function CheckEntitlements(productCodes as Object) as Boolean
    store = CreateObject("roSGNode", "ChannelStore")
    port = CreateObject("roMessagePort")
    store.SetMessagePort(port)
    store.ObserveField("purchases", "OnPurchases")
    store.command = "getPurchases"

    msg = wait(10000, port)
    if type(msg) <> "roSGNodeEvent"
        print "[ROKUPAY] getPurchases timed out"
        return false
    end if

    purchases = store.purchases
    if purchases <> invalid
        for each purchase in purchases.GetChild(0).GetChildren(-1, 0)
            code = purchase.code
            if productCodes.Count() > 0
                for each entitlementCode in productCodes
                    if code = entitlementCode
                        print "[ROKUPAY] Customer entitled: " + code
                        return true
                    end if
                end for
            end if
        end for
    end if
    return false
end function

sub OnPurchases()
    ' Observer stub for purchases field changes
end sub

' ------------------------------------------------------------------
' Purchase a subscription or one-time product (initiate order)
' ------------------------------------------------------------------
sub PurchaseProduct(productCode as String)
    store = CreateObject("roSGNode", "ChannelStore")
    port = CreateObject("roMessagePort")
    store.SetMessagePort(port)

    myOrder = CreateObject("roSGNode", "ContentNode")
    orderItem = myOrder.CreateChild("ContentNode")
    orderItem.AddFields({ code: productCode, qty: 1 })
    store.order = myOrder
    store.command = "doOrder"

    msg = wait(30000, port)
    if type(msg) = "roSGNodeEvent" and msg.GetField() = "orderStatus"
        status = store.orderStatus
        HandleOrderStatus(status)
    end if
end sub

sub HandleOrderStatus(status as Dynamic)
    if status = invalid
        print "[ROKUPAY] Order status unavailable"
        return
    end if
    if status.status <> invalid
        print "[ROKUPAY] Order status: " + status.status
    end if
    if status.errorCode <> invalid
        print "[ROKUPAY] Order error: " + StrI(status.errorCode) + " " + status.errorMessage
    end if
    ' On success, call CheckEntitlements again to confirm access
end sub

' ------------------------------------------------------------------
' Browse the in-channel product catalog
' ------------------------------------------------------------------
sub BrowseCatalog()
    store = CreateObject("roSGNode", "ChannelStore")
    port = CreateObject("roMessagePort")
    store.SetMessagePort(port)
    store.command = "doBrowse"
    msg = wait(10000, port)
    if type(msg) = "roSGNodeEvent" and store.catalog <> invalid
        print "[ROKUPAY] Catalog loaded"
        ' Populate the purchase UI from store.catalog children here
    end if
end sub

' ------------------------------------------------------------------
' Roku OS 16.0+: retrieve the unique Roku customer ID without requiring
' a prior purchase (ChannelStore GetRokuCustomerId command).
' ------------------------------------------------------------------
function GetRokuCustomerId() as String
    di = CreateObject("roDeviceInfo")
    if di <> invalid and di.GetVersion() <> invalid
        store = CreateObject("roSGNode", "ChannelStore")
        port = CreateObject("roMessagePort")
        store.SetMessagePort(port)
        store.command = "getRokuCustomerId"
        msg = wait(10000, port)
        if type(msg) = "roSGNodeEvent"
            ' rokuCustomerId is exposed via the store purchase/identity data
            ' after the command completes. Use it to identify the customer
            ' consistently across apps and Roku Pay push notifications.
            if store.rokuCustomerId <> invalid
                return store.rokuCustomerId
            end if
        end if
    end if
    return ""
end function"""

        path = os.path.join(project_dir, "source", "RokuPay.brs")
        success, msg = await _create_file_with_header(
            path, roku_pay_brs, is_brightscript=True
        )
        if not success:
            return False, msg
        return (
            True,
            "Roku Pay integration generated at "
            + path
            + ". Call CheckEntitlements(codes) on every launch (certification also "
            + "requires an entitlement check whenever the channel resumes from the "
            + "home screen), PurchaseProduct(code) to trigger a order, and "
            + "GetRokuCustomerId() on Roku OS 16.0+ devices for the customer ID "
            + "without a prior purchase.",
        )
    except Exception as e:
        return False, f"Failed to generate Roku Pay integration: {str(e)}"


def validate_content_feed(content: str) -> str:
    """Validate a Roku Direct Publisher JSON content feed against the
    published feed schema requirements."""
    issues = []
    warnings = []

    try:
        feed = json.loads(content)
    except json.JSONDecodeError as e:
        return f"Error: Feed is not valid JSON: {e}"

    # Top-level required fields
    required_top = ["providerName", "lastUpdated", "language"]
    for field in required_top:
        if field not in feed:
            issues.append(f"Missing required top-level field: {field}")

    if "lastUpdated" in feed:
        try:
            datetime.datetime.fromisoformat(
                feed["lastUpdated"].replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            issues.append("lastUpdated must be an ISO 8601 timestamp (e.g. 2026-10-16T10:00:00Z)")

    content_types = ["movies", "series", "shortFormVideos", "liveFeeds"]
    has_content = any(t in feed and len(feed[t]) > 0 for t in content_types)
    if not has_content:
        issues.append(
            "Feed must contain at least one of: movies, series, shortFormVideos, or liveFeeds arrays"
        )

    valid_video_types = ["HLS", "DASH", "MP4", "SmoothStreaming"]

    def validate_item(item, index, key):
        for field in ["id", "title", "shortDescription", "thumbnail", "content"]:
            if field not in item:
                issues.append(f"{key}[{index}]: Missing required field: {field}")
        if "thumbnail" in item and isinstance(item.get("thumbnail"), str):
            if not item["thumbnail"].lower().startswith("https"):
                issues.append(f"{key}[{index}]: thumbnail URL must use HTTPS")
        content = item.get("content")
        if isinstance(content, dict):
            if "dateAdded" in content:
                try:
                    datetime.datetime.fromisoformat(
                        content["dateAdded"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    issues.append(
                        f"{key}[{index}]: content.dateAdded must be ISO 8601 format"
                    )
            duration = content.get("duration")
            if duration is not None and (
                not isinstance(duration, int) or duration <= 0
            ):
                issues.append(
                    f"{key}[{index}]: content.duration must be a positive integer (seconds)"
                )
            videos = content.get("videos", [])
            if not videos:
                issues.append(f"{key}[{index}]: content.videos array is empty")
            for vi, video in enumerate(videos):
                url = video.get("url", "")
                if url and not url.lower().startswith("https"):
                    issues.append(f"{key}[{index}].videos[{vi}]: video URL must use HTTPS")
                vt = video.get("videoType")
                if vt and vt not in valid_video_types:
                    issues.append(
                        f"{key}[{index}].videos[{vi}]: videoType must be one of "
                        + ", ".join(valid_video_types)
                    )
        rating = item.get("rating")
        if isinstance(rating, dict) and "ratingSource" in rating:
            if "rating" not in rating:
                issues.append(f"{key}[{index}]: rating block requires both rating and ratingSource")

    for key in content_types:
        items = feed.get(key, [])
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    validate_item(item, index, key)

    if issues:
        return (
            "Content feed validation failed:\n"
            + "\n".join(f"  - {issue}" for issue in issues)
            + ("\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings) if warnings else "")
        )
    if warnings:
        return (
            "Content feed validation passed with warnings:\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )
    return "Content feed validation passed. Feed matches the Direct Publisher JSON schema requirements."


def _validate_ipv4(address: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False


def _ecp_request(device_ip: str, command: str) -> str:
    """Issue an ECP GET request to a Roku device (requires developer mode for
    developer commands like query/chanperf). Uses only the standard library."""
    if not _validate_ipv4(device_ip):
        return f"Error: Invalid device IP address: {device_ip}"
    url = f"http://{device_ip}:8060/{command}"
    try:
        import urllib.request

        request = urllib.request.Request(
            url, headers={"User-Agent": "Roku-Engineer/2.1"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error querying Roku device at {device_ip}: {str(e)}"


def get_roku_device_info(device_ip: str) -> str:
    """Fetch device information from a Roku device via ECP
    (GET http://<ip>:8060/query/device-info)."""
    result = _ecp_request(device_ip, "query/device-info")
    if result.startswith("Error"):
        return result
    if "<device-info>" not in result:
        return f"Unexpected response from device:\n{result[:500]}"
    return result


def check_device_performance(device_ip: str) -> str:
    """Query channel performance stats via the ECP chanperf command.
    Requires the device to be in developer mode with Control by mobile
    apps enabled. Roku OS 15.2+ responses include the <proc-stat> field
    with raw Linux CPU/process statistics for monitoring tools."""
    result = _ecp_request(device_ip, "query/chanperf")
    if result.startswith("Error"):
        return result
    has_proc_stat = "<proc-stat>" in result
    summary = "Channel performance data retrieved"
    if has_proc_stat:
        summary += " (includes OS 15.2+ <proc-stat> raw Linux CPU/process stats)"
    else:
        summary += " (<proc-stat> requires Roku OS 15.2+)"
    return summary + ":\n\n" + result


def capture_device_screenshot(
    device_ip: str, username: str, password: str, output_path: str
) -> str:
    """Capture a screenshot from a Roku device in developer mode over HTTP
    digest auth and save it to output_path. Requires curl to be installed."""
    if not _validate_ipv4(device_ip):
        return f"Error: Invalid device IP address: {device_ip}"
    if not is_installed("curl"):
        return "Error: curl is required for device screenshots but was not found on PATH."
    try:
        screenshot_cmd = [
            "curl",
            "-s",
            "--user",
            f"{username}:{password}",
            "--digest",
            "--max-time",
            "15",
            "-o",
            output_path,
            f"http://{device_ip}/plugin_inspect",
        ]
        result = subprocess.run(
            screenshot_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return f"Error capturing screenshot: {result.stderr}"
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return f"Screenshot saved to {output_path}."
        return "Error: Screenshot capture returned no data. Verify developer mode is enabled."
    except Exception as e:
        return f"Error capturing screenshot: {str(e)}"


def capture_device_logs(
    device_ip: str, duration_seconds: int = 10, output_file: Optional[str] = None
) -> str:
    """Connect to the Roku debug console (telnet port 8085) and capture
    BrightScript runtime output for a fixed duration. Uses raw sockets
    (telnetlib was removed in Python 3.13)."""
    if not _validate_ipv4(device_ip):
        return f"Error: Invalid device IP address: {device_ip}"
    import socket

    duration_seconds = max(1, min(duration_seconds, 300))
    log_lines = []
    try:
        sock = socket.create_connection((device_ip, 8085), timeout=5)
        sock.settimeout(1)
        deadline = time.time() + duration_seconds
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if chunk:
                    log_lines.append(chunk.decode("utf-8", errors="replace"))
                else:
                    break
            except socket.timeout:
                continue
        sock.close()
    except Exception as e:
        return f"Error connecting to the debug console on {device_ip}:8085 - {str(e)}"

    logs = "".join(log_lines)
    if not logs.strip():
        return (
            f"No log output captured in {duration_seconds}s. Make sure a sideloaded "
            + "channel is running and the device is in developer mode."
        )
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(logs)
        return f"Captured {len(logs)} characters of debug output to {output_file}."
    return logs[:20000]


async def create_roku_component(
    component_type: str,
    name: str,
    output_dir: str,
    include_accessibility: bool = True,
) -> Tuple[bool, str]:
    """Create a new Roku SceneGraph component with associated BrightScript file"""
    try:
        if component_type not in SCENEGRAPH_TEMPLATES:
            raise ValueError(
                f"Invalid component type. Must be one of: {list(SCENEGRAPH_TEMPLATES.keys())}"
            )

        component_dir = os.path.join(output_dir, name)

        xml_path = os.path.join(component_dir, f"{name}.xml")
        script_uri = f"pkg:/components/{name}/{name}.brs"
        xml_content = SCENEGRAPH_TEMPLATES[component_type].format(
            name=name, script_uri=script_uri
        )

        success, message = await _create_file_with_header(xml_path, xml_content)
        if not success:
            return False, message

        brs_path = os.path.join(component_dir, f"{name}.brs")
        brs_content = BRIGHTSCRIPT_TEMPLATES[component_type]

        success, message = await _create_file_with_header(
            brs_path, brs_content, is_brightscript=True
        )
        if not success:
            return False, message

        return True, f"Created component {name} in {component_dir}"

    except (ValueError, IOError) as e:
        error_message = f"Error creating component: {str(e)}"
        logging.error(error_message)
        return False, error_message
    except Exception as e:
        error_message = (
            f"An unexpected error occurred while creating component {name}: {str(e)}"
        )
        logging.error(error_message)
        return False, error_message


async def create_roku_project(
    project_name: str, output_dir: str, project_type: str = "basic"
) -> Tuple[bool, str]:
    """Create a new Roku project with a modern, certification-ready structure
    including the mandatory roAppMemoryMonitor integration."""
    try:
        project_dir = os.path.join(output_dir, project_name)

        # Create project structure
        dirs = ["components", "images", "source", "locale/en_US"]
        for dir_name in dirs:
            os.makedirs(os.path.join(project_dir, dir_name), exist_ok=True)

        # Create locale translations placeholder (required for localization)
        translations = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<!DOCTYPE TS>\n"
            '<TS version="2.0" language="en_US" sourcelanguage="en_US">\n'
            "  <defaultcodec>UTF-8</defaultcodec>\n"
            "  <context>\n"
            "    <name>default</name>\n"
            "  </context>\n"
            "</TS>\n"
        )
        await _create_file_with_header(
            os.path.join(project_dir, "locale", "en_US", "translations.ts"),
            translations,
        )

        # Create manifest with all certification-required fields
        manifest_content = f"""title={project_name}
major_version=1
minor_version=0
build_version=1
mm_icon_focus_hd=pkg:/images/icon_focus_hd.png
mm_icon_focus_sd=pkg:/images/icon_focus_sd.png
splash_screen_hd=pkg:/images/splash_hd.jpg
splash_screen_sd=pkg:/images/splash_sd.jpg
ui_resolutions=hd,fhd
splash_color=#000000
splash_min_time=1500
supported_locales=en_US
channel_genre=Entertainment
parental_rating=G
content_rating=TV-G
privacy_policy=https://example.com/privacy
terms_of_service=https://example.com/terms
screensaver_title={project_name} Screensaver
supports_input_launch=1
channel_store_description={project_name} - a modern Roku channel built with Roku Engineer."""
        success, message = await _create_file_with_header(
            os.path.join(project_dir, "manifest"), manifest_content
        )
        if not success:
            return False, message

        # Create main scene (GridView for sgdex projects)
        scene_type = "GridView" if project_type == "sgdex" else "Scene"
        success, message = await create_roku_component(
            scene_type, "MainScene", os.path.join(project_dir, "components")
        )
        if not success:
            return False, message

        # roAppMemoryMonitor integration is mandatory for certification as of
        # October 1, 2026 - generate it into every new project.
        await generate_memory_monitor(project_dir)

        # Deep link handling is required for certification - generate it too.
        await generate_deep_link_handler(project_dir)

        # Create main.brs with memory monitoring and deep link handling wired in
        main_content = """sub Main(args as Dynamic)
    screen = CreateObject("roSGScreen")
    m.port = CreateObject("roMessagePort")
    screen.setMessagePort(m.port)

    scene = screen.CreateScene("MainScene")
    screen.show()

    ' roAppMemoryMonitor: REQUIRED for certification as of Oct 1, 2026.
    ' Handles roAppMemoryNotificationEvent (OS 15.2+ threshold alerts at
    ' 80/85/90/95%) and falls back to roDeviceInfo low-memory events.
    StartMemoryMonitor(m.port)

    ' Handle deep link launch arguments (required for certification).
    ' InitDeepLink stores the args on the scene global node; observe
    ' m.global.deepLinkArgs in your scene to route to the content.
    if args <> invalid and args.contentId <> invalid
        InitDeepLink(screen.getGlobalNode(), args)
    end if

    ' Handle runtime deep links and other input events via roInput
    input = CreateObject("roInput")
    input.SetMessagePort(m.port)

    while true
        msg = wait(0, m.port)
        msgType = type(msg)

        if msgType = "roSGScreenEvent"
            if msg.isScreenClosed()
                return
            end if
        else if msgType = "roInputEvent"
            info = msg.GetInfo()
            if info <> invalid and info.contentId <> invalid
                InitDeepLink(screen.getGlobalNode(), info)
            end if
        else if HandleMemoryEvent(msg)
            ' Low-memory notification handled by MemoryMonitor.brs
        end if
    end while
end sub"""
        success, message = await _create_file_with_header(
            os.path.join(project_dir, "source", "main.brs"),
            main_content,
            is_brightscript=True,
        )
        if not success:
            return False, message

        return (
            True,
            f"Created Roku project {project_name} in {project_dir}. "
            f"Project type: {project_type}. Includes certification-ready manifest, "
            "memory monitor integration (mandatory as of Oct 1, 2026), and deep "
            "link launch handling.",
        )

    except (ValueError, IOError) as e:
        error_message = f"Error creating project: {str(e)}"
        logging.error(error_message)
        return False, error_message
    except Exception as e:
        error_message = f"An unexpected error occurred while creating project {project_name}: {str(e)}"
        logging.error(error_message)
        return False, error_message


async def deploy_to_roku(
    package_path: str,
    device_ip: str,
    password: str,
    username: str = "rokudev",
) -> str:
    """Deploy a Roku channel package to a device in developer mode via the
    plugin_install endpoint (HTTP digest auth)."""
    try:
        # Validate package exists
        if not os.path.exists(package_path):
            raise FileNotFoundError(f"Package not found: {package_path}")

        if not _validate_ipv4(device_ip):
            return f"Error: Invalid device IP address: {device_ip}"

        if not is_installed("curl"):
            return "Error: curl is required for deployment but was not found on PATH."

        # Sideload via the developer web server (digest auth)
        deploy_cmd = [
            "curl",
            "-s",
            "--user",
            f"{username}:{password}",
            "--digest",
            "--form",
            "mysubmit=Install",
            "--form",
            f"archive=@{package_path}",
            f"http://{device_ip}/plugin_install",
        ]

        result = subprocess.run(deploy_cmd, capture_output=True, text=True, timeout=60)

        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and ("Success" in output or "Identified" in output):
            return f"Deployment succeeded: {package_path} installed on {device_ip}."
        else:
            logging.error(f"Deployment failed: {result.stderr}")
            return f"Deployment failed on {device_ip}. Device response: {output[:1000]}"

    except FileNotFoundError as e:
        return f"Error deploying to Roku: {str(e)}"
    except Exception as e:
        logging.error(f"Error deploying to Roku: {str(e)}")
        return f"Error deploying to Roku: {str(e)}"


async def validate_roku_component(component_path: str) -> str:
    """Validate a Roku SceneGraph component XML file structure:
    the root element must be <component> with name/extends/script attributes."""
    try:
        import xml.etree.ElementTree as ET

        if not os.path.exists(component_path):
            return "Error: Component path does not exist."

        with open(component_path, "r", encoding="utf-8") as f:
            content = f.read()

        root = ET.fromstring(content)

        if root.tag != "component":
            return (
                f"Invalid root element: <{root.tag}>. SceneGraph component "
                "files must use <component> as the root element."
            )

        issues = []
        if "name" not in root.attrib:
            issues.append("Missing required attribute: name")
        if "extends" not in root.attrib:
            issues.append("Missing recommended attribute: extends")

        has_script = any(
            child.tag == "script" and "uri" in child.attrib for child in root
        )
        if not has_script:
            issues.append(
                "No <script type=\"text/brightscript\" uri=\"...\" /> element found - "
                "the component has no BrightScript logic"
            )

        children_element = root.find("children")
        if children_element is not None and len(children_element) > 0:
            if not any(
                child.tag in ROKU_COMPONENT_TYPES for child in children_element
            ):
                issues.append(
                    "Warning: <children> contains no known SceneGraph node types"
                )

        if issues:
            return (
                f"Component validation found issues in {component_path}:\n"
                + "\n".join(f"  - {issue}" for issue in issues)
            )
        return f"Component {component_path} is a valid SceneGraph component."
    except ET.ParseError as e:
        return f"Invalid XML in {component_path}: {str(e)}"
    except Exception as e:
        return f"Error validating component: {str(e)}"


if __name__ == "__main__":
    # Run the main program
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\nProgram interrupted by user. Exiting...", style="bold red")
    except Exception as e:
        console.print(f"An unexpected error occurred: {str(e)}", style="bold red")
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        console.print("Program finished. Goodbye!", style="bold green")

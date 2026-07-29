import streamlit as st
import json
import os
from datetime import datetime
from pathlib import Path

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version, artifact_version_dict
from chat import run_model_tool_loop, trim_history, write_transcript, safe_slug, now_iso

# Configuration
ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)

st.set_page_config(page_title="Research Agent Eval UI", layout="wide")
st.title("Research Agent (Lab 04)")

# Sidebar for configuration
with st.sidebar:
    st.header("Settings")
    provider_name = st.selectbox("Provider", ["openrouter", "openai", "anthropic", "gemini"])
    version_label = st.text_input("Version Label", "v3")
    history_window = st.number_input("History Window", min_value=1, max_value=20, value=5)
    max_tool_rounds = st.number_input("Max Tool Rounds", min_value=1, max_value=10, value=4)
    
    if st.button("Reset Chat"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Initialization
if "history" not in st.session_state:
    st.session_state.history = []
if "transcript" not in st.session_state:
    st.session_state.transcript = None
if "turn_index" not in st.session_state:
    st.session_state.turn_index = 0
if "transcript_path" not in st.session_state:
    st.session_state.transcript_path = None

# Load artifacts
system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
tools_path = ARTIFACTS_DIR / "tools.yaml"

try:
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(tools_path)
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)
    selected_model = getattr(provider, "default_model", None)
    artifact_version = build_artifact_version(version_label, system_prompt_path, tools_path)
except Exception as e:
    st.error(f"Error loading configuration: {e}")
    st.stop()

# Initialize transcript
if st.session_state.transcript is None:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([
        safe_slug(version_label),
        safe_slug(provider_name),
        timestamp,
    ])
    st.session_state.transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    st.session_state.transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": system_prompt,
        "tools": str(tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }

st.caption(f"Artifact version: `{artifact_version.artifact_version}`")

# Display chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "tool_events" in msg and msg["tool_events"]:
            with st.expander("🛠 Tool Execution Traces"):
                for event in msg["tool_events"]:
                    st.code(f"Call: {event['tool']}\nArgs: {json.dumps(event['args'], ensure_ascii=False)}\nResult: {json.dumps(event.get('result', {}), ensure_ascii=False, indent=2)}", language="json")

# Chat input
if user_text := st.chat_input("Nhập câu hỏi hoặc yêu cầu..."):
    # Show user message
    with st.chat_message("user"):
        st.markdown(user_text)
    
    st.session_state.turn_index += 1
    
    # Prepare messages
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history([{"role": m["role"], "content": m["content"]} for m in st.session_state.history], history_window),
        {"role": "user", "content": user_text},
    ]
    
    turn_record = {
        "turn_index": st.session_state.turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }
    
    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            try:
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=openai_tools,
                    model=selected_model,
                    max_tool_rounds=max_tool_rounds,
                )
                turn_record.update(result)
                assistant_text = result["assistant_text"]
                
                # Show assistant response
                st.markdown(assistant_text)
                
                # Show tool events if any
                tool_events = result.get("tool_events", [])
                if tool_events:
                    with st.expander("🛠 Tool Execution Traces", expanded=False):
                        for event in tool_events:
                            st.code(f"Call: {event['tool']}\nArgs: {json.dumps(event['args'], ensure_ascii=False)}\nResult: {json.dumps(event.get('result', {}), ensure_ascii=False, indent=2)}", language="json")
                
                # Append to history
                st.session_state.history.append({"role": "user", "content": user_text})
                st.session_state.history.append({"role": "assistant", "content": assistant_text, "tool_events": tool_events})
                
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {str(exc)}"
                st.error(error_msg)
                turn_record.update({
                    "status": "provider_error",
                    "error": error_msg,
                })
    
    # Save transcript
    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(st.session_state.transcript_path, st.session_state.transcript)

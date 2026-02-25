"""
Zonny CLI - Terminal Interface

A dumb pipe that:
- Renders UI
- Reads user input
- Sends JSON to MCP Gateway
- Displays response

DOES NOT:
[FAIL] Decide agents
[FAIL] Touch memory
[FAIL] Call Ollama
[FAIL] Know about tools

This is Zonny Protocol v1.
"""

import uuid
import os
import sys
import requests
import json
from typing import Optional


# Configuration
MCP_ENDPOINT = os.environ.get("ZONNY_ENDPOINT", "http://127.0.0.1:8000/mcp")
# API key: set ZONNY_API_KEY in your environment, or generate one with: python create_key.py
API_KEY = os.environ.get("ZONNY_API_KEY", "")


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_logo():
    """Print Zonny logo/header"""
    print("\n" + "="*70)
    print("""
    ███████╗ ██████╗ ███╗ ██╗███╗ ██╗██╗ ██╗
    ╚══███╔╝██╔═══██╗████╗ ██║████╗ ██║╚██╗ ██╔╝
      ███╔╝ ██║ ██║██╔██╗ ██║██╔██╗ ██║ ╚████╔╝
     ███╔╝ ██║ ██║██║╚██╗██║██║╚██╗██║ ╚██╔╝
    ███████╗╚██████╔╝██║ ╚████║██║ ╚████║ ██║
    ╚══════╝ ╚═════╝ ╚═╝ ╚═══╝╚═╝ ╚═══╝ ╚═╝
    """)
    print(" Welcome to the zone")
    print("="*70)


def print_hints():
    """Print usage hints"""
    print("\n[IDEA] Commands:")
    print(" /agents - List available agents")
    print(" /help - Show help")
    print(" /exit - Exit Zonny")
    print("\n[CHAT] Or just type a message to chat")
    print()


def send_to_mcp(session_id: str, input_text: Optional[str] = None, command: Optional[str] = None) -> dict:
    """
    Send request to MCP Gateway.
    
    This is the ONLY external call the CLI makes.
    
    Args:
        session_id: Session UUID
        input_text: User input (if chat)
        command: Command (if starts with /)
        
    Returns:
        Response dict from gateway
    """
    # Build payload (Zonny Protocol v1)
    payload = {
        "session": session_id,
        "input": input_text,
        "command": command
    }
    
    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            MCP_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.ConnectionError:
        return {
            "output": "[FAIL] Cannot connect to MCP Gateway. Is the server running?\n Run: python -m uvicorn server:app --reload"
        }
    except requests.exceptions.Timeout:
        return {
            "output": "⏱️ Request timed out. The agent may be processing..."
        }
    except requests.exceptions.RequestException as e:
        return {
            "output": f"[FAIL] Request failed: {e}"
        }
    except Exception as e:
        return {
            "output": f"[FAIL] Unexpected error: {e}"
        }


def render_response(response: dict):
    """
    Display response from MCP Gateway.
    
    No interpretation - just print what we got.
    """
    # Slice E uses 'response' key
    output = response.get("response") or response.get("output", "")
    
    if output:
        print("\n" + output)
    else:
        print("\n[WARN]️ No response from gateway")


def run_cli():
    """
    Main CLI loop.
    
    Responsibilities:
    1. Generate session UUID
    2. Loop forever reading input
    3. Send to MCP
    4. Display response
    """
    # Startup
    clear_screen()
    print_logo()
    print_hints()
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    print(f" Session: {session_id[:8]}...\n")
    
    # Input loop
    try:
        while True:
            # Read input
            try:
                user_input = input("\n Zonny > ").strip()
            except EOFError:
                print("\n Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Check for exit
            if user_input.lower() in ['/exit', 'exit', 'quit']:
                print("\n Goodbye!")
                break
            
            # Check if command or input
            if user_input.startswith('/'):
                # It's a command
                command = user_input
                response = send_to_mcp(session_id, command=command)
            else:
                # It's input
                response = send_to_mcp(session_id, input_text=user_input)
            
            # Render response
            render_response(response)
    
    except KeyboardInterrupt:
        print("\n\n Interrupted. Goodbye!")
        sys.exit(0)


def main():
    """
    Entry point for Zonny CLI.
    
    This is what gets called when you type 'zonny' anywhere.
    It captures the current working directory and starts Zonny there.
    """
    import os
    from zonny.runtime import start
    
    # Capture the directory where 'zonny' was invoked
    project_root = os.getcwd()
    
    # Clear screen and show logo
    clear_screen()
    print_logo()
    
    # Start Zonny in that directory
    start(project_root)


def main_server_mode():
    """
    Entry point for server mode (legacy).
    
    This keeps the HTTP client-server mode working for backwards compatibility.
    """
    run_cli()


if __name__ == "__main__":
    main()

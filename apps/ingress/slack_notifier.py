#!/usr/bin/env python3
"""Send Slack DM notifications for HITL gates."""
import os
import sys
from pathlib import Path
from slack_sdk import WebClient
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

def notify_gate(job_id: str, gate: int, slack_user: str = None):
    """Send a DM to the user who created the job."""
    if not slack_user:
        return  # CLI jobs don't have Slack user
    
    token = os.environ.get("SLACK_TOKEN")
    if not token:
        print("ERROR: SLACK_TOKEN not found for notification")
        return
        
    client = WebClient(token=token)
    
    text = f"*{job_id}* is waiting for Gate {gate} approval.\n"
    if gate == 1:
        text += f"Run: `py -3.12 scripts/approve.py --job work/jobs/{job_id}.md --gate 1`"
    elif gate == 2:
        text += f"Audit passed. Run: `py -3.12 scripts/approve.py --job work/jobs/{job_id}.md --gate 2`"
    elif gate == 3:
        text += f"Staged for promotion. Run: `py -3.12 scripts/approve.py --job work/jobs/{job_id}.md --gate 3`"
    
    try:
        client.chat_postMessage(channel=slack_user, text=text, as_user=True)
    except Exception as e:
        print(f"Error sending Slack notification to {slack_user}: {e}")

#!/usr/bin/env python3
"""Slack ingress for NIM-Kinetic Meta-Agent MVP."""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import yaml
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.atomic_io import atomic_write

# Load .env
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

app = App(token=os.environ.get("SLACK_TOKEN"))

def create_job_from_slack(text: str, user: str) -> str:
    """Create a JOB-###.md from Slack message text."""
    job_id = f"JOB-SLACK-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    job_path = Path("work/jobs") / f"{job_id}.md"
    job_path.parent.mkdir(parents=True, exist_ok=True)
    
    frontmatter = {
        "job_id": job_id,
        "status": "created",
        "source": "slack",
        "slack_user": user,
        "objective": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n# {job_id}\n\n{text}\n"
    atomic_write(job_path, content)
    return job_id

@app.message("")
def handle_message(message, say):
    """Handle incoming Slack DM."""
    user = message["user"]
    text = message["text"]
    
    job_id = create_job_from_slack(text, user)
    say(f"JOB created: `{job_id}`\nRun `approve --job work/jobs/{job_id}.md --gate 1` to approve.")

if __name__ == "__main__":
    # Use Socket Mode (no public URL needed)
    if "SLACK_APP_TOKEN" not in os.environ:
        print("ERROR: SLACK_APP_TOKEN not found in environment")
        sys.exit(1)
        
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Slack app started in Socket Mode...")
    handler.start()

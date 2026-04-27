import os
import time
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from utils.atomic_io import read_frontmatter, write_frontmatter
from utils.job_utils import get_job_path

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AntigravitySlackAdapter:
    """
    Antigravity Slack Adapter (Socket Mode).
    Handles interactive HITL (Approve/Reject) from Slack.
    """
    def __init__(self):
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN")
        self.app_token = os.environ.get("SLACK_APP_TOKEN")
        self.channel_id = os.environ.get("SLACK_CHANNEL_ID")
        self.admin_ids = os.environ.get("SLACK_ADMIN_USER_IDS", "").split(",")
        
        if not all([self.bot_token, self.app_token, self.channel_id]):
            logger.warning("Slack environment variables missing. SlackAdapter will be disabled.")
            self.app = None
            return

        self.app = App(token=self.bot_token)
        self._register_handlers()

    def _register_handlers(self):
        self.app.action("approve_job")(self.handle_approve)
        self.app.action("reject_request")(self.open_reject_modal)
        self.app.view("reject_submission")(self.handle_reject_submission)

    def is_authorized(self, user_id: str) -> bool:
        """Check if user_id is in the admin whitelist."""
        # Fail-Closed: 管理者IDが未設定の場合は全拒否
        if not self.admin_ids or self.admin_ids == [""]:
            logger.error("No SLACK_ADMIN_USER_IDS configured. Rejecting all HITL actions for safety.")
            return False
        return user_id in self.admin_ids

    def _unauthorized_response(self, client, channel, user_id):
        """Send ephemeral message to unauthorized user."""
        try:
            client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text="⚠️ *Access Denied*: You are not authorized to perform HITL actions in this system."
            )
        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")

    def send_audit_notification(self, job_id: str, artifact_path: str):
        """Notify Slack about a job pending audit."""
        if not self.app:
            return

        job_path = get_job_path(job_id)
        if not job_path.exists():
            logger.error(f"Job file not found for notification: {job_id}")
            return

        fm, body = read_frontmatter(job_path)

        # Prevent duplicate notifications
        if fm.get("slack_ts"):
            return

        blocks = self._build_audit_blocks(job_id, artifact_path)
        try:
            response = self.app.client.chat_postMessage(
                channel=self.channel_id,
                blocks=blocks,
                text=f"🔍 Audit Pending: {job_id}"
            )
            # Store slack_ts in job file
            fm["slack_ts"] = response["ts"]
            write_frontmatter(job_path, fm, body)
            logger.info(f"Slack notification sent for {job_id} (ts: {response['ts']})")
        except Exception as e:
            logger.error(f"Failed to send Slack notification for {job_id}: {e}")

    def handle_approve(self, ack, body, client):
        """Handle Approve button click (Gate 2 Only)."""
        ack()
        user_id = body["user"]["id"]
        if not self.is_authorized(user_id):
            return self._unauthorized_response(client, body["channel"]["id"], user_id)

        job_id = body["actions"][0]["value"]
        job_path = get_job_path(job_id)
        approver = body["user"]["username"]
        
        logger.info(f"Approve request (Gate 2) from Slack for {job_id} by @{approver}")

        try:
            fm, b = read_frontmatter(job_path)
            current_status = fm.get("status", "created")
            
            # STRICT STATE CHECK: Gate 2 only
            if current_status != "audit_passed":
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=f"⚠️ *Approval Denied*: Slack Approve is only allowed for jobs in `audit_passed` state. Current state: `{current_status}`"
                )
                return

            # Transition to approved_gate_2
            fm["status"] = "approved_gate_2"
            fm["approved_gate_2_by"] = approver
            fm["approved_gate_2_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_frontmatter(job_path, fm, b)

            # Update message to show processed state
            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"✅ *Gate 2 Approved by @{approver}* at {time.strftime('%H:%M')} (UTC)\nJob: `{job_id}`"}
                    }
                ],
                text=f"✅ Gate 2 Approved: {job_id}"
            )
        except Exception as e:
            logger.error(f"Failed to process Slack approval for {job_id}: {e}")

    def open_reject_modal(self, ack, body, client):
        """Open modal to collect rejection reason."""
        ack()
        user_id = body["user"]["id"]
        if not self.is_authorized(user_id):
            return self._unauthorized_response(client, body["channel"]["id"], user_id)

        job_id = body["actions"][0]["value"]
        try:
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "reject_submission",
                    "private_metadata": job_id,
                    "title": {"type": "plain_text", "text": "Reject Reason"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "reason_block",
                            "element": {
                                "type": "plain_text_input", 
                                "action_id": "reason_input", 
                                "multiline": True,
                                "placeholder": {"type": "plain_text", "text": "Describe why this job was rejected..."}
                            },
                            "label": {"type": "plain_text", "text": "Feedback"}
                        }
                    ],
                    "submit": {"type": "plain_text", "text": "Submit Reject"}
                }
            )
        except Exception as e:
            logger.error(f"Failed to open Slack modal for {job_id}: {e}")

    def handle_reject_submission(self, ack, body, view, client):
        """Handle modal submission for rejection (Gate 2 Only)."""
        ack()
        user_id = body["user"]["id"]
        if not self.is_authorized(user_id):
            return 
        
        job_id = view["private_metadata"]
        reason = view["state"]["values"]["reason_block"]["reason_input"]["value"]
        approver = body["user"]["name"]
        job_path = get_job_path(job_id)

        logger.info(f"Reject submission (Gate 2) from Slack for {job_id} by @{approver}")

        try:
            fm, b = read_frontmatter(job_path)
            current_status = fm.get("status", "created")

            # STRICT STATE CHECK: Gate 2 only
            if current_status != "audit_passed":
                client.chat_postEphemeral(
                    channel=self.channel_id,
                    user=user_id,
                    text=f"⚠️ *Rejection Denied*: Slack Reject is only allowed for jobs in `audit_passed` state. Current state: `{current_status}`"
                )
                return

            # Transition to gate_2_rejected
            fm["status"] = "gate_2_rejected"
            fm["rejected_gate"] = 2
            fm["rejected_by"] = approver
            fm["rejected_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            fm["reject_reason"] = reason
            
            # Append feedback to body
            header = "\n\n## Reject Feedback (Gate 2)\n"
            b = b + header + reason + "\n"
            write_frontmatter(job_path, fm, b)

            # Update original message if slack_ts exists
            slack_ts = fm.get("slack_ts")
            if slack_ts:
                client.chat_update(
                    channel=self.channel_id,
                    ts=slack_ts,
                    blocks=[
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"❌ *Gate 2 Rejected by @{approver}*\nReason: _{reason}_\nJob: `{job_id}`"}
                        }
                    ],
                    text=f"❌ Rejected: {job_id}"
                )
        except Exception as e:
            logger.error(f"Failed to process Slack rejection for {job_id}: {e}")

    def _build_audit_blocks(self, job_id, artifact_path):
        return [
            {
                "type": "header", 
                "text": {"type": "plain_text", "text": f"🔍 Gate 2 Audit Pending: {job_id}"}
            },
            {
                "type": "section", 
                "text": {"type": "mrkdwn", "text": f"A generated artifact is ready for *Gate 2* review:\n`{artifact_path}`\n\nPlease approve to stage for promotion, or reject with feedback."}
            },
            {
                "type": "actions", 
                "elements": [
                    {
                        "type": "button", 
                        "text": {"type": "plain_text", "text": "Approve ✅"}, 
                        "style": "primary", 
                        "action_id": "approve_job", 
                        "value": job_id
                    },
                    {
                        "type": "button", 
                        "text": {"type": "plain_text", "text": "Reject ❌"}, 
                        "style": "danger", 
                        "action_id": "reject_request", 
                        "value": job_id
                    }
                ]
            }
        ]

    def run_in_background(self):
        """Start Socket Mode handler in background."""
        if not self.app or not self.app_token:
            return
        handler = SocketModeHandler(self.app, self.app_token)
        handler.connect()
        return handler

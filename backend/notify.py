"""
api/notify.py — Dropot Notification System
Handles: Notify pending members before dismantling
Uses Gmail API to send email via admin's account
"""

import os
import json
import base64
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
from email.mime.text import MIMEText

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://code-manigopal.github.io/dropot")


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        auth   = self.headers.get("Authorization", "")
        body   = self._body()

        if not auth.startswith("Bearer "):
            self._json({"error": "Unauthorized"}, 401)
            return

        access_token = auth.replace("Bearer ", "").strip()

        # POST /api/notify/pending — notify members who haven't flagged done
        if path.endswith("/pending"):
            group_name    = body.get("groupName", "your group")
            group_id      = body.get("groupId")
            pending       = body.get("pendingMembers", [])  # [{name, email}]
            admin_name    = body.get("adminName", "The admin")

            sent = []
            failed = []

            for member in pending:
                email   = member.get("email")
                name    = member.get("name", "there")
                subject = f"📥 Action needed — Download your files from {group_name} on Dropot"
                body_text = f"""Hi {name},

{admin_name} is preparing to dismantle the Dropot group "{group_name}".

Before the group is closed, please:
1. Visit the group on Dropot
2. Download any files you want to keep
3. Click the ✅ "I'm Done Downloading" button

Once all members flag Done, the admin can proceed with dismantling and all files will be permanently deleted.

Visit your group here:
{FRONTEND_URL}/group.html?id={group_id}

— The Dropot Team
"""
                success = self._send_email(access_token, email, subject, body_text)
                if success:
                    sent.append(email)
                else:
                    failed.append(email)

            self._json({"sent": sent, "failed": failed})
            return

        self._json({"error": "Not found"}, 404)

    def _send_email(self, access_token, to, subject, body_text):
        """Send email via Gmail API"""
        try:
            msg = MIMEText(body_text)
            msg["to"]      = to
            msg["subject"] = subject

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            res = requests.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type":  "application/json"
                },
                json={"raw": raw}
            )
            return res.status_code == 200
        except Exception as e:
            print(f"Email error: {e}")
            return False

    # ── Helpers ──────────────────────────────────────────
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  FRONTEND_URL)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self._cors()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            try:
                return json.loads(self.rfile.read(length))
            except Exception:
                return {}
        return {}

    def log_message(self, *args):
        pass

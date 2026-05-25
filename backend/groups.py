"""
api/groups.py — Dropot Group Management
Handles: Create group, get group, update member done flag, dismantle group
Uses Firebase Admin SDK to read/write Firestore
"""

import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://code-manigopal.github.io/dropot")

# Init Firebase Admin (once)
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type":                        "service_account",
        "project_id":                  os.environ.get("FIREBASE_PROJECT_ID"),
        "private_key_id":              os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
        "private_key":                 os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email":                os.environ.get("FIREBASE_CLIENT_EMAIL"),
        "client_id":                   os.environ.get("FIREBASE_CLIENT_ID"),
        "auth_uri":                    "https://accounts.google.com/o/oauth2/auth",
        "token_uri":                   "https://oauth2.googleapis.com/token",
    })
    firebase_admin.initialize_app(cred)

db = firestore.client()


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        # GET /api/groups/get?id=GROUP_ID
        if path.endswith("/get"):
            group_id = qs.get("id", [None])[0]
            if not group_id:
                self._json({"error": "Missing group id"}, 400)
                return
            doc = db.collection("groups").document(group_id).get()
            if not doc.exists:
                self._json({"error": "Group not found"}, 404)
                return
            self._json({"id": doc.id, **doc.to_dict()})
            return

        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        body   = self._body()

        # POST /api/groups/create
        if path.endswith("/create"):
            name     = body.get("name")
            desc     = body.get("desc", "")
            admin_id = body.get("adminId")
            admin_name = body.get("adminName")
            admin_email = body.get("adminEmail")

            if not all([name, admin_id]):
                self._json({"error": "Missing required fields"}, 400)
                return

            group_data = {
                "name":      name,
                "desc":      desc,
                "adminId":   admin_id,
                "adminName": admin_name,
                "status":    "active",
                "memberIds": [admin_id],
                "members": [{
                    "uid":      admin_id,
                    "name":     admin_name,
                    "email":    admin_email,
                    "done":     False,
                    "joinedAt": firestore.SERVER_TIMESTAMP
                }],
                "createdAt": firestore.SERVER_TIMESTAMP
            }

            ref = db.collection("groups").add(group_data)
            self._json({"id": ref[1].id, "name": name})
            return

        # POST /api/groups/join
        if path.endswith("/join"):
            group_id = body.get("groupId")
            uid      = body.get("uid")
            name     = body.get("name")
            email    = body.get("email")

            if not all([group_id, uid]):
                self._json({"error": "Missing required fields"}, 400)
                return

            ref = db.collection("groups").document(group_id)
            doc = ref.get()
            if not doc.exists:
                self._json({"error": "Group not found"}, 404)
                return

            data = doc.to_dict()
            if uid in data.get("memberIds", []):
                self._json({"message": "Already a member", "id": group_id})
                return

            ref.update({
                "memberIds": firestore.ArrayUnion([uid]),
                "members":   firestore.ArrayUnion([{
                    "uid":      uid,
                    "name":     name,
                    "email":    email,
                    "done":     False,
                    "joinedAt": firestore.SERVER_TIMESTAMP
                }])
            })
            self._json({"message": "Joined successfully", "id": group_id})
            return

        # POST /api/groups/done — flag member as done
        if path.endswith("/done"):
            group_id = body.get("groupId")
            uid      = body.get("uid")

            if not all([group_id, uid]):
                self._json({"error": "Missing required fields"}, 400)
                return

            ref  = db.collection("groups").document(group_id)
            doc  = ref.get()
            if not doc.exists:
                self._json({"error": "Group not found"}, 404)
                return

            data    = doc.to_dict()
            members = data.get("members", [])
            updated = [
                {**m, "done": True} if m["uid"] == uid else m
                for m in members
            ]
            ref.update({"members": updated})

            all_done = all(m["done"] for m in updated)
            self._json({"success": True, "allDone": all_done})
            return

        # POST /api/groups/dismantle — admin only, delete group + notify
        if path.endswith("/dismantle"):
            group_id = body.get("groupId")
            uid      = body.get("uid")

            if not all([group_id, uid]):
                self._json({"error": "Missing required fields"}, 400)
                return

            ref = db.collection("groups").document(group_id)
            doc = ref.get()
            if not doc.exists:
                self._json({"error": "Group not found"}, 404)
                return

            data = doc.to_dict()
            if data.get("adminId") != uid:
                self._json({"error": "Only admin can dismantle"}, 403)
                return

            # Delete all files subcollection
            files_ref = ref.collection("files")
            for f in files_ref.stream():
                f.reference.delete()

            # Delete group document
            ref.delete()
            self._json({"success": True, "message": "Group dismantled"})
            return

        self._json({"error": "Not found"}, 404)

    # ── Helpers ──────────────────────────────────────────
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  FRONTEND_URL)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
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

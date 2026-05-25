"""
api/drive.py — Dropot Google Drive Bridge
Handles: Upload file to user's Drive, delete file, list group files
All files are tagged with a group ID so only group files get deleted on dismantling.
"""

import os
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import io

FRONTEND_URL      = os.environ.get("FRONTEND_URL", "https://code-manigopal.github.io/dropot")
DROPOT_FOLDER     = "Dropot"   # Folder created in user's Drive


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        auth   = self.headers.get("Authorization", "")

        if not auth.startswith("Bearer "):
            self._json({"error": "Unauthorized"}, 401)
            return

        access_token = auth.replace("Bearer ", "").strip()

        # POST /api/drive/upload
        if path.endswith("/upload"):
            body = self._body()
            file_name    = body.get("name")
            file_content = body.get("content")   # base64 encoded
            file_type    = body.get("type", "application/octet-stream")
            group_id     = body.get("groupId")

            if not all([file_name, file_content, group_id]):
                self._json({"error": "Missing required fields"}, 400)
                return

            import base64
            file_bytes = base64.b64decode(file_content)

            # Get or create Dropot folder in user's Drive
            folder_id = self._get_or_create_folder(access_token, group_id)
            if not folder_id:
                self._json({"error": "Could not create Drive folder"}, 500)
                return

            # Upload file to Drive
            result = self._upload_to_drive(
                access_token, file_name, file_bytes, file_type, folder_id, group_id
            )

            if "error" in result:
                self._json(result, 500)
                return

            self._json({
                "fileId":   result["id"],
                "name":     result["name"],
                "url":      f"https://drive.google.com/uc?id={result['id']}&export=download",
                "viewUrl":  f"https://drive.google.com/file/d/{result['id']}/view",
                "groupId":  group_id
            })
            return

        # POST /api/drive/delete
        if path.endswith("/delete"):
            body    = self._body()
            file_id = body.get("fileId")
            if not file_id:
                self._json({"error": "Missing fileId"}, 400)
                return

            res = requests.delete(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if res.status_code in (200, 204):
                self._json({"success": True})
            else:
                self._json({"error": "Delete failed", "status": res.status_code}, 500)
            return

        self._json({"error": "Not found"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        auth   = self.headers.get("Authorization", "")

        if not auth.startswith("Bearer "):
            self._json({"error": "Unauthorized"}, 401)
            return

        access_token = auth.replace("Bearer ", "").strip()

        # GET /api/drive/storage — get user's Drive storage quota
        if path.endswith("/storage"):
            res = requests.get(
                "https://www.googleapis.com/drive/v3/about?fields=storageQuota",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            data = res.json()
            quota = data.get("storageQuota", {})
            self._json({
                "limit": int(quota.get("limit", 0)),
                "usage": int(quota.get("usage", 0)),
                "free":  int(quota.get("limit", 0)) - int(quota.get("usage", 0))
            })
            return

        self._json({"error": "Not found"}, 404)

    # ── Drive Helpers ─────────────────────────────────────

    def _get_or_create_folder(self, access_token, group_id):
        """Get or create a folder named 'Dropot-{groupId}' in user's Drive"""
        folder_name = f"Dropot-{group_id}"
        headers     = {"Authorization": f"Bearer {access_token}"}

        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res   = requests.get(
            f"https://www.googleapis.com/drive/v3/files?q={requests.utils.quote(query)}&fields=files(id,name)",
            headers=headers
        )
        files = res.json().get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        res = requests.post(
            "https://www.googleapis.com/drive/v3/files",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "name":     folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "description": f"Dropot group files — Group ID: {group_id}"
            }
        )
        folder = res.json()
        return folder.get("id")

    def _upload_to_drive(self, access_token, name, content, mime_type, folder_id, group_id):
        """Upload file to Drive using multipart upload"""
        headers = {"Authorization": f"Bearer {access_token}"}

        metadata = {
            "name":        name,
            "parents":     [folder_id],
            "description": f"dropot-group:{group_id}",
            "appProperties": {"dropotGroupId": group_id}
        }

        import base64
        boundary = "dropot_boundary_xyz"
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n"
            f"Content-Transfer-Encoding: base64\r\n\r\n"
            f"{base64.b64encode(content).decode()}\r\n"
            f"--{boundary}--"
        )

        res = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name",
            headers={
                **headers,
                "Content-Type": f"multipart/related; boundary={boundary}"
            },
            data=body.encode()
        )
        return res.json()

    # ── Generic Helpers ───────────────────────────────────
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

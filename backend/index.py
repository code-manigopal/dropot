"""
api/index.py — Dropot Flask Backend
All routes in one file for Vercel Python deployment.
"""

import os
import json
import base64
import requests
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from urllib.parse import urlencode
from email.mime.text import MIMEText

# ── Firebase Admin ────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore

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

# ── Flask App ─────────────────────────────────────────
app = Flask(__name__)

FRONTEND_URL         = os.environ.get("FRONTEND_URL", "https://code-manigopal.github.io/dropot")
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI         = os.environ.get("REDIRECT_URI", "https://dropot.vercel.app/api/auth/callback")

CORS(app, origins=["https://code-manigopal.github.io"], supports_credentials=True)

SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://mail.google.com/"
]

# ── Health Check ──────────────────────────────────────
@app.route("/")
def index():
    return jsonify({"status": "Dropot API is live 🫕"})

# ══════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════

@app.route("/api/auth/login")
def auth_login():
    """Redirect to Google OAuth"""
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(url)


@app.route("/api/auth/callback")
def auth_callback():
    """Exchange code for tokens, redirect to frontend"""
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return redirect(f"{FRONTEND_URL}?error=auth_failed")

    # Exchange code for tokens
    token_res = requests.post("https://oauth2.googleapis.com/token", data={
        "code":          code,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code"
    })
    tokens = token_res.json()

    if "error" in tokens:
        return redirect(f"{FRONTEND_URL}?error=token_failed")

    access_token  = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    # Get user info
    user_res  = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user = user_res.json()

    # Redirect to dashboard with tokens in fragment
    return redirect(
        f"{FRONTEND_URL}/dashboard.html"
        f"#access_token={access_token}"
        f"&refresh_token={refresh_token}"
        f"&email={user.get('email','')}"
        f"&name={user.get('name','')}"
    )


@app.route("/api/auth/refresh", methods=["POST"])
def auth_refresh():
    """Refresh access token"""
    data          = request.get_json() or {}
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({"error": "Missing refresh_token"}), 400

    res = requests.post("https://oauth2.googleapis.com/token", data={
        "refresh_token": refresh_token,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type":    "refresh_token"
    })
    return jsonify(res.json())


# ══════════════════════════════════════════════════════
# DRIVE ROUTES
# ══════════════════════════════════════════════════════

@app.route("/api/drive/upload", methods=["POST"])
def drive_upload():
    """Upload file to user's Google Drive"""
    token = _get_token()
    if not token:
        return jsonify({"error": "Unauthorized"}), 401

    data         = request.get_json() or {}
    file_name    = data.get("name")
    file_content = data.get("content")  # base64
    file_type    = data.get("type", "application/octet-stream")
    group_id     = data.get("groupId")

    if not all([file_name, file_content, group_id]):
        return jsonify({"error": "Missing required fields"}), 400

    file_bytes = base64.b64decode(file_content)
    headers    = {"Authorization": f"Bearer {token}"}

    # Get or create group folder
    folder_id = _get_or_create_folder(token, group_id)
    if not folder_id:
        return jsonify({"error": "Could not create Drive folder"}), 500

    # Upload file
    boundary = "dropot_boundary"
    metadata = json.dumps({
        "name":          file_name,
        "parents":       [folder_id],
        "description":   f"dropot-group:{group_id}",
        "appProperties": {"dropotGroupId": group_id}
    })

    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{metadata}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {file_type}\r\n"
        f"Content-Transfer-Encoding: base64\r\n\r\n"
        f"{base64.b64encode(file_bytes).decode()}\r\n"
        f"--{boundary}--"
    )

    res = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files"
        "?uploadType=multipart&fields=id,name",
        headers={**headers, "Content-Type": f"multipart/related; boundary={boundary}"},
        data=body.encode()
    )
    result = res.json()

    if "error" in result:
        return jsonify(result), 500

    return jsonify({
        "fileId":  result["id"],
        "name":    result["name"],
        "url":     f"https://drive.google.com/uc?id={result['id']}&export=download",
        "viewUrl": f"https://drive.google.com/file/d/{result['id']}/view",
        "groupId": group_id
    })


@app.route("/api/drive/delete", methods=["POST"])
def drive_delete():
    """Delete file from Google Drive"""
    token = _get_token()
    if not token:
        return jsonify({"error": "Unauthorized"}), 401

    data    = request.get_json() or {}
    file_id = data.get("fileId")

    if not file_id:
        return jsonify({"error": "Missing fileId"}), 400

    res = requests.delete(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if res.status_code in (200, 204):
        return jsonify({"success": True})
    return jsonify({"error": "Delete failed"}), 500


@app.route("/api/drive/storage")
def drive_storage():
    """Get user's Drive storage quota"""
    token = _get_token()
    if not token:
        return jsonify({"error": "Unauthorized"}), 401

    res   = requests.get(
        "https://www.googleapis.com/drive/v3/about?fields=storageQuota",
        headers={"Authorization": f"Bearer {token}"}
    )
    quota = res.json().get("storageQuota", {})
    limit = int(quota.get("limit", 0))
    usage = int(quota.get("usage", 0))

    return jsonify({
        "limit": limit,
        "usage": usage,
        "free":  limit - usage
    })


# ══════════════════════════════════════════════════════
# GROUPS ROUTES
# ══════════════════════════════════════════════════════

@app.route("/api/groups/get")
def groups_get():
    """Get group by ID"""
    group_id = request.args.get("id")
    if not group_id:
        return jsonify({"error": "Missing id"}), 400

    doc = db.collection("groups").document(group_id).get()
    if not doc.exists:
        return jsonify({"error": "Group not found"}), 404

    return jsonify({"id": doc.id, **doc.to_dict()})


@app.route("/api/groups/create", methods=["POST"])
def groups_create():
    """Create a new group"""
    data        = request.get_json() or {}
    name        = data.get("name")
    desc        = data.get("desc", "")
    admin_id    = data.get("adminId")
    admin_name  = data.get("adminName")
    admin_email = data.get("adminEmail")

    if not all([name, admin_id]):
        return jsonify({"error": "Missing required fields"}), 400

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
    return jsonify({"id": ref[1].id, "name": name})


@app.route("/api/groups/join", methods=["POST"])
def groups_join():
    """Join an existing group"""
    data     = request.get_json() or {}
    group_id = data.get("groupId")
    uid      = data.get("uid")
    name     = data.get("name")
    email    = data.get("email")

    if not all([group_id, uid]):
        return jsonify({"error": "Missing required fields"}), 400

    ref = db.collection("groups").document(group_id)
    doc = ref.get()

    if not doc.exists:
        return jsonify({"error": "Group not found"}), 404

    group = doc.to_dict()
    if uid in group.get("memberIds", []):
        return jsonify({"message": "Already a member", "id": group_id})

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
    return jsonify({"message": "Joined successfully", "id": group_id})


@app.route("/api/groups/done", methods=["POST"])
def groups_done():
    """Flag member as done downloading"""
    data     = request.get_json() or {}
    group_id = data.get("groupId")
    uid      = data.get("uid")

    if not all([group_id, uid]):
        return jsonify({"error": "Missing required fields"}), 400

    ref = db.collection("groups").document(group_id)
    doc = ref.get()
    if not doc.exists:
        return jsonify({"error": "Group not found"}), 404

    members = doc.to_dict().get("members", [])
    updated = [{**m, "done": True} if m["uid"] == uid else m for m in members]
    ref.update({"members": updated})

    all_done = all(m["done"] for m in updated)
    return jsonify({"success": True, "allDone": all_done})


@app.route("/api/groups/dismantle", methods=["POST"])
def groups_dismantle():
    """Admin dismantles group — deletes all files and group"""
    data     = request.get_json() or {}
    group_id = data.get("groupId")
    uid      = data.get("uid")

    if not all([group_id, uid]):
        return jsonify({"error": "Missing required fields"}), 400

    ref = db.collection("groups").document(group_id)
    doc = ref.get()
    if not doc.exists:
        return jsonify({"error": "Group not found"}), 404

    if doc.to_dict().get("adminId") != uid:
        return jsonify({"error": "Only admin can dismantle"}), 403

    # Delete files subcollection
    for f in ref.collection("files").stream():
        f.reference.delete()

    # Delete group
    ref.delete()
    return jsonify({"success": True, "message": "Group dismantled"})


# ══════════════════════════════════════════════════════
# NOTIFY ROUTES
# ══════════════════════════════════════════════════════

@app.route("/api/notify/pending", methods=["POST"])
def notify_pending():
    """Email members who haven't flagged done yet"""
    token = _get_token()
    if not token:
        return jsonify({"error": "Unauthorized"}), 401

    data           = request.get_json() or {}
    group_name     = data.get("groupName", "your group")
    group_id       = data.get("groupId")
    pending        = data.get("pendingMembers", [])
    admin_name     = data.get("adminName", "The admin")

    sent   = []
    failed = []

    for member in pending:
        email   = member.get("email")
        name    = member.get("name", "there")
        subject = f"📥 Action needed — Download your files from {group_name} on Dropot"
        body    = f"""Hi {name},

{admin_name} is preparing to dismantle the Dropot group "{group_name}".

Before the group is closed, please:
1. Visit the group on Dropot
2. Download any files you want to keep
3. Click the ✅ "I'm Done Downloading" button

Visit your group here:
{FRONTEND_URL}/group.html?id={group_id}

— The Dropot Team
"""
        if _send_email(token, email, subject, body):
            sent.append(email)
        else:
            failed.append(email)

    return jsonify({"sent": sent, "failed": failed})


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _get_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.replace("Bearer ", "").strip()
    return None


def _get_or_create_folder(token, group_id):
    """Get or create Dropot-{groupId} folder in user's Drive"""
    folder_name = f"Dropot-{group_id}"
    headers     = {"Authorization": f"Bearer {token}"}

    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res   = requests.get(
        f"https://www.googleapis.com/drive/v3/files"
        f"?q={requests.utils.quote(query)}&fields=files(id,name)",
        headers=headers
    )
    files = res.json().get("files", [])
    if files:
        return files[0]["id"]

    res = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "name":        folder_name,
            "mimeType":    "application/vnd.google-apps.folder",
            "description": f"Dropot group files — Group ID: {group_id}"
        }
    )
    return res.json().get("id")


def _send_email(token, to, subject, body_text):
    """Send email via Gmail API"""
    try:
        msg            = MIMEText(body_text)
        msg["to"]      = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        res = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json"
            },
            json={"raw": raw}
        )
        return res.status_code == 200
    except Exception as e:
        print(f"Email error: {e}")
        return False
"""
api/auth.py — Dropot Google OAuth Handler
Handles: OAuth login, callback, token exchange, token refresh
"""

import os
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
FRONTEND_URL         = os.environ.get("FRONTEND_URL", "https://code-manigopal.github.io/dropot")
REDIRECT_URI         = os.environ.get("VERCEL_URL", "https://dropot-api.vercel.app")
REDIRECT_URI         = f"https://{REDIRECT_URI}/api/auth/callback" if not REDIRECT_URI.startswith("http") else f"{REDIRECT_URI}/api/auth/callback"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file"
]

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # GET /api/auth/login — redirect to Google OAuth
        if path.endswith("/login"):
            params = {
                "client_id":     GOOGLE_CLIENT_ID,
                "redirect_uri":  REDIRECT_URI,
                "response_type": "code",
                "scope":         " ".join(SCOPES),
                "access_type":   "offline",
                "prompt":        "consent",
            }
            url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
            self._cors()
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()
            return

        # GET /api/auth/callback — exchange code for tokens
        if path.endswith("/callback"):
            qs   = parse_qs(parsed.query)
            code = qs.get("code", [None])[0]

            if not code:
                self._json({"error": "No code received"}, 400)
                return

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
                self._json({"error": tokens["error"]}, 400)
                return

            access_token  = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")

            # Get user info
            user_res  = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"})
            user_info = user_res.json()

            # Redirect back to frontend with tokens in URL fragment
            redirect = (
                f"{FRONTEND_URL}/dashboard.html"
                f"#access_token={access_token}"
                f"&refresh_token={refresh_token}"
                f"&email={user_info.get('email','')}"
                f"&name={user_info.get('name','')}"
            )

            self._cors()
            self.send_response(302)
            self.send_header("Location", redirect)
            self.end_headers()
            return

        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        body   = self._body()

        # POST /api/auth/refresh — refresh access token
        if path.endswith("/refresh"):
            refresh_token = body.get("refresh_token")
            if not refresh_token:
                self._json({"error": "No refresh token"}, 400)
                return

            res = requests.post("https://oauth2.googleapis.com/token", data={
                "refresh_token": refresh_token,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type":    "refresh_token"
            })
            self._json(res.json())
            return

        self._json({"error": "Not found"}, 404)

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

# 🫕 Dropot

> *"Multiple droplets of water become the ocean."*

Dropot is a transparent, federated media sharing platform where groups pool their Google Drive storage into one shared space — upload, download, and when everyone is done, the admin dismantles everything cleanly.

**Live URL:** `https://code-manigopal.github.io/dropot`

---

## 🌊 The Concept

Like a potluck — everyone brings something, everyone consumes freely, and when the party is over, the host cleans up. No hidden storage. No black boxes. Full transparency.

---

## 🏗️ Project Structure

```
dropot/
├── frontend/               ← Hosted on GitHub Pages (code-manigopal.github.io/dropot)
│   ├── index.html          ← Landing page / Sign-in flow
│   ├── dashboard.html      ← Main group dashboard
│   ├── group.html          ← Group view (upload, download, Done flag)
│   ├── css/
│   │   └── style.css       ← Global styles (teal palette)
│   ├── js/
│   │   ├── auth.js         ← Google OAuth flow
│   │   ├── group.js        ← Group create/join/manage logic
│   │   ├── storage.js      ← Google Drive integration
│   │   └── app.js          ← Main app logic
│   └── assets/
│       └── logo.svg        ← Dropot logo (photo+video icons falling into pot)
│
├── backend/                ← Hosted on Vercel (serverless functions)
│   ├── api/
│   │   ├── auth.py         ← Google OAuth handler
│   │   ├── groups.py       ← Group CRUD operations
│   │   ├── storage.py      ← Google Drive API bridge
│   │   ├── members.py      ← Member management (join, leave, done flag)
│   │   └── notify.py       ← Email/dashboard notifications
│   ├── requirements.txt    ← Python dependencies
│   └── vercel.json         ← Vercel deployment config
│
├── docs/
│   ├── PROMPT_LOG.txt      ← Full prompt history (GitHub tracking)
│   └── StoragePlatform_ConceptDoc.docx  ← Full concept document
│
├── .gitignore
└── README.md               ← This file
```

---

## 🎨 Design System

| Token | Value | Usage |
|---|---|---|
| Primary Dark | `#1F6F5F` | Header, sidebar, buttons |
| Primary Mid | `#2FA084` | Active states, ocean pool UI |
| Accent Green | `#6FCF97` | ✅ Done flag, success states |
| Neutral | `#EEEEEE` | Backgrounds, cards |
| Font | System default | Clean, no dependencies |

---

## 🔑 Tech Stack

| Layer | Technology | Hosting | Cost |
|---|---|---|---|
| Frontend | HTML + CSS + JS | GitHub Pages | Free |
| Backend | Python (Vercel serverless) | Vercel | Free |
| Auth | Google OAuth 2.0 | Google Cloud | Free |
| Storage | Google Drive API | User's own Drive | Free |
| Database | Firebase Firestore (free tier) | Firebase | Free |

**Total running cost: $0** until significant scale.

---

## 🚀 Setup Guide

### Step 1 — Fork & Clone
```bash
# On GitHub: fork this repo to your account
# Then clone it locally
git clone https://github.com/code-manigopal/dropot.git
cd dropot
```

### Step 2 — Frontend (GitHub Pages)
```bash
# No build step needed — pure HTML/CSS/JS
# Just push to GitHub and enable Pages

# Go to: GitHub repo → Settings → Pages
# Source: Deploy from branch → main → /frontend
# Your site will be live at:
# https://code-manigopal.github.io/dropot
```

### Step 3 — Backend (Vercel)
```bash
# Install Vercel CLI (one time only)
npm install -g vercel

# From the backend folder
cd backend
pip install -r requirements.txt

# Deploy to Vercel
vercel

# Follow the prompts — free account, no credit card needed
# Your backend will be live at:
# https://dropot-api.vercel.app
```

### Step 4 — Google OAuth Setup (one time only)
```
1. Go to console.cloud.google.com
2. Create a new project → name it "Dropot"
3. Enable: Google Drive API + Google OAuth 2.0
4. Create OAuth credentials → Web Application
5. Add authorized origin: https://code-manigopal.github.io
6. Add redirect URI: https://dropot-api.vercel.app/api/auth/callback
7. Copy Client ID + Client Secret → add to Vercel environment variables
```

### Step 5 — Firebase Setup (one time only)
```
1. Go to console.firebase.google.com
2. Create project → name it "Dropot"
3. Enable Firestore Database (free tier)
4. Copy config → add to Vercel environment variables
```

### Step 6 — Environment Variables on Vercel
```
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_PRIVATE_KEY=your_private_key
FRONTEND_URL=https://code-manigopal.github.io/dropot
```

---

## 👤 User Flow

```
1. User opens code-manigopal.github.io/dropot
2. ⚠️  Advisory modal appears (dedicated account warning)
3. User reads ToS checklist + checks the box
4. Signs in with Google OAuth
5. Creates a group OR joins via invite code
6. Uploads media → lands in shared ocean pool
7. Downloads what they want → clicks ✅ Done
8. Admin sees all-green dashboard → dismantles group
9. All files permanently deleted from connected Drives
```

---

## 📋 Group Lifecycle

```
[Admin Creates Group]
        ↓
[Members Join via Invite Code]
        ↓
[Everyone Contributes Google Drive Storage]
        ↓
[Upload & Download Freely]
        ↓
[Member wants to leave?]
  → Sends leave request
  → Admin notified
  → Conversation → Approve / Reject
        ↓
[Admin initiates Dismantling]
        ↓
[All members get notification → Download remaining files]
        ↓
[Each member clicks ✅ Done]
        ↓
[All flags green → Admin gets Dismantle button]
        ↓
[Group permanently deleted]
```

---

## 📁 Docs

- `docs/PROMPT_LOG.txt` — Every prompt from Mani during product design (educational vibe coding)
- `docs/StoragePlatform_ConceptDoc.docx` — Full concept document

---

## 🗺️ Roadmap

- [x] Concept & design decisions
- [x] Naming (Dropot)
- [x] Colour palette
- [x] Project structure
- [ ] Frontend UI (sign-in, advisory modal, ToS)
- [ ] Google OAuth integration
- [ ] Group creation & invite flow
- [ ] Google Drive storage pooling
- [ ] Upload / download interface
- [ ] Done flag system
- [ ] Admin dashboard
- [ ] Dismantling flow
- [ ] Mobile app (Android + iOS)

---

## 📜 License

Private project — all rights reserved © Mani, 2026

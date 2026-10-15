# 🤖 ACR_AGENT — AI-Powered Autonomous Code Repair Agent

ACR_AGENT is an AI-powered autonomous DevOps and code-repair platform that analyzes GitHub repositories, detects software issues, uses Gemini AI to generate and apply fixes, validates the changes, and creates a Pull Request with the repaired code.

The system combines a **Next.js web interface**, **FastAPI backend**, **Socket.IO real-time communication**, **Docker-based isolated execution**, **Gemini AI**, and **GitHub API integration** into a single automated workflow.

---

## 📌 Table of Contents

* [Overview](#-overview)
* [Key Features](#-key-features)
* [How ACR_AGENT Works](#-how-acr_agent-works)
* [System Architecture](#-system-architecture)
* [Project Structure](#-project-structure)
* [Technology Stack](#-technology-stack)
* [Core Workflow](#-core-workflow)
* [Frontend](#-frontend)
* [Backend](#-backend)
* [AI Code Repair](#-ai-code-repair)
* [GitHub Integration](#-github-integration)
* [Docker Execution](#-docker-execution)
* [Authentication](#-authentication)
* [Environment Variables](#-environment-variables)
* [Installation](#-installation)
* [Running the Application](#-running-the-application)
* [Using ACR_AGENT](#-using-acr_agent)
* [API](#-api)
* [Real-Time Events](#-real-time-events)
* [Output](#-output)
* [Security](#-security)
* [Troubleshooting](#-troubleshooting)
* [Future Enhancements](#-future-enhancements)

---

# 🎯 Overview

## Current implementation status (October 2026)

The Python backend is type-checked and compiles successfully. The dashboard route is now `/dashboard` and consumes real Socket.IO worker events. The prior simulated `/test` run and its fake PR URL were removed; `/test` now displays the same real dashboard for compatibility.

The two assistants are deliberately separate:

- **AURA AI** at the top right answers general programming and DevOps questions through the Gemini API. It receives only the question explicitly typed by the user; pipeline logs and credentials are never sent to it.
- **Pipeline Assistant** uses only the actual stage, Socket.IO logs, verified fixes, and verified PR data from the live browser session. It does not call Gemini and does not invent pipeline data.

The previous human/team image is replaced by the local `frontend/public/simple-ai-bot.svg` image. It does not need an image-generation API or another secret.

### Database and authentication (current implementation)

The active project uses **SQLite**, a free SQL database included with Python. It
does not require PostgreSQL, Supabase, Prisma, a connection pool, or a database
container. On first backend startup, `backend/data/acr_agent.sqlite3` is created
automatically. Login and signup store salted PBKDF2 password hashes and use an
HTTP-only session cookie; the dashboard and pipeline socket require that session.

The old `CICD\ACR_AGENT\frontend` copy may still contain Prisma/PostgreSQL files,
but it is not the active project and should not be used to run this copy.

### Exact environment-file steps

1. In `backend`, copy `.env.example` to `.env` once. Put `GITHUB_TOKEN`,
   `GEMINI_API_KEY`, and the SQLite settings in **`backend/.env` only**.
2. In `frontend`, optionally copy `.env.example` to `.env.local` and keep only
   `NEXT_PUBLIC_ACR_API_URL=http://localhost:8000` there.
3. Do not create or edit `DATABASE_URL`, Prisma, Supabase, or PostgreSQL values.
   Do not put Gemini/GitHub secrets in any frontend file.
4. Start the backend once; it creates `backend/data/acr_agent.sqlite3`. That
   file is local, free, ignored by Git, and needs no migration command.

### Run the complete application locally (Windows PowerShell)

Use the active project at `F:\FINAL_YEAR_PROJECT\ACR_AGENT\FINAL_YEAR_PROJECT`.
Do not use the older `C:\Users\user\OneDrive\Desktop\CICD\ACR_AGENT` copy.

Run this one-time setup after cloning or when dependencies are missing:

```powershell
cd F:\FINAL_YEAR_PROJECT\ACR_AGENT\FINAL_YEAR_PROJECT
if (-not (Test-Path .\backend\.venv\Scripts\python.exe)) { py -3.12 -m venv .\backend\.venv }
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Open three terminals and leave all three running. If PowerShell says script
execution is disabled for `npm`, use `npm.cmd` as shown.

```powershell
# Terminal 1: start Docker Desktop, then build the isolated worker image
cd F:\FINAL_YEAR_PROJECT\ACR_AGENT\FINAL_YEAR_PROJECT\backend
docker version
docker build -t rift-worker:latest -f Dockerfile.worker .
```

```powershell
# Terminal 2: backend API and Socket.IO server
cd F:\FINAL_YEAR_PROJECT\ACR_AGENT\FINAL_YEAR_PROJECT\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 3: frontend
cd F:\FINAL_YEAR_PROJECT\ACR_AGENT\FINAL_YEAR_PROJECT\frontend
npm.cmd install
npm.cmd run dev
```

Check the backend before opening the UI:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Then open `http://localhost:3000/auth`, create an account or sign in, and open
the dashboard. The GitHub repository field is intentionally blank on every new
dashboard session; enter the HTTPS repository and select one language before
starting a run. Set `GEMINI_API_KEY` and `GITHUB_TOKEN` only in `backend/.env`.
Docker Desktop must be running before ACR_AGENT can build or test a repository.

For the multi-language demonstration repository, use this branch in the
`GITHUB BRANCH` field so the worker runs the consolidated fixtures:
`acr-agent/five-errors-all-languages`. Leaving the branch as `main` runs the
repository's default branch instead.

If `backend/.env` does not exist, copy `backend/.env.example` to `backend/.env`
and fill in only your own keys. AURA and the healing agent use
`GEMINI_API_KEY`; the configured text model is `gemini-3.5-flash-lite` for
healing, chat, and AURA, with `gemini-3.6-flash` as the fallback model.

### Important operating limits

- Email/password authentication is implemented locally with SQLite. Google OAuth is also supported when `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and the registered callback URL are added to `backend/.env`.
- The frontend uses system font fallbacks rather than downloading Google Fonts during the build, so `npm.cmd run build` does not depend on Google Fonts network access.
- The frontend uses system font fallbacks rather than downloading Google Fonts during the build, so `npm.cmd run build` does not depend on Google Fonts network access.
- The Docker worker includes toolchains for Python, JavaScript/TypeScript, Java, Kotlin, C/C++, C#, Go, Rust and PHP. Each language still needs an end-to-end run against a representative repository before claiming universal autonomous repair success.
- A successful repair requires a running Docker Desktop instance, a valid Gemini key, a GitHub token with repository write/PR permission, and a repository whose checks actually pass after the patch. ACR_AGENT reports unresolved instead of claiming success when verification fails.

### Public hosting

ACR_AGENT can be published as a public website, but the backend must run on a server that can run Docker because it executes untrusted repository checks inside worker containers. A practical layout is a Next.js frontend on Vercel and the FastAPI backend plus Docker worker on a Docker-enabled VPS. Set only `NEXT_PUBLIC_ACR_API_URL` in the frontend; keep `GEMINI_API_KEY`, `GITHUB_TOKEN`, OAuth secrets, and the SQLite database on the backend server. For HTTPS production hosting set `ACR_FRONTEND_ORIGIN` to the frontend URL, `GOOGLE_REDIRECT_URI` to the public backend callback, and `ACR_COOKIE_SECURE=true`. Add authentication, rate limits, repository limits, persistent SQLite storage, and resource/time limits before allowing unknown public users to run repositories.

Modern software projects can contain syntax errors, build failures, type issues, logical bugs, and other problems that require developers to manually investigate and repair.

ACR_AGENT automates this process.

Instead of manually:

1. Cloning a repository
2. Installing dependencies
3. Running checks
4. Finding the failing files
5. Understanding the error
6. Writing a fix
7. Testing the fix
8. Creating a branch
9. Committing changes
10. Creating a Pull Request

ACR_AGENT performs these steps through an automated agent pipeline.

### High-level flow

```text
GitHub Repository
       │
       ▼
Repository Preparation
       │
       ▼
Code Analysis
       │
       ▼
Error Detection
       │
       ▼
Gemini AI Analysis
       │
       ▼
Automatic Code Fix
       │
       ▼
Validation
       │
       ├── Failed ──► Retry Healing
       │
       ▼
Git Operations
       │
       ▼
Commit + Push
       │
       ▼
Pull Request
```

---

# ✨ Key Features

## 🔍 Automated Repository Analysis

ACR_AGENT accepts a GitHub repository URL and prepares the repository for analysis.

It can detect and analyze:

* Python
* JavaScript and TypeScript
* Java and Kotlin
* C and C++
* C#/.NET
* Go
* Rust
* PHP

The dashboard language selector is forwarded to the Docker worker as
`LANGUAGE_HINT`. For a multi-language repository, an explicit selection looks
for the matching subproject (even when the root `acr-project.json` documents a
different language). If the selected language is not present, the run stops
with a clear detection error instead of silently compiling another language.

---

## 🧠 AI-Powered Code Repair

Gemini AI analyzes:

* Error output
* Relevant source files
* Error location
* Error type
* Existing source code

It then generates structured fixes that can be applied automatically.

---

## 🔄 Iterative Healing

If the first fix does not resolve the detected problem, the system can repeat the:

```text
Analyze
   ↓
Generate Fix
   ↓
Apply Fix
   ↓
Validate
```

cycle until the issue is resolved or the configured retry limit is reached.

---

## 🐳 Isolated Docker Execution

Repository processing is performed inside a Docker worker environment.

This provides an isolated execution environment for:

* Repository cloning
* Dependency installation
* Build checks
* Syntax checks
* AI-based repair
* Git operations

---

## 📡 Real-Time Execution Logs

The frontend communicates with the backend using Socket.IO.

The dashboard can display:

* Current pipeline stage
* Execution logs
* Error messages
* Healing progress
* Completion status
* Final Pull Request information

---

## 🔀 Automated GitHub Pull Requests

After successful repair, ACR_AGENT can:

1. Create a working branch
2. Apply changes
3. Commit changes
4. Check repository ownership
5. Create a fork when required
6. Push the repaired code
7. Create a Pull Request

---

## 📊 Repair Results Dashboard

The frontend provides a dashboard containing:

* Pipeline status
* Repository information
* Execution progress
* Detected issues
* Applied fixes
* Branch information
* Pull Request link
* Execution statistics
* Fix distribution
* Downloadable JSON results

---

# 🏗️ How ACR_AGENT Works

ACR_AGENT follows a multi-stage autonomous pipeline.

```text
┌─────────────────────────┐
│      User Login         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Repository URL Input  │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Repository Preparation  │
│ Clone + Environment     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│     Code Analysis       │
│ Build / Syntax Checks   │
└────────────┬────────────┘
             │
             ▼
        Error Found?
          /      \
        No        Yes
        │          │
        ▼          ▼
      Done    Gemini AI
                  │
                  ▼
             Generate Fix
                  │
                  ▼
              Apply Fix
                  │
                  ▼
              Validate
               /    \
            Pass    Fail
             │       │
             │       └──────► Retry
             ▼
        Git Operations
             │
             ▼
        Commit + Push
             │
             ▼
       Create Pull Request
```

---

# 🏛️ System Architecture

```text
                    ┌──────────────────────┐
                    │      User / Browser  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Next.js Frontend   │
                    │                      │
                    │ Login                │
                    │ Dashboard            │
                    │ Logs                 │
                    │ Results              │
                    └──────────┬───────────┘
                               │
                     HTTP / Socket.IO
                               │
                               ▼
                    ┌──────────────────────┐
                    │   FastAPI Backend    │
                    │                      │
                    │ API                  │
                    │ Socket.IO            │
                    │ Pipeline Controller  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Docker Worker      │
                    │                      │
                    │ Repository Prep      │
                    │ Analysis             │
                    │ AI Healing           │
                    │ Git Operations       │
                    └───────┬───────┬──────┘
                            │       │
                ┌───────────┘       └───────────┐
                ▼                               ▼
        ┌───────────────┐               ┌───────────────┐
        │   Gemini AI   │               │    GitHub     │
        │               │               │               │
        │ Error         │               │ Repository    │
        │ Analysis      │               │ Fork          │
        │ Code Fix      │               │ Commit        │
        └───────────────┘               │ Pull Request  │
                                        └───────────────┘
```

---

# 📁 Project Structure

```text
ACR_AGENT/
│
├── backend/
│   ├── main.py
│   ├── worker_entrypoint.py
│   ├── repo_prep_agent.py
│   ├── analysis_agent.py
│   ├── healing_agent.py
│   ├── git_agent.py
│   ├── container_manager.py
│   ├── requirements.txt
│   ├── Dockerfile.worker
│   └── .env
│
├── frontend/
│   ├── app/
│   │   ├── api/
│   │   │   └── auth/
│   │   │       └── [...nextauth]/
│   │   │           └── route.ts
│   │   │
│   │   ├── login/
│   │   │   └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   └── theme-provider.tsx
│   │   │
│   │   ├── layout.tsx
│   │   ├── providers.tsx
│   │   ├── page.tsx
│   │   ├── test/
│   │   │   └── page.tsx
│   │   └── globals.css
│   │
│   ├── components/
│   │   └── ui/
│   │       └── sonner.tsx
│   │
│   ├── lib/
│   │   └── utils.ts
│   │
│   ├── auth.ts
│   ├── middleware.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── postcss.config.mjs
│   ├── components.json
│   └── .env.local
│
├── .gitignore
└── README.md
```

> The current implementation uses the SQLite email/password session described below. Google/GitHub OAuth is optional and is not required for local execution.

---

# 🧰 Technology Stack

## Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* shadcn/ui
* Socket.IO Client
* Recharts
* GSAP
* Lucide React
* Sonner
* next-themes
* Auth.js / NextAuth

The repository currently uses Next.js 16, React 19, Tailwind CSS 4, Socket.IO Client, Recharts, GSAP, and related frontend libraries.

## Backend

* Python
* FastAPI
* Uvicorn
* Python Socket.IO
* Pydantic
* GitPython
* PyGithub
* Docker SDK
* Requests
* aiohttp
* python-dotenv

## AI

* Google Gemini
* `google-genai`

## Infrastructure

* Docker
* Git
* GitHub API

---

# 🔄 Core Workflow

## Stage 1 — Repository Preparation

The repository preparation agent:

1. Receives the repository URL.
2. Clones the repository.
3. Detects the project environment.
4. Installs required dependencies.
5. Prepares the working branch.

The current implementation supports Python and JavaScript/TypeScript project detection.

---

# Stage 2 — Code Analysis

The analysis agent runs appropriate checks based on the detected project.

### Python

Possible checks include:

```bash
python -m compileall
```

### JavaScript / TypeScript

Possible checks include:

```bash
npm run build
```

or:

```bash
bun run build
```

Simple JavaScript files can also be syntax checked with Node.js.

The analysis stage returns the detected failure information and status.

---

# Stage 3 — AI Healing

When an error is detected, the healing agent:

1. Reads the error output.
2. Identifies relevant files.
3. Reads the source code.
4. Sends the required context to Gemini.
5. Receives structured fix information.
6. Validates the response.
7. Applies the generated changes.
8. Sends the repository back for validation.

The current implementation classifies fixes into categories such as:

* LINTING
* SYNTAX
* LOGIC
* TYPE

---

# Stage 4 — Git Operations

After successful repair:

```text
Create / checkout branch
        ↓
Stage changes
        ↓
Commit
        ↓
Check repository ownership
        ↓
Fork if necessary
        ↓
Push changes
        ↓
Create Pull Request
```

The Git agent uses GitHub APIs to manage repository and Pull Request operations.

---

# 🎨 Frontend

The main dashboard provides a user interface for starting and monitoring the repair process.

## Dashboard Capabilities

* Repository URL input
* Retry configuration
* Real-time execution logs
* Pipeline stage tracking
* Repair summary
* Applied-fix details
* Pull Request link
* Execution statistics
* Charts
* JSON result download

These capabilities are present in the current frontend implementation.

---

# 🔐 Authentication

ACR_AGENT uses a SQLite-backed email/password session for protected access to the application.

### Authentication Flow

```text
User
 │
 ▼
Login Page
 │
 ▼
Email and password
 │
 ▼
HTTP-only SQLite session
 │
 ▼
Authenticated Session
 │
 ▼
ACR_AGENT Dashboard
```

Authentication protects the main application while keeping the existing DevOps dashboard functionality intact.

### Authentication Components

```text
frontend/
├── auth.ts
├── middleware.ts
├── app/
│   ├── login/
│   │   └── page.tsx
│   ├── providers.tsx
│   └── api/
│       └── auth/
│           └── [...nextauth]/
│               └── route.ts
```

---

# 🔑 Environment Variables

## Backend

Create:

```text
backend/.env
```

Example:

```env
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_token
```

The original backend uses Gemini and GitHub credentials for AI repair and GitHub operations.

---

## Frontend

Create:

```text
frontend/.env.local
```

Example:

```env
NEXT_PUBLIC_ACR_API_URL=http://localhost:8000
```

### Security

Never expose:

```text
GEMINI_API_KEY
GITHUB_TOKEN
```

to the client-side application.

Never commit `.env` or `.env.local` files to GitHub.

---

# 🚀 Installation

## Prerequisites

Install:

* Git
* Node.js
* npm
* Python 3.12
* Docker
* A Gemini API key for AURA and healing
* A GitHub token

---

# 1. Clone the Repository

```bash
git clone https://github.com/SuhasKumarHR/ACR_AGENT.git
cd ACR_AGENT
```

---

# 2. Backend Setup

```bash
cd backend
```

Create a virtual environment:

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 3. Configure Backend Environment

Create:

```text
backend/.env
```

Add:

```env
GEMINI_API_KEY=your_gemini_api_key
ACR_AURA_MODEL=gemini-3.8-flash
ACR_AURA_FALLBACK_MODEL=gemini-3.7-flash
GITHUB_TOKEN=your_github_token
GOOGLE_CLIENT_ID=your_google_web_client_id
GOOGLE_CLIENT_SECRET=your_google_web_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
ACR_HEAL_MODEL=gemini-3.8-flash
ACR_HEAL_FALLBACK_MODEL=gemini-3.7-flash
ACR_CHAT_MODEL=gemini-3.8-flash
PIPELINE_TIME_LIMIT_SECONDS=270
MAX_RETRIES=5
ACR_AUTH_DB=./data/acr_agent.sqlite3
ACR_AUTH_COOKIE=acr_session
ACR_COOKIE_SECURE=false
ACR_FRONTEND_ORIGIN=http://localhost:3000
```

`GEMINI_API_KEY` and `GITHUB_TOKEN` are server-side secrets. Never
copy them into `frontend/.env.local` or any `NEXT_PUBLIC_` variable.
The SQLite path is a file path, not a PostgreSQL connection URL.
Google OAuth is optional; register the exact redirect URI above in Google Cloud
Console under the OAuth web client. The Google button redirects to
`/auth/google/start`, verifies the callback state, and then creates the same
SQLite session used by email/password login.

---

# 4. Build the Docker Worker

From the `backend` directory:

```bash
docker build -f Dockerfile.worker -t rift-worker:latest .
```

---

# 5. Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

---

# 6. Configure Frontend Environment

Create:

```text
frontend/.env.local
```

Add:

```env
NEXT_PUBLIC_ACR_API_URL=http://localhost:8000
```

Do not add `DATABASE_URL`, Prisma settings, or API secrets to the frontend.

---

# ▶️ Running the Application

## Terminal 1 — Backend

```bash
cd backend
```

Start the FastAPI / Socket.IO server:

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The backend will be available at:

```text
http://localhost:8000
```

---

## Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

---

# 🔐 Local Login Flow

When the application starts:

```text
http://localhost:3000
       │
       ▼
 SQLite session check
       │
       ├── Not authenticated
       │          │
       │          ▼
       │       /auth
       │          │
       │          ▼
       │   Email + password
       │          │
       │          ▼
       │    HTTP-only cookie
       │          │
       │          ▼
       └──────► Dashboard
```

---

# 🧪 Testing Mode

The `/test` route renders the same real dashboard as `/dashboard`; it is retained for compatibility with older links.

Run:

```bash
cd frontend
npm run dev
```

Then open:

```text
http://localhost:3000/test
```

Use `/auth` first, then start a real run from the dashboard.

---

# 📡 API

## Health Check

```http
GET /health
```

Used to verify that the backend is running.

---

## Run Pipeline

```http
POST /run
```

Example request:

```json
{
  "repo_url": "https://github.com/username/repository",
  "max_retries": 5
}
```

The backend uses this request to start repository analysis and repair.

---

# 📡 Real-Time Socket Events

The frontend uses Socket.IO for real-time communication.

## Start Agent

```text
start_agent
```

Starts the repository repair pipeline.

---

## Log

```text
log
```

Streams pipeline logs to the frontend.

---

## Completed

```text
completed
```

Returns the final pipeline result.

---

## Fatal Error

```text
error_fatal
```

Reports an unrecoverable pipeline error.

These events correspond to the current backend/frontend communication flow.

---

# 📊 Output

A successful pipeline produces structured information similar to:

```json
{
  "status": "SUCCESS",
  "total_time_minutes": 3.45,
  "fixes_applied": 5,
  "branch": "AI_FIX_BRANCH",
  "pr_link": "https://github.com/user/repository/pull/1",
  "iterations_used": 2,
  "total_failures": 5,
  "commits_count": 5,
  "fixes": [
    {
      "file_path": "src/utils.py",
      "bug_type": "SYNTAX",
      "line_number": 15,
      "explanation": "Syntax issue repaired",
      "commit_message": "Fix syntax issue",
      "status": "Fixed"
    }
  ]
}
```

The actual repository's output model includes pipeline status, timing, applied fixes, branch, Pull Request information, iterations, failures, commits, and detailed fix objects.

---

# 📋 Fix Information

Each detected fix can contain:

| Field            | Description                              |
| ---------------- | ---------------------------------------- |
| `file_path`      | File where the problem was detected      |
| `bug_type`       | Category of the problem                  |
| `line_number`    | Relevant line number                     |
| `explanation`    | Description of the issue/fix             |
| `commit_message` | Commit message generated for the repair  |
| `status`         | Whether the fix was successfully applied |

---

# 🐳 Docker Worker

The worker image provides an isolated environment for running the repair pipeline.

The worker is based on:

```text
python:3.12-slim
```

It includes tools required for:

* Git operations
* Python execution
* Node.js / npm checks
* AI repair
* Repository analysis

The container manager starts the worker, streams its logs, reads the final result, and cleans up the container after execution.

---

# 🔒 Security

ACR_AGENT processes source-code repositories and therefore must protect credentials and repository access.

### Recommended security practices

* Never commit API keys.
* Never commit GitHub tokens.
* Never expose OAuth client secrets to the browser.
* Keep `.env` and `.env.local` out of Git.
* Run untrusted repository code inside isolated containers.
* Validate AI-generated changes before applying them.
* Limit Docker resources where appropriate.
* Validate repository paths and URLs.
* Use minimum required GitHub token permissions.

---

# 🛠️ Troubleshooting

## Backend does not start

Check:

```bash
python --version
```

and:

```bash
pip install -r requirements.txt
```

Also verify that Docker is running.

---

## Frontend cannot connect to backend

Check:

Use `NEXT_PUBLIC_ACR_API_URL=http://localhost:8000` in `frontend/.env.local` if the frontend API is not on its default address.

Then verify:

```text
http://localhost:8000/health
```

---

## Login or signup fails

Make sure the backend is running and that `backend/data/acr_agent.sqlite3` is
writable. Then open `/auth`, create an account, and sign in with the same email
and password. No PostgreSQL service or `DATABASE_URL` is needed.

---

## Docker worker fails

Check:

```bash
docker images
```

Make sure the worker image exists:

```text
rift-worker:latest
```

If necessary, rebuild:

```bash
docker build -f Dockerfile.worker -t rift-worker:latest .
```

---

## Gemini AI fails

Check:

```env
GEMINI_API_KEY=your_key
```

Make sure the backend environment can access the key.

---

## GitHub Pull Request fails

Check:

```env
GITHUB_TOKEN=your_token
```

and verify that the token has the repository permissions required by your workflow.

---

# 🚀 Future Enhancements

Potential improvements for future versions include:

### Authentication & Users

* User profile management
* Repository history
* Per-user execution history
* Saved repositories
* User-specific configuration

### AI Improvements

* Support for additional AI models
* Better error classification
* Multi-file reasoning
* Test generation
* Regression detection
* AI-generated explanations

### DevOps Improvements

* CI/CD integration
* GitHub Actions integration
* Automated test execution
* Deployment verification
* Multiple repository support
* Scheduled repository scans

### Dashboard Improvements

* Execution history
* Repository health score
* Code-quality trends
* Repair analytics
* Detailed execution timeline
* Downloadable reports

---

# 📌 Project Goal

ACR_AGENT aims to reduce the manual effort required to identify and repair software issues.

The platform brings together:

```text
AI
+
DevOps
+
GitHub
+
Docker
+
Automated Code Analysis
+
Automated Code Repair
+
Pull Request Automation
```

into one autonomous development workflow.

---

# 👨‍💻 Development

For frontend development:

```bash
cd frontend
npm run dev
```

For backend development:

```bash
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

For a production frontend build:

```bash
cd frontend
npm run build
npm run start
```

---

# 📄 License

Add the project's chosen license here before publishing the project publicly.

---

## Project Summary

**ACR_AGENT** is an autonomous AI-powered code repair platform that:

> **Accepts a repository → analyzes the code → identifies problems → uses AI to generate fixes → validates the changes → commits the repair → pushes the changes → creates a Pull Request.**

The goal is to make software debugging and repair faster, more automated, and easier to monitor through a unified dashboard.

## Current verification notes

The worker detects and analyzes Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, PHP, and Kotlin. Each language uses its detected project build system where available and returns the actual compiler/test output to KNN, Gemini, the dashboard, and the run chatbot. C# source-only repositories are compiled in a disposable .NET SDK project; PHP Composer dependencies and C/C++ Makefiles are validated before source review.

Runs have a configurable five-minute budget (`PIPELINE_TIME_LIMIT_SECONDS=270`) and the dashboard reports the measured time taken beneath the pipeline status. The value is telemetry from the worker result; it does not claim success unless the verification stage passes.

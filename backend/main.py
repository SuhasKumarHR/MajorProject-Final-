import os
import asyncio
import secrets
from urllib.parse import urlencode
from http.cookies import SimpleCookie
from collections.abc import Awaitable, Callable
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
import socketio
from auth_store import (
    authenticate,
    create_session,
    create_user,
    delete_session,
    get_or_create_oauth_user,
    initialize as initialize_auth_store,
    user_for_session,
)
from container_manager import run_pipeline_in_container


AsyncLogCallback = Callable[[str, str, Optional[str]], Awaitable[None]]

# Load environment variables
# The repository .env is the single source of truth for local runs. This also
# prevents an old PowerShell GOOGLE_* variable from selecting the wrong OAuth
# client after switching between the duplicate project copies.
load_dotenv(override=True)
initialize_auth_store()

AUTH_COOKIE = os.getenv("ACR_AUTH_COOKIE", "acr_session")


def _frontend_origins() -> list[str]:
    configured = os.getenv("ACR_FRONTEND_ORIGIN", "").strip()
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if configured and configured not in origins:
        origins.append(configured)
    return origins


def _cookie_secure() -> bool:
    return os.getenv("ACR_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}


def _user_from_request(request: Request) -> dict | None:
    return user_for_session(request.cookies.get(AUTH_COOKIE))


def _user_from_cookie_header(header: str | None) -> dict | None:
    if not header:
        return None
    cookies = SimpleCookie()
    cookies.load(header)
    morsel = cookies.get(AUTH_COOKIE)
    return user_for_session(morsel.value if morsel else None)


def _require_user(request: Request) -> dict:
    user = _user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use ACR_AGENT.")
    return user


def _set_session_cookie(response: Response, token: str, remember: bool) -> None:
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        max_age=(60 * 60 * 24 * 30) if remember else (60 * 60 * 8),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _frontend_url(path: str = "/auth") -> str:
    return f"{os.getenv('ACR_FRONTEND_ORIGIN', 'http://localhost:3000').rstrip('/')}{path}"


def _google_redirect_uri() -> str:
    return os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    ).strip()


def _oauth_error(message: str) -> RedirectResponse:
    return RedirectResponse(
        f"{_frontend_url('/auth')}?{urlencode({'oauth_error': message[:180]})}",
        status_code=303,
    )

app = FastAPI(title="Rift Autonomous DevOps Agent", version="1.0.0")

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=_frontend_origins(),
    cookie=None,
    logger=True,
    engineio_logger=True
)

# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    repo_url: HttpUrl
    team_name: str
    leader_name: str
    language_hint: str = "auto"


class RunResponse(BaseModel):
    status: str
    total_time_minutes: float
    fixes_applied: int
    branch: str
    pr_link: str
    speed_bonus_eligible: bool
    fixes: list[dict]


class AssistantRequest(BaseModel):
    """AURA AI receives only an explicitly supplied general question."""

    prompt: str


class AuthRequest(BaseModel):
    name: str = ""
    email: str
    password: str
    remember: bool = True


@app.post("/auth/signup")
def signup(request: AuthRequest, response: Response):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    try:
        user = create_user(request.name, request.email, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session_cookie(response, create_session(user["id"], request.remember), request.remember)
    return {"user": user}


@app.post("/auth/login")
def login(request: AuthRequest, response: Response):
    user = authenticate(request.email, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    _set_session_cookie(response, create_session(user["id"], request.remember), request.remember)
    return {"user": user}


@app.get("/auth/me")
def current_user(request: Request):
    return {"user": _require_user(request)}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    delete_session(request.cookies.get(AUTH_COOKIE))
    response.delete_cookie(AUTH_COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/google/start")
def google_start():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id or not os.getenv("GOOGLE_CLIENT_SECRET", "").strip():
        return _oauth_error("Google OAuth is not configured in backend/.env.")
    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
    )
    redirect = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=303
    )
    redirect.set_cookie(
        "acr_oauth_state",
        state,
        max_age=600,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return redirect


@app.get("/auth/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return _oauth_error(f"Google authorization was cancelled: {error}.")
    expected_state = request.cookies.get("acr_oauth_state")
    if not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return _oauth_error("Google OAuth state validation failed. Please try again.")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return _oauth_error("Google OAuth is not configured in backend/.env.")

    try:
        import requests

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": _google_redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ValueError("Google did not return an access token.")
        profile_response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        if profile.get("email_verified") is not True:
            raise ValueError("Google returned an unverified email address.")
        user = get_or_create_oauth_user(profile.get("name", "Google operator"), profile.get("email", ""))
    except Exception as exc:
        return _oauth_error(f"Google sign-in failed: {exc}")

    redirect = RedirectResponse(_frontend_url("/dashboard"), status_code=303)
    _set_session_cookie(redirect, create_session(user["id"], True), True)
    redirect.delete_cookie("acr_oauth_state", path="/")
    return redirect


@app.post("/run", response_model=RunResponse)
def run_pipeline(request: RunRequest, http_request: Request):
    _require_user(http_request)
    # PRE-FLIGHT CHECKS
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("GITHUB_TOKEN"):
        raise HTTPException(
            status_code=500,
            detail="Missing API keys: GEMINI_API_KEY or GITHUB_TOKEN not set.",
        )

    repo_url = str(request.repo_url)
    team_name = request.team_name.strip()
    leader_name = request.leader_name.strip()

    try:
        result = run_pipeline_in_container(
            repo_url,
            team_name,
            leader_name,
            language_hint=request.language_hint,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("status") == "FAILED":
        error_msg = result.get("error", "Pipeline failed inside container")
        raise HTTPException(status_code=500, detail=error_msg)

    return RunResponse(
        status=result.get("status", "UNKNOWN"),
        total_time_minutes=result.get("total_time_minutes", 0),
        fixes_applied=result.get("fixes_applied", 0),
        branch=result.get("branch", "N/A"),
        pr_link=result.get("pr_link", "N/A"),
        speed_bonus_eligible=result.get("speed_bonus_eligible", False),
        fixes=result.get("fixes", []),
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/assistant")
def ask_aura(request: AssistantRequest, http_request: Request):
    """Answer a general question without sending pipeline logs or secrets to an AI provider."""
    _require_user(http_request)
    prompt = request.prompt.strip()
    if not prompt or len(prompt) > 4_000:
        raise HTTPException(status_code=400, detail="Prompt must contain 1 to 4000 characters.")

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="AURA AI requires GEMINI_API_KEY in backend/.env.",
        )
    try:
        from google import genai

        model = os.getenv(
            "ACR_AURA_MODEL",
            "gemini-3.5-flash-lite",
        ).strip()
        fallback_model = os.getenv(
            "ACR_AURA_FALLBACK_MODEL", "gemini-3.8-flash"
        ).strip()
        models = [model]
        if fallback_model and fallback_model not in models:
            models.append(fallback_model)
        from google.genai import types

        # AURA is interactive: keep each provider attempt bounded and let our
        # explicit fallback handle temporary 429/503 capacity responses.
        client = genai.Client(
            api_key=gemini_api_key,
            http_options=types.HttpOptions(
                timeout=25_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        contents = (
            "You are AURA AI, a helpful general assistant inside ACR_AGENT. "
            "Answer programming, DevOps, and general questions clearly. "
            "Do not claim to have run code, viewed a repository, or know a live pipeline. "
            "For live ACR_AGENT run details, direct the user to the separate Pipeline Assistant.\n\n"
            f"User question: {prompt}"
        )
        last_error = None
        for model_index, model_name in enumerate(models):
            attempts = 1
            for attempt in range(attempts):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config={"temperature": 0.3},
                    )
                    answer = str(getattr(response, "text", "") or "").strip()
                    if not answer:
                        raise RuntimeError("Gemini returned an empty response.")
                    return {"answer": answer, "provider": "gemini", "model": model_name}
                except Exception as exc:
                    last_error = exc
                    message = str(exc).upper()
                    transient = any(
                        marker in message
                        for marker in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
                    )
                    if not transient:
                        raise
                    # A capacity error on the primary model is retried on the
                    # fallback model before reporting failure to AURA.
                    break
        raise RuntimeError(f"Gemini models are temporarily unavailable: {last_error}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Gemini AURA request failed: {exc}",
        ) from exc


# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit('log', {
        'message': '🔌 Connected to RIFT Agent backend',
        'type': 'info'
    }, room=sid)


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


@sio.event
async def start_agent(sid, data):
    """Handle agent start request via WebSocket"""
    print(f"[Socket] Received start_agent from {sid}: {data}")

    environ = sio.get_environ(sid) or {}
    if _user_from_cookie_header(environ.get("HTTP_COOKIE")) is None:
        await sio.emit('error_fatal', {
            'message': 'Your session has expired. Sign in again before starting a run.'
        }, room=sid)
        return
    
    repo_url = data.get('repo_url')
    team_name = data.get('team_name')
    leader_name = data.get('leader_name')
    retry_limit = data.get('retry_limit', 5)  # Default to 5 if not provided
    language_hint = str(data.get('language_hint', 'auto') or 'auto').strip().lower()
    
    if not repo_url or not team_name or not leader_name:
        await sio.emit('error_fatal', {
            'message': 'Missing required fields'
        }, room=sid)
        return
    
    # Pre-flight checks
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("GITHUB_TOKEN"):
        await sio.emit('error_fatal', {
            'message': 'Missing API keys: GEMINI_API_KEY or GITHUB_TOKEN not set.'
        }, room=sid)
        return
    
    # Create a callback function to emit logs
    async def log_callback(
        message: str,
        log_type: str = "info",
        stage: Optional[str] = None,
    ) -> None:
        payload = {'message': message, 'type': log_type}
        if stage:
            payload['stage'] = stage
        await sio.emit('log', payload, room=sid)
    
    # Run pipeline in background
    asyncio.create_task(
        run_agent_pipeline(
            sid,
            repo_url,
            team_name,
            leader_name,
            retry_limit,
            language_hint,
            log_callback,
        )
    )


async def run_agent_pipeline(
    sid: str,
    repo_url: str,
    team_name: str,
    leader_name: str,
    retry_limit: int,
    language_hint: str,
    log_callback: AsyncLogCallback,
) -> None:
    """Run the pipeline and emit results"""
    try:
        await log_callback("🚀 Initializing Autonomous DevOps Agent...", "info", "Initializing")
        
        # Create a synchronous wrapper for the callback that can be called from thread
        loop = asyncio.get_event_loop()
        
        def sync_log_callback(
            message: str,
            log_type: str = "info",
            stage: Optional[str] = None,
        ) -> None:
            """Thread-safe synchronous wrapper for async log callback"""
            payload = {'message': message, 'type': log_type}
            if stage:
                payload['stage'] = stage
            # Schedule the emit on the main event loop from the worker thread
            asyncio.run_coroutine_threadsafe(
                sio.emit('log', payload, room=sid),
                loop
            )
        
        # Run the pipeline in a thread pool to avoid blocking
        result = await loop.run_in_executor(
            None, 
            run_pipeline_in_container, 
            repo_url, 
            team_name, 
            leader_name,
            retry_limit,
            language_hint,
            sync_log_callback
        )
        
        # Always send the complete result, including failed runs. The UI and
        # chatbot need the authoritative compiler/test output, failure history,
        # diagnosis, rollback events, and verification data—not just a status.
        completion = {
            **result,
            'run': result,
            'status': result.get('status', 'UNKNOWN'),
            'total_time': result.get('total_time_minutes', 0),
            'pr_link': result.get('pr_link', 'N/A'),
            'branch': result.get('branch', 'N/A'),
            'fixes': result.get('fixes', []),
            'iterations_used': result.get('iterations_used', 1),
            'total_failures': result.get('total_failures', 0),
            'commits_count': result.get('commits_count', 0),
            'error': result.get('error'),
        }
        await sio.emit('completed', completion, room=sid)
        
    except Exception as e:
        await sio.emit('error_fatal', {
            'message': f'Pipeline error: {str(e)}'
        }, room=sid)


# Export the socket_app for uvicorn
# Run with: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
app = socket_app

import json
import os
import sys
import threading
import time
import docker
from typing import Callable, Optional
from docker.errors import ImageNotFound

WORKER_IMAGE = "rift-worker:latest"


def run_pipeline_in_container(
    repo_url: str, 
    team_name: str, 
    leader_name: str,
    retry_limit: int = 5,
    language_hint: str = "auto",
    log_callback: Optional[Callable[[str, str, Optional[str]], None]] = None
) -> dict:
    """
    Spin up a worker container, run the pipeline, collect the result, and
    destroy the container.
    
    Args:
        repo_url: Git repository URL
        team_name: Team name
        leader_name: Leader name
        retry_limit: Maximum number of healing iterations (default: 5)
        language_hint: Explicit language ID from the dashboard, or ``auto``
        log_callback: Optional synchronous function to emit logs via WebSocket
        
    Returns:
        dict with pipeline result (status, fixes, pr_link, etc.)
    """
    client = docker.from_env()
    container = None
    started_at = time.monotonic()
    timed_out = False
    timeout_timer = None
    
    def emit_log(
        message: str,
        log_type: str = "info",
        stage: Optional[str] = None,
    ) -> None:
        """Helper to emit logs both to console and websocket"""
        print(message, flush=True)
        if log_callback:
            try:
                log_callback(message, log_type, stage)
            except Exception as e:
                # Fail silently if socket emit fails
                print(f"[Warning] Failed to emit log via socket: {e}", flush=True)

    env_vars = {
        "REPO_URL": repo_url,
        "TEAM_NAME": team_name,
        "LEADER_NAME": leader_name,
        "LANGUAGE_HINT": str(language_hint or "auto").strip().lower(),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "ACR_HEAL_MODEL": os.getenv("ACR_HEAL_MODEL", "gemini-3.8-flash"),
        "ACR_CHAT_MODEL": os.getenv("ACR_CHAT_MODEL", "gemini-3.8-flash"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "MAX_RETRIES": str(retry_limit),
        "PIPELINE_TIME_LIMIT_SECONDS": os.getenv("PIPELINE_TIME_LIMIT_SECONDS", "270"),
    }

    try:
        emit_log(f"📦 Creating container from image '{WORKER_IMAGE}'...", "info", "Stage 1: Prep")
        container = client.containers.run(
            image=WORKER_IMAGE,
            environment=env_vars,
            detach=True,
            mem_limit="1g",
        )

        try:
            configured_limit = int(os.getenv("PIPELINE_TIME_LIMIT_SECONDS", "270"))
        except (TypeError, ValueError):
            configured_limit = 270
        time_limit = max(60, min(configured_limit, 300))

        def stop_overdue_container() -> None:
            nonlocal timed_out
            timed_out = True
            emit_log(
                f"Pipeline time limit reached ({time_limit} seconds); stopping worker.",
                "error",
                "TIMEOUT",
            )
            try:
                if container is not None:
                    container.stop(timeout=5)
            except Exception as stop_error:
                emit_log(f"Unable to stop overdue worker: {stop_error}", "error")

        timeout_timer = threading.Timer(time_limit, stop_overdue_container)
        timeout_timer.daemon = True
        timeout_timer.start()

        emit_log(f"✅ Container started: {container.short_id}", "success", "Stage 2: Analysis")
        emit_log("📡 Streaming container logs...", "info")

        # Stream logs directly — this blocks until container exits
        for line in container.logs(stream=True, follow=True, stdout=True, stderr=True):
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                emit_log(decoded, "info")

        emit_log("✨ Container execution completed", "success")

        # Container has exited by now
        exit_result = container.wait(timeout=30)
        exit_code = exit_result.get("StatusCode", -1)
        emit_log(f"Container exited with code: {exit_code}", "info" if exit_code == 0 else "warning")

        # Get stdout-only for JSON parsing
        stdout_logs = container.logs(stdout=True, stderr=False).decode("utf-8").strip()

        if timed_out:
            elapsed = time.monotonic() - started_at
            return {
                "status": "FAILED",
                "error": f"Pipeline exceeded the {time_limit}-second time limit.",
                "total_time_seconds": round(elapsed, 1),
                "total_time_minutes": round(elapsed / 60, 2),
                "fixes": [],
                "iterations_used": 0,
                "total_failures": 0,
                "pr_link": "N/A",
            }

        if not stdout_logs:
            raise RuntimeError(f"Worker container produced no output (exit code: {exit_code})")

        last_line = stdout_logs.strip().split("\n")[-1]

        try:
            result = json.loads(last_line)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse worker output as JSON: {e}\n"
                f"Raw output (last 500 chars): {stdout_logs[-500:]}"
            )

        if exit_code != 0 and result.get("status") != "FAILED":
            result["status"] = "FAILED"
            result.setdefault("error", f"Container exited with code {exit_code}")

        status = result.get('status')
        emit_log(
            f"🎉 Pipeline finished with status: {status}", 
            "success" if status == "SUCCESS" else "error",
            "Stage 4: Git Ops" if status == "SUCCESS" else "Failed"
        )
        return result

    except ImageNotFound:
        raise RuntimeError(
            f"Worker image '{WORKER_IMAGE}' not found. "
            f"Build it with: docker build -f Dockerfile.worker -t {WORKER_IMAGE} ."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"Container execution failed: {e}")

    finally:
        if timeout_timer is not None:
            timeout_timer.cancel()
        if container is not None:
            try:
                emit_log(f"🧹 Removing container {container.short_id}...", "info")
                container.remove(force=True)
                emit_log("✅ Container removed successfully", "success")
            except Exception as cleanup_err:
                emit_log(f"⚠️ WARNING: Failed to remove container: {cleanup_err}", "warning")

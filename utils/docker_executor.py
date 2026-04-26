import subprocess
import platform
import os
import sys
from pathlib import Path
from utils.logging_config import get_logger

logger = get_logger("docker_executor")

IMAGE_NAME = "antigravity-sandbox"
DOCKERFILE_PATH = Path("work/Dockerfile.sandbox")

def get_docker_user_args():
    """Generate Docker user arguments based on OS (empty for Windows)."""
    if platform.system() == "Windows":
        return []
    try:
        # On Linux/macOS/WSL2, run as host UID:GID to avoid permission issues with mounts
        return ["--user", f"{os.getuid()}:{os.getgid()}"]
    except AttributeError:
        return []

def ensure_sandbox_image():
    """Ensure the antigravity-sandbox image exists, building it if necessary."""
    try:
        # Check if image exists
        res = subprocess.run(["docker", "images", "-q", IMAGE_NAME], capture_output=True, text=True)
        if res.stdout.strip():
            return True
            
        logger.info(f"Image {IMAGE_NAME} not found. Building from {DOCKERFILE_PATH}...")
        
        # Ensure Dockerfile exists
        if not DOCKERFILE_PATH.exists():
            DOCKERFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            # We copy requirements.txt from the root to /tmp/requirements.txt inside the container
            dockerfile_content = """FROM python:3.12-slim
WORKDIR /mnt/artifacts
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python"]
"""
            DOCKERFILE_PATH.write_text(dockerfile_content, encoding="utf-8")
        
        # Build execution (context is project root)
        build_res = subprocess.run([
            "docker", "build", "-t", IMAGE_NAME, "-f", str(DOCKERFILE_PATH), "."
        ], capture_output=True, text=True)
        
        if build_res.returncode == 0:
            logger.info(f"Successfully built {IMAGE_NAME}")
            return True
        else:
            logger.error(f"Failed to build {IMAGE_NAME}: {build_res.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error checking/building Docker image: {e}")
        return False

def run_in_docker(code: str, timeout: int = 60, job_id: str = "unknown") -> dict:
    """Safely execute Python code within a disposable Docker container."""
    if not ensure_sandbox_image():
        return {"success": False, "stderr": "Docker image not ready", "exit_code": 1, "tier": 2}

    # Absolute path for host artifacts directory
    host_artifacts = Path("work/artifacts").resolve()
    host_artifacts.mkdir(parents=True, exist_ok=True)
    
    # Build docker run command
    docker_cmd = [
        "docker", "run", "--rm",
        *get_docker_user_args(),
        "-v", f"{host_artifacts}:/mnt/artifacts",
        "-w", "/mnt/artifacts",
        IMAGE_NAME,
        "python", "-c", code
    ]
    
    logger.info(f"Executing code in Docker for job {job_id}", extra={"job_id": job_id})
    
    try:
        res = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8"
        )
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode,
            "tier": 2 # Docker Tier
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Docker execution timed out", extra={"job_id": job_id})
        return {"success": False, "stderr": "Timeout", "exit_code": 124, "tier": 2}
    except Exception as e:
        logger.error(f"Docker execution failed: {e}", extra={"job_id": job_id})
        return {"success": False, "stderr": str(e), "exit_code": 1, "tier": 2}

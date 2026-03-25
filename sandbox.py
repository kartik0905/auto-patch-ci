import docker
import tempfile
import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

# Lazy Docker client — only connects when actually needed
_docker_client = None

def _get_docker_client():
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _run_local_fallback(workspace_dir: str, file_relative_path: str, patch_code: str, test_cmd: str = "pytest") -> dict:
    """
    Fallback: applies the patch locally in a temp copy and runs tests via subprocess.
    Used when Docker is unavailable.
    """
    # Create a temporary copy of the workspace
    tmp_dir = tempfile.mkdtemp(prefix="cicd_sandbox_")
    try:
        # Copy workspace to temp dir
        tmp_workspace = os.path.join(tmp_dir, "workspace")
        shutil.copytree(workspace_dir, tmp_workspace, ignore=shutil.ignore_patterns(
            'venv', '.venv', '__pycache__', '.git', '.pytest_cache', 'node_modules'
        ))

        # Overlay the patched file
        patched_file = os.path.join(tmp_workspace, file_relative_path)
        os.makedirs(os.path.dirname(patched_file), exist_ok=True)
        with open(patched_file, 'w') as f:
            f.write(patch_code)

        # Run tests in the temp workspace
        result = subprocess.run(
            test_cmd.split(),
            capture_output=True,
            text=True,
            cwd=tmp_workspace,
            timeout=60
        )
        logs = result.stdout + result.stderr

        if result.returncode == 0:
            return {"status": "pass", "logs": logs}
        else:
            return {"status": "fail", "logs": logs}
    except Exception as e:
        return {"status": "fail", "logs": f"Local sandbox error: {e}"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_in_sandbox(workspace_dir: str, file_relative_path: str, patch_code: str, test_cmd: str = "pytest") -> dict:
    """
    Creates an isolated, ephemeral Python container.
    Mounts the user's workspace, but explicitly overlays the patched code
    using a temporary file mount. Runs the test command and captures logs.

    Falls back to a local subprocess sandbox if Docker is unavailable.
    """
    # Try Docker first, fall back to local subprocess
    try:
        client = _get_docker_client()
    except docker.errors.DockerException as e:
        logger.warning(f"Docker unavailable ({e}). Using local subprocess fallback.")
        return _run_local_fallback(workspace_dir, file_relative_path, patch_code, test_cmd)

    # Save the generated code patch to a secure temporary file on host
    fd, temp_path = tempfile.mkstemp(suffix=".py", text=True)
    with os.fdopen(fd, 'w') as f:
        f.write(patch_code)
    
    target_original_file = f"/app/{file_relative_path}"
    
    # Mount workspace as read-write (for pytest cache) and patch file as read-only overlay
    volumes = {
        workspace_dir: {'bind': '/app', 'mode': 'rw'},
        temp_path: {'bind': target_original_file, 'mode': 'ro'}
    }
    
    try:
        # Spin up slim container, sync requirements, and run tests
        # This keeps the container incredibly isolated
        container = client.containers.run(
            "python:3.11-slim",
            command=f"sh -c 'pip install -r requirements.txt -q && pip install pytest -q && {test_cmd}'",
            volumes=volumes,
            working_dir="/app",
            detach=True
        )
        
        # Wait for test to finish
        result = container.wait()
        exit_code = result.get('StatusCode', 1)
        
        # Capture stdout/stderr logs
        logs = container.logs().decode('utf-8')
        
    finally:
        # Immediately destroy ephemeral sandbox and the temp file to prevent leaks
        try:
            container.remove(force=True)
        except Exception:
            pass
        os.remove(temp_path)
    
    if exit_code == 0:
        return {"status": "pass", "logs": logs}
    else:
        return {"status": "fail", "logs": logs}

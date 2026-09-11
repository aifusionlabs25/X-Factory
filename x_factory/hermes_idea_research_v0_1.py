"""Process-isolated Hermes web-only R&D. No Desktop/profile installation required."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = Path(os.environ.get('LOCALAPPDATA', '')) / 'hermes'
HERMES_CODE = HERMES_ROOT / 'hermes-agent'
RUNNER = ROOT / 'scripts' / 'hermes_idea_research_worker.py'

class ResearchOutputError(RuntimeError):
    pass


def _launch(work_dir, prompt, limits, *, preflight=False, cancel_event=None, specialist=None):
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    executable = HERMES_CODE / 'venv/Scripts/python.exe'
    if not executable.is_file():
        raise RuntimeError('Hermes Python runtime is unavailable. Open Hermes Desktop and check its installation.')
    request_path = work_dir / ('preflight-request.json' if preflight else 'worker-request.json')
    output_path = work_dir / ('preflight-result.json' if preflight else 'worker-result.json')
    with request_path.open('x', encoding='utf-8') as handle:
        json.dump({'prompt': prompt, 'limits': limits, 'preflight': preflight, 'specialist': specialist}, handle)
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1', HERMES_HOME=str(work_dir / 'runtime'), HERMES_RESEARCH_SOURCE_ROOT=str(HERMES_ROOT))
    # Keep native tool tracing and imports inside the job; no user profile is changed.
    env['PYTHONPATH'] = os.pathsep.join([str(HERMES_CODE), str(ROOT)])
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    process = subprocess.Popen([str(executable), '-B', str(RUNNER), str(request_path), str(output_path)],
                               # Windows CreateProcess rejects a current directory
                               # longer than MAX_PATH, even though Python supports
                               # long artifact paths. The audit guard still binds
                               # every runtime write to work_dir, not this cwd.
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=flags)
    deadline = time.monotonic() + min(int(limits.get('timeout_seconds', 180)), 180)
    try:
        while process.poll() is None:
            if (cancel_event and cancel_event.is_set()) or time.monotonic() > deadline:
                process.kill()
                process.wait(timeout=10)
                raise RuntimeError('Research was cancelled or reached its time limit. No automatic retry was made.')
            time.sleep(.2)
        if not output_path.is_file():
            raise RuntimeError('Hermes research did not return a readable result. Check Hermes runtime compatibility.')
        response = json.loads(output_path.read_text(encoding='utf-8'))
        if response.get('error'):
            if response.get('error_code')=='RESEARCH_OUTPUT_INVALID':
                raise ResearchOutputError('Research ran, but its citations or output did not pass Factory validation. Your input is saved; no facts were approved.')
            raise RuntimeError(response['error'])
        if process.returncode != 0:
            raise RuntimeError('Hermes research stopped before completion.')
        return response
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def run_research(prompt: str, *, work_dir: Path, limits: dict, cancel_event) -> dict:
    return _launch(work_dir, prompt, limits, cancel_event=cancel_event)


def preflight(work_dir: Path) -> dict:
    return _launch(work_dir, '', {'timeout_seconds': 45}, preflight=True)


def run_specialist(actor, prompt, *, work_dir, cancel_event=None):
    if actor not in {'aria', 'omnara', 'troy'}:
        raise ValueError('Unknown preparation specialist')
    policy = ROOT / 'profiles' / actor / 'DRAFT_MODE.v0.1.md'
    return _launch(work_dir, prompt, {'timeout_seconds': 180, 'max_model_calls': 1,
                   'max_tool_calls': 0, 'max_sources': 0}, cancel_event=cancel_event,
                   specialist={'actor': actor, 'system_prompt': policy.read_text(encoding='utf-8')})

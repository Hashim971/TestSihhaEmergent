"""Executes an agent, times it, and writes exactly one append-only agent_runs document."""
import asyncio
import time
import uuid

AGENT_TIMEOUT_SECONDS = 60


class AgentRunFailed(Exception):
    def __init__(self, status: str, message: str, agent_run_id: str):
        super().__init__(message)
        self.status = status
        self.message = message
        self.agent_run_id = agent_run_id


async def _attempt(agent, db, **kwargs):
    try:
        return await agent.run(db, **kwargs)
    except Exception:
        await asyncio.sleep(0.5)
        return await agent.run(db, **kwargs)


async def run_agent(db, agent, *, patient_user_id, encounter_id, invoked_by, **kwargs):
    """Returns (content, agent_run_id). Raises AgentRunFailed on timeout or error."""
    import server

    started = time.perf_counter()
    content, input_refs, status, error_message = None, {}, "success", None
    try:
        content, input_refs = await asyncio.wait_for(
            _attempt(agent, db, patient_user_id=patient_user_id, encounter_id=encounter_id, **kwargs),
            timeout=AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        status = "timeout"
        error_message = f"Agent exceeded {AGENT_TIMEOUT_SECONDS}s"
    except Exception as exc:
        status = "error"
        error_message = f"{type(exc).__name__}: {exc}"[:500]

    run = {
        "agent_run_id": f"run_{uuid.uuid4().hex[:12]}",
        "agent_type": agent.agent_type,
        "encounter_id": encounter_id,
        "patient_user_id": patient_user_id,
        "invoked_by_user_id": invoked_by,
        "model": agent.model,
        "prompt_version": agent.prompt_version,
        "input_refs": input_refs or {},
        "output_ref": None,
        "status": status,
        "error_message": error_message,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "human_action": "none",
        "human_action_at": None,
        "created_at": server.iso(),
    }
    await db.agent_runs.insert_one(dict(run))

    if status != "success":
        raise AgentRunFailed(status, error_message, run["agent_run_id"])
    return content, run["agent_run_id"]

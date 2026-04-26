from __future__ import annotations


class AgentGateError(Exception):
    pass


class ManifestNotFoundError(AgentGateError):
    def __init__(self, url: str):
        super().__init__(f"No agent manifest found at {url}")


class IntentError(AgentGateError):
    pass


class FlowNotFoundError(AgentGateError):
    def __init__(self, name: str):
        super().__init__(f"Flow '{name}' not found in manifest")


class StepTransitionError(AgentGateError):
    def __init__(self, attempted: str, current: str, allowed: list[str]):
        self.attempted = attempted
        self.current = current
        self.allowed = allowed
        super().__init__(
            f"Step '{attempted}' cannot follow '{current}'. Allowed next: {allowed}"
        )


class SessionNotFoundError(AgentGateError):
    def __init__(self, session_id: str):
        super().__init__(f"Session '{session_id}' not found or expired")


class AuthError(AgentGateError):
    pass

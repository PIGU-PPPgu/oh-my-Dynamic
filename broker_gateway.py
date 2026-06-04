"""
Local A2A-style HTTP gateway for AgentBroker.

The gateway exposes the broker contract over a small stdlib HTTP server so
external tools, future MCP/A2A adapters, and Codex App orchestration glue can
inspect and drive the same messages, artifacts, handoffs, review requests, and
audit trace used by local isolated workers.
"""

from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse
import ipaddress
import json
import os
import uuid

from agent_broker import AgentBroker, validate_agent_id
from protocol_adapters import a2a_agent_card


DEFAULT_MAX_BODY_BYTES = 1_048_576


def _new_thread_id() -> str:
    return f"task-{uuid.uuid4().hex[:12]}"


def _is_loopback_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    if normalized in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


class BrokerGateway:
    """Thin service layer around AgentBroker for HTTP handlers and tests."""

    def __init__(
        self,
        broker: AgentBroker,
        base_url: str = "http://localhost:8765",
        auth_token: Optional[str] = None,
        agent_tokens: Optional[Dict[str, str]] = None,
    ) -> None:
        self.broker = broker
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.agent_tokens = dict(agent_tokens or {})

    def agent_card(self) -> Dict[str, Any]:
        card = a2a_agent_card(self.base_url)
        card["capabilities"] = {
            **card.get("capabilities", {}),
            "streaming": True,
            "streamingMode": "cursor_snapshot",
            "stateTransitionHistory": True,
            "artifacts": True,
            "agentBroker": True,
            "capabilityDiscovery": True,
            "supportedEventKinds": list(self.broker.policy.allowed_event_kinds),
            "artifactContentTypes": list(self.broker.policy.allowed_content_types),
            "auth": {
                "gatewayToken": bool(self.auth_token),
                "agentActorToken": bool(self.auth_token),
            },
            "registeredAgents": [agent.id for agent in self.broker.list_agents()],
        }
        card["skills"].append(
            {
                "id": "agent-broker",
                "name": "Agent Broker",
                "description": "Coordinate agents through messages, artifacts, handoffs, review requests, and audit traces.",
                "tags": ["a2a", "agent-broker", "artifacts", "audit-trace"],
                "examples": [
                    "POST /agents to register an agent.",
                    "POST /tasks to create a broker thread.",
                    "POST /tasks/{id}/handoffs to hand work from one agent to another.",
                ],
            }
        )
        return card

    def register_agent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.broker.register_agent(
            str(payload.get("id", payload.get("agent_id", ""))),
            str(payload.get("role", "agent")),
            capabilities=list(payload.get("capabilities", [])),
            metadata=dict(payload.get("metadata", {})),
        )
        data = asdict(agent)
        if self.auth_token and agent.id not in self.broker.policy.system_agents:
            token = str(payload.get("agent_token", payload.get("token", ""))).strip()
            if not token:
                token = self.agent_tokens.get(agent.id) or f"agt_{uuid.uuid4().hex}"
            self.agent_tokens[agent.id] = token
            data["agent_token"] = token
        return data

    def list_agents(self) -> Dict[str, Any]:
        return {"agents": [asdict(agent) for agent in self.broker.list_agents()]}

    def read_inbox(self, agent_id: str, mark_delivered: bool = True) -> Dict[str, Any]:
        return {
            "agentId": agent_id,
            "events": [
                asdict(event)
                for event in self.broker.read_inbox(agent_id, mark_delivered=mark_delivered)
            ],
        }

    def create_task(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not message.strip():
            raise ValueError("message is required")
        thread_id = _new_thread_id()
        self.broker.register_agent("user", "user", ["submit"])
        self.broker.register_agent("orchestrator", "orchestrator", ["coordinate", "reduce"])
        self.broker.send_message(
            "user",
            "orchestrator",
            "task_submitted",
            message,
            thread_id=thread_id,
            metadata=metadata or {},
        )
        self.broker.trace(
            "orchestrator",
            "workflow_started",
            message,
            thread_id=thread_id,
            metadata=metadata or {},
        )
        return self.broker.to_a2a_task(thread_id)

    def get_task(self, thread_id: str) -> Dict[str, Any]:
        return self.broker.to_a2a_task(thread_id)

    def list_events(self, thread_id: str, after: str = "") -> Dict[str, Any]:
        events = [asdict(event) for event in self.broker.list_events(thread_id=thread_id)]
        if after:
            ids = [event["id"] for event in events]
            if after in ids:
                events = events[ids.index(after) + 1:]
        return {
            "taskId": thread_id,
            "after": after,
            "events": events,
        }

    def send_message(self, thread_id: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
        event = self.broker.send_message(
            actor or str(payload.get("from", payload.get("from_agent", "orchestrator"))),
            payload.get("to", payload.get("to_agent")),
            str(payload.get("subject", "message")),
            str(payload.get("body", payload.get("message", ""))),
            thread_id=thread_id,
            task_id=str(payload.get("task_id", "")),
            artifact_ids=list(payload.get("artifact_ids", [])),
            metadata=dict(payload.get("metadata", {})),
        )
        return asdict(event)

    def publish_artifact(self, thread_id: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
        artifact = self.broker.publish_artifact(
            actor or str(payload.get("producer", payload.get("from", "orchestrator"))),
            str(payload.get("name", "artifact")),
            str(payload.get("content", "")),
            kind=str(payload.get("kind", "text")),
            content_type=str(payload.get("content_type", "text/plain")),
            metadata={**dict(payload.get("metadata", {})), "thread_id": thread_id},
            thread_id=thread_id,
        )
        return asdict(artifact)

    def create_handoff(self, thread_id: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
        event = self.broker.create_handoff(
            actor or str(payload.get("from", payload.get("from_agent", "orchestrator"))),
            str(payload.get("to", payload.get("to_agent", ""))),
            str(payload.get("task_id", thread_id)),
            str(payload.get("subject", "handoff")),
            str(payload.get("body", "")),
            artifact_ids=list(payload.get("artifact_ids", [])),
            thread_id=thread_id,
            metadata=dict(payload.get("metadata", {})),
        )
        return asdict(event)

    def request_review(self, thread_id: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
        event = self.broker.request_review(
            actor or str(payload.get("from", payload.get("from_agent", "orchestrator"))),
            str(payload.get("reviewer", payload.get("to", payload.get("to_agent", "reviewer")))),
            str(payload.get("task_id", thread_id)),
            str(payload.get("subject", "review_request")),
            str(payload.get("body", "")),
            artifact_ids=list(payload.get("artifact_ids", [])),
            thread_id=thread_id,
            metadata=dict(payload.get("metadata", {})),
        )
        return asdict(event)

    def respond_review(self, thread_id: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
        event = self.broker.respond_review(
            actor or str(payload.get("from", payload.get("from_agent", payload.get("reviewer", "reviewer")))),
            str(payload.get("to", payload.get("to_agent", "orchestrator"))),
            str(payload.get("task_id", thread_id)),
            str(payload.get("subject", "review_response")),
            str(payload.get("body", "")),
            str(payload.get("verdict", "commented")),
            artifact_ids=list(payload.get("artifact_ids", [])),
            thread_id=thread_id,
            parent_id=str(payload.get("parent_id", "")),
            metadata=dict(payload.get("metadata", {})),
        )
        return asdict(event)

    def complete_task(
        self,
        thread_id: str,
        payload: Optional[Dict[str, Any]] = None,
        actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        from_agent = actor or str(payload.get("from", "orchestrator"))
        artifact_ids = list(payload.get("artifact_ids", []))
        if "final_answer" in payload:
            artifact = self.broker.publish_artifact(
                from_agent,
                "final_answer",
                str(payload.get("final_answer", "")),
                kind="final_answer",
                metadata={"thread_id": thread_id},
                thread_id=thread_id,
            )
            artifact_ids.append(artifact.id)
        self.broker.trace(
            from_agent,
            "workflow_completed",
            str(payload.get("body", "Workflow completed.")),
            thread_id=thread_id,
            artifact_ids=artifact_ids,
            metadata=dict(payload.get("metadata", {})),
        )
        return self.broker.to_a2a_task(thread_id)


class BrokerGatewayHandler(BaseHTTPRequestHandler):
    """HTTP handler for BrokerGateway."""

    gateway: BrokerGateway
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path in ("/", "/agent-card", "/.well-known/agent.json"):
                self._send_json(200, self.gateway.agent_card())
                return
            self._require_auth()

            parts = [part for part in path.split("/") if part]
            if path == "/agents":
                self._send_json(200, self.gateway.list_agents())
                return
            if len(parts) == 3 and parts[0] == "agents" and parts[2] == "inbox":
                mark_delivered = parse_qs(parsed.query).get("mark_delivered", ["1"])[0] != "0"
                self._authorize_agent_access(parts[1])
                self._send_json(200, self.gateway.read_inbox(parts[1], mark_delivered=mark_delivered))
                return
            if len(parts) == 2 and parts[0] == "tasks":
                self._send_json(200, self.gateway.get_task(parts[1]))
                return
            if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "events":
                after = parse_qs(parsed.query).get("after", [""])[0]
                if self.headers.get("Accept") == "text/event-stream" or parse_qs(parsed.query).get("stream") == ["1"]:
                    self._send_sse(self.gateway.list_events(parts[1], after=after)["events"])
                else:
                    self._send_json(200, self.gateway.list_events(parts[1], after=after))
                return

            self._send_json(404, {"error": "not found"})
        except PermissionError as exc:
            self._send_json(401, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self) -> None:
        try:
            path = (urlparse(self.path).path.rstrip("/") or "/")
            self._require_auth()
            payload = self._read_json()
            parts = [part for part in path.split("/") if part]

            if path == "/agents":
                self._send_json(201, self.gateway.register_agent(payload))
                return

            if path == "/tasks":
                message = str(payload.get("message", payload.get("query", "")))
                self._send_json(201, self.gateway.create_task(message, dict(payload.get("metadata", {}))))
                return

            if len(parts) == 3 and parts[0] == "tasks":
                thread_id = parts[1]
                action = parts[2]
                status, result = self._dispatch_task_action(thread_id, action, payload)
                self._send_json(status, result)
                return

            self._send_json(404, {"error": "not found"})
        except PermissionError as exc:
            self._send_json(401, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _dispatch_task_action(self, thread_id: str, action: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        actor = self._authenticated_actor()
        if action == "messages":
            return 201, self.gateway.send_message(thread_id, payload, actor=actor)
        if action == "artifacts":
            return 201, self.gateway.publish_artifact(thread_id, payload, actor=actor)
        if action == "handoffs":
            return 201, self.gateway.create_handoff(thread_id, payload, actor=actor)
        if action == "review-requests":
            return 201, self.gateway.request_review(thread_id, payload, actor=actor)
        if action == "review-responses":
            return 201, self.gateway.respond_review(thread_id, payload, actor=actor)
        if action == "complete":
            return 200, self.gateway.complete_task(thread_id, payload, actor=actor)
        return 404, {"error": "not found"}

    def _read_json(self) -> Dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer") from exc
        if length < 0:
            raise ValueError("Content-Length must not be negative")
        if length > self.max_body_bytes:
            raise ValueError(f"request body exceeds {self.max_body_bytes} bytes")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _require_auth(self) -> None:
        token = self.gateway.auth_token
        if not token:
            return
        auth = self.headers.get("Authorization", "")
        token_header = self.headers.get("X-Oh-My-Dynamic-Token", "")
        if auth == f"Bearer {token}" or token_header == token:
            return
        raise PermissionError("missing or invalid gateway auth token")

    def _authenticated_actor(self) -> Optional[str]:
        if not self.gateway.auth_token:
            return None
        actor = self.headers.get("X-Agent-Id", "")
        if not actor:
            raise ValueError("X-Agent-Id is required when gateway auth is enabled")
        actor = validate_agent_id(actor, "X-Agent-Id")
        expected_token = self.gateway.agent_tokens.get(actor)
        if expected_token:
            supplied_token = self.headers.get("X-Agent-Token", "")
            if supplied_token != expected_token:
                raise PermissionError("missing or invalid agent actor token")
        elif actor not in self.gateway.broker.policy.system_agents:
            registered_ids = {agent.id for agent in self.gateway.broker.list_agents()}
            if actor in registered_ids:
                raise PermissionError("missing agent actor token")
        return actor

    def _authorize_agent_access(self, agent_id: str) -> None:
        if not self.gateway.auth_token:
            return
        target = validate_agent_id(agent_id, "agent_id")
        actor = self._authenticated_actor()
        if actor == target or actor in self.gateway.broker.policy.system_agents:
            return
        raise PermissionError("actor is not authorized for this agent resource")

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, events: list[Dict[str, Any]]) -> None:
        lines = []
        for event in events:
            lines.append(f"id: {event['id']}")
            lines.append(f"event: {event['kind']}")
            lines.append(f"data: {json.dumps(event, ensure_ascii=False)}")
            lines.append("")
        body = ("\n".join(lines) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(
    broker: Optional[AgentBroker] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    agent_tokens: Optional[Dict[str, str]] = None,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> ThreadingHTTPServer:
    """Create a configured broker gateway server."""
    if not _is_loopback_host(host) and not auth_token:
        raise ValueError("non-loopback gateway binding requires --auth-token or OH_MY_DYNAMIC_GATEWAY_TOKEN")
    broker = broker or AgentBroker()
    gateway = BrokerGateway(
        broker,
        base_url or f"http://{host}:{port}",
        auth_token=auth_token,
        agent_tokens=agent_tokens,
    )

    class Handler(BrokerGatewayHandler):
        pass

    Handler.gateway = gateway
    Handler.max_body_bytes = max_body_bytes
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the oh-my-Dynamic AgentBroker HTTP gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--broker-dir", default=".orchestry/agent_broker")
    parser.add_argument("--auth-token", default=os.environ.get("OH_MY_DYNAMIC_GATEWAY_TOKEN"))
    parser.add_argument("--max-body-bytes", type=int, default=DEFAULT_MAX_BODY_BYTES)
    args = parser.parse_args()

    broker = AgentBroker(args.broker_dir)
    server = create_server(
        broker,
        args.host,
        args.port,
        auth_token=args.auth_token,
        max_body_bytes=args.max_body_bytes,
    )
    print(f"oh-my-Dynamic AgentBroker gateway listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

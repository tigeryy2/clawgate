from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from python_template.core.exceptions import APIError, NotFoundError, ValidationError
from python_template.core.manifests import (
    PluginActionManifest,
    PluginManifest,
    PluginResourceManifest,
)
from python_template.core.models import (
    ActionStatus,
    InternalActionResult,
    InternalReadResult,
    PolicyItem,
    ReadQuery,
    RiskTier,
    RuntimeMode,
)
from python_template.core.plugin_registry import ActionContext


class BlueBubblesClient:
    def __init__(self):
        self.base_url = os.getenv(
            "BLUEBUBBLES_BASE_URL", "http://127.0.0.1:1234"
        ).rstrip("/")
        self.password = os.getenv("BLUEBUBBLES_PASSWORD")
        self.timeout_seconds = float(os.getenv("BLUEBUBBLES_TIMEOUT_SECONDS", "5"))

    def list_threads(self, query: ReadQuery) -> dict[str, Any]:
        offset = int(query.cursor or "0")
        raw = self._request(
            method="GET",
            path="/api/v1/chat",
            params={"offset": offset, "limit": query.limit, "q": query.q},
        )
        items = self._ensure_list(raw)
        page = items[: query.limit]
        next_cursor = str(offset + len(page)) if len(page) == query.limit else None
        return {
            "items": [self._thread_payload(item) for item in page],
            "next_cursor": next_cursor,
            "raw_items": page,
        }

    def list_messages(self, query: ReadQuery) -> dict[str, Any]:
        offset = int(query.cursor or "0")
        raw = self._request(
            method="GET",
            path="/api/v1/message",
            params={"offset": offset, "limit": query.limit, "q": query.q},
        )
        items = self._ensure_list(raw)
        page = items[: query.limit]
        next_cursor = str(offset + len(page)) if len(page) == query.limit else None
        return {
            "items": [self._message_payload(item) for item in page],
            "next_cursor": next_cursor,
            "raw_items": page,
        }

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        raw = self._request(method="GET", path=f"/api/v1/chat/{thread_id}", params={})
        return self._thread_payload(self._ensure_dict(raw))

    def get_message(self, message_id: str) -> dict[str, Any]:
        raw = self._request(
            method="GET", path=f"/api/v1/message/{message_id}", params={}
        )
        return self._message_payload(self._ensure_dict(raw))

    def send_text(self, chat_guid: str, text: str) -> dict[str, Any]:
        payload = {
            "chatGuid": chat_guid,
            "message": text,
            "method": "apple-script",
        }
        return self._ensure_dict(
            self._request(
                method="POST", path="/api/v1/message/text", params={}, payload=payload
            )
        )

    def reply(self, message_guid: str, text: str) -> dict[str, Any]:
        payload = {
            "messageGuid": message_guid,
            "message": text,
            "method": "apple-script",
        }
        return self._ensure_dict(
            self._request(
                method="POST", path="/api/v1/message/reply", params={}, payload=payload
            )
        )

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any],
        payload: dict[str, Any] | None = None,
    ) -> Any:
        query_items = {key: value for key, value in params.items() if value is not None}
        if self.password:
            query_items["password"] = self.password
        query = urllib.parse.urlencode(query_items)
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"

        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url=url, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            if exc.code == 404:
                raise NotFoundError(detail or "BlueBubbles resource not found") from exc
            raise APIError(
                500, "BLUEBUBBLES_HTTP_ERROR", detail or "BlueBubbles request failed"
            ) from exc
        except urllib.error.URLError as exc:
            raise APIError(500, "BLUEBUBBLES_UNREACHABLE", str(exc.reason)) from exc

        if not raw_body:
            return {}
        body = json.loads(raw_body)
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    @staticmethod
    def _ensure_list(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "results", "messages", "chats"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        raise ValidationError("BlueBubbles response must contain a list")

    @staticmethod
    def _ensure_dict(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        raise ValidationError("BlueBubbles response must contain an object")

    @staticmethod
    def _thread_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(
                item.get("guid") or item.get("chatGuid") or item.get("id") or "unknown"
            ),
            "display_name": item.get("displayName") or item.get("name") or "",
            "participants": item.get("participants") or [],
            "snippet": item.get("latestMessage") or item.get("text") or "",
        }

    @staticmethod
    def _message_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(
                item.get("guid")
                or item.get("messageGuid")
                or item.get("id")
                or "unknown"
            ),
            "thread_id": str(item.get("chatGuid") or item.get("threadId") or ""),
            "sender": item.get("handle") or item.get("sender") or "",
            "text": item.get("text") or "",
            "date": item.get("dateCreated") or item.get("date") or "",
        }


class IMessageBlueBubblesPlugin:
    manifest = PluginManifest(
        id="imessage",
        name="iMessage (BlueBubbles)",
        version="0.1.0",
        runtime_mode=RuntimeMode.in_process,
        resources=[
            PluginResourceManifest(
                name="threads",
                capability_id="imessage.threads.read",
                allowed_views=["headers", "body"],
            ),
            PluginResourceManifest(
                name="messages",
                capability_id="imessage.messages.read",
                allowed_views=["headers", "body"],
            ),
        ],
        required_secrets=["bluebubbles_password"],
        required_scopes=["bluebubbles.messages.read", "bluebubbles.messages.send"],
        default_policy={"max_limit": 100},
        actions=[
            PluginActionManifest(
                name="send",
                capability_id="imessage.message.send",
                resource_type="message",
                risk_tier=RiskTier.transactional,
                route_pattern="/:send/{phase}",
                supports_propose=True,
                requires_idempotency=True,
                emits_attributes=["principal", "counterparty_domain", "thread_id"],
                resource=None,
                mutating=True,
            ),
            PluginActionManifest(
                name="send",
                capability_id="imessage.thread.send",
                resource_type="message",
                risk_tier=RiskTier.transactional,
                route_pattern="/threads/{resource_id}:send/{phase}",
                supports_propose=True,
                requires_idempotency=True,
                emits_attributes=["principal", "counterparty_domain", "thread_id"],
                resource="threads",
                mutating=True,
            ),
            PluginActionManifest(
                name="reply",
                capability_id="imessage.message.reply",
                resource_type="message",
                risk_tier=RiskTier.transactional,
                route_pattern="/messages/{resource_id}:reply/{phase}",
                supports_propose=True,
                requires_idempotency=True,
                emits_attributes=["principal", "counterparty_domain", "thread_id"],
                resource="messages",
                mutating=True,
            ),
        ],
    )

    def __init__(self, client: BlueBubblesClient | None = None):
        self._client = client or BlueBubblesClient()

    def list_resource(self, resource: str, query: ReadQuery) -> InternalReadResult:
        if resource == "threads":
            result = self._client.list_threads(query)
            return self._collection_response(result, key="threads")
        if resource == "messages":
            result = self._client.list_messages(query)
            return self._collection_response(result, key="messages")
        raise NotFoundError(f"resource '{resource}' not found")

    def get_resource(
        self,
        resource: str,
        resource_id: str,
        view: str | None,
        query: ReadQuery,
    ) -> InternalReadResult:
        _ = query
        _ = view
        if resource == "threads":
            item = self._client.get_thread(thread_id=resource_id)
            principal = self._best_principal(item)
            return InternalReadResult(
                data=item,
                policy_items=[
                    PolicyItem(
                        data_ref="self",
                        attrs={
                            "resource_type": "thread",
                            "principal": principal,
                            "counterparty_domain": self._domain_for(principal),
                            "thread_id": item.get("id"),
                        },
                    )
                ],
            )
        if resource == "messages":
            item = self._client.get_message(message_id=resource_id)
            principal = str(item.get("sender") or "")
            return InternalReadResult(
                data=item,
                policy_items=[
                    PolicyItem(
                        data_ref="self",
                        attrs={
                            "resource_type": "message",
                            "principal": principal,
                            "counterparty_domain": self._domain_for(principal),
                            "thread_id": item.get("thread_id"),
                        },
                    )
                ],
            )
        raise NotFoundError(f"resource '{resource}' not found")

    def run_action(self, context: ActionContext, args: dict) -> InternalActionResult:
        text = str(args.get("text") or "").strip()
        if not text:
            raise ValidationError("args.text is required")

        if context.action.name == "send" and context.resource is None:
            chat_guid = str(args.get("chat_guid") or "").strip()
            if not chat_guid:
                raise ValidationError("global send requires args.chat_guid")
            return self._send_to_thread(
                chat_guid=chat_guid, text=text, phase=context.phase
            )

        if context.action.name == "send" and context.resource == "threads":
            if context.resource_id is None:
                raise ValidationError("thread send requires resource id")
            return self._send_to_thread(
                chat_guid=context.resource_id,
                text=text,
                phase=context.phase,
            )

        if context.action.name == "reply" and context.resource == "messages":
            if context.resource_id is None:
                raise ValidationError("reply requires resource id")
            return self._reply_to_message(
                message_guid=context.resource_id,
                text=text,
                phase=context.phase,
            )

        raise NotFoundError(f"action '{context.action.name}' not implemented")

    def _collection_response(
        self, result: dict[str, Any], key: str
    ) -> InternalReadResult:
        items = result.get("items", [])
        raw_items = result.get("raw_items", [])
        policy_items: list[PolicyItem] = []
        for idx, raw_item in enumerate(raw_items):
            principal = self._best_principal(raw_item)
            policy_items.append(
                PolicyItem(
                    data_ref=f"items[{idx}]",
                    attrs={
                        "resource_type": key.rstrip("s"),
                        "principal": principal,
                        "counterparty_domain": self._domain_for(principal),
                        "thread_id": raw_item.get("guid") or raw_item.get("chatGuid"),
                    },
                )
            )

        return InternalReadResult(
            data={"items": items, "next_cursor": result.get("next_cursor")},
            policy_items=policy_items,
        )

    def _send_to_thread(
        self, chat_guid: str, text: str, phase: str
    ) -> InternalActionResult:
        result_payload = {
            "chat_guid": chat_guid,
            "text": text,
        }
        if phase == "execute":
            delivery = self._client.send_text(chat_guid=chat_guid, text=text)
            result_payload["delivery"] = delivery

        return InternalActionResult(
            status=ActionStatus.success,
            summary=f"Send iMessage to thread {chat_guid}",
            result=result_payload,
            proposed_effect=result_payload,
            policy_items=[
                PolicyItem(
                    data_ref="result",
                    attrs={
                        "principal": chat_guid,
                        "counterparty_domain": self._domain_for(chat_guid),
                        "thread_id": chat_guid,
                    },
                )
            ],
        )

    def _reply_to_message(
        self, message_guid: str, text: str, phase: str
    ) -> InternalActionResult:
        result_payload = {
            "message_guid": message_guid,
            "text": text,
        }
        if phase == "execute":
            delivery = self._client.reply(message_guid=message_guid, text=text)
            result_payload["delivery"] = delivery

        return InternalActionResult(
            status=ActionStatus.success,
            summary=f"Reply to iMessage {message_guid}",
            result=result_payload,
            proposed_effect=result_payload,
            policy_items=[
                PolicyItem(
                    data_ref="result",
                    attrs={
                        "principal": message_guid,
                        "counterparty_domain": self._domain_for(message_guid),
                    },
                )
            ],
        )

    @staticmethod
    def _best_principal(item: dict[str, Any]) -> str:
        participants = item.get("participants")
        if isinstance(participants, list) and participants:
            first = participants[0]
            if isinstance(first, dict):
                candidate = first.get("address") or first.get("identifier")
                if isinstance(candidate, str):
                    return candidate
            if isinstance(first, str):
                return first

        for key in ("sender", "handle", "address", "chatGuid", "guid"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _domain_for(value: str) -> str | None:
        if "@" not in value:
            return None
        return value.split("@", 1)[-1].lower()

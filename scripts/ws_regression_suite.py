#!/usr/bin/env python3
"""WebSocket regression helper for VibResearch global channel."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import urlencode, urlparse, urlunparse

import requests
import websockets


@dataclass
class MessageRecord:
    raw: str
    received_at: float
    event_type: str | None


def build_ws_url(base_http: str, token: str, path: str = "/ws/global") -> str:
    parsed = urlparse(base_http)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    query = urlencode({"token": token})
    return urlunparse((scheme, netloc, path, "", query, ""))


def login_for_token(base_url: str, email: str, password: str, timeout: float) -> str:
    response = requests.post(
        base_url.rstrip("/") + "/api/auth/login",
        json={"email": email, "password": password},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Login response missing access_token")
    return token


async def collect_messages(ws_url: str, duration: float, verbose: bool) -> list[MessageRecord]:
    messages: list[MessageRecord] = []
    start = time.perf_counter()
    print(f"Connecting to {ws_url}")
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
        print("WebSocket connected")
        while time.perf_counter() - start < duration:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            timestamp = time.time()
            event_type: str | None = None
            try:
                parsed: Any = json.loads(raw)
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("type"), str):
                        event_type = parsed["type"]
                    elif isinstance(parsed.get("event"), dict):
                        inner = parsed["event"]
                        if isinstance(inner, dict) and isinstance(inner.get("type"), str):
                            event_type = inner["type"]
            except json.JSONDecodeError:
                pass
            record = MessageRecord(raw=raw, received_at=timestamp, event_type=event_type)
            messages.append(record)
            if verbose:
                stamp = time.strftime("%H:%M:%S", time.localtime(timestamp))
                label = event_type or "unknown"
                print(f"[{stamp}] {label}: {raw[:200]}")
    print("WebSocket closed")
    return messages


def summarize_messages(messages: Sequence[MessageRecord]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for record in messages:
        key = record.event_type or "unknown"
        by_type[key] = by_type.get(key, 0) + 1
    return {"total": len(messages), "by_type": by_type}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify VibResearch WebSocket connectivity")
    parser.add_argument("--base-url", default=os.getenv("VIBERESEARCH_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("VIBERESEARCH_TEST_EMAIL"))
    parser.add_argument("--password", default=os.getenv("VIBERESEARCH_TEST_PASSWORD"))
    parser.add_argument("--token", help="Use an explicit JWT token instead of logging in")
    parser.add_argument("--duration", type=float, default=15.0, help="Listen window in seconds")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout for login")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", help="Persist captured messages to JSON file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.token:
        token = args.token
    else:
        if not args.email or not args.password:
            print("Provide --token or --email/--password to authenticate", file=sys.stderr)
            return 2
        try:
            token = login_for_token(args.base_url, args.email, args.password, args.timeout)
            print("Authenticated successfully")
        except Exception as exc:  # pragma: no cover - runtime error reporting
            print(f"Authentication failed: {exc}", file=sys.stderr)
            return 1

    ws_url = build_ws_url(args.base_url, token)
    try:
        messages = asyncio.run(collect_messages(ws_url, args.duration, args.verbose))
    except Exception as exc:  # pragma: no cover
        print(f"WebSocket failure: {exc}", file=sys.stderr)
        return 1

    summary = summarize_messages(messages)
    print("\n=== WebSocket Summary ===")
    print(f"Total messages: {summary['total']}")
    for event_type, count in sorted(summary["by_type"].items()):
        print(f"  {event_type}: {count}")

    if args.output:
        payload = {
            "base_url": args.base_url,
            "ws_url": ws_url,
            "summary": summary,
            "messages": [
                {
                    "received_at": record.received_at,
                    "event_type": record.event_type,
                    "raw": record.raw,
                }
                for record in messages
            ],
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"Messages written to {args.output}")

    return 0 if summary["total"] > 0 else 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


"""session-init plugin

on_session_start でバックグラウンドスレッドを起動して
指定ファイルを先読みし、
pre_llm_call の初回ターン（is_first_turn=True）でコンテキストとして注入する。

注入先はユーザーメッセージ（システムプロンプトではない）なので
プロンプトキャッシュのプレフィックスを壊さない。

SOUL.md / memories/MEMORY.md / memories/USER.md は Hermes が
system_prompt の stable/volatile 層で自動ロード済みなので含めない。
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / "hermes"))

# session_id → 取得済みコンテキスト文字列
_context_cache: dict[str, str] = {}
# session_id → 完了通知 Event
_ready_events: dict[str, threading.Event] = {}
_lock = threading.Lock()

# 読み込ませたいファイルを HERMES_HOME からの相対パスで列挙してください
# 例:
#_UNIQUE_FILES = [
#    "PERSONA.md",
#    "PROFILE.md",
#]
_UNIQUE_FILES: list[str] = []


def _fetch_context(session_id: str) -> None:
    """バックグラウンドで固有コンテキストを収集する。"""
    parts: list[str] = []
    now = datetime.now()
    parts.append(f"--- Current Date/Time ---\n{now.strftime('%Y-%m-%d %H:%M')}")

    for rel in _UNIQUE_FILES:
        path = _HERMES_HOME / rel
        if path.exists():
            try:
                parts.append(f"--- {rel} ---\n{path.read_text(encoding='utf-8')}")
            except Exception as exc:
                logger.warning("session-init: failed to read %s: %s", rel, exc)

    context = "\n\n".join(parts)

    with _lock:
        _context_cache[session_id] = context
        event = _ready_events.get(session_id)
    if event:
        event.set()


def _on_session_start(session_id: str = "", **_) -> None:
    """セッション作成時にバックグラウンドで先読み開始。"""
    event = threading.Event()
    with _lock:
        _ready_events[session_id] = event

    t = threading.Thread(
        target=_fetch_context, args=(session_id,), name=f"session-init-{session_id[:8]}", daemon=True
    )
    t.start()
    logger.debug("session-init: prefetch started for session %s", session_id[:8])


def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **_,
) -> Optional[dict]:
    """初回ターンのみコンテキストを注入する。"""
    if not is_first_turn:
        return None

    with _lock:
        event = _ready_events.get(session_id)

    if event and not event.is_set():
        logger.debug("session-init: waiting for prefetch (session %s)…", session_id[:8])
        event.wait(timeout=15)

    with _lock:
        context = _context_cache.pop(session_id, "")
        _ready_events.pop(session_id, None)

    if not context:
        logger.debug("session-init: no context for session %s, skipping", session_id[:8])
        return None

    injected = (
        "[セッション開始コンテキスト]\n"
        + context
        + "\n\n[System: 上記を踏まえて、ユーザーを迎える挨拶を添えてから返答してください。]"
    )
    logger.debug("session-init: injecting context (%d chars)", len(injected))
    return {"context": injected}


def register(ctx) -> None:
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)

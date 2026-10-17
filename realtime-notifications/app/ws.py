import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger("ws")


class ConnectionManager:
    """Guarda os WebSockets abertos por usuário e repassa mensagens vindas do Redis pub/sub.

    Como o aviso passa pelo Redis, funciona mesmo com várias instâncias da API:
    cada instância recebe a mensagem e entrega aos sockets que ela mesma mantém.
    """

    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns[user_id].add(ws)

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        self._conns[user_id].discard(ws)
        if not self._conns[user_id]:
            self._conns.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str) -> None:
        for ws in list(self._conns.get(user_id, ())):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(user_id, ws)

    async def listen(self, redis_client) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.psubscribe("notifications:*")
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "pmessage":
                    continue
                user_id = msg["channel"].split(":", 1)[1]
                await self.send_to_user(user_id, msg["data"])
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.aclose()

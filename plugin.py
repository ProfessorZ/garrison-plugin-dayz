"""
Garrison game plugin for DayZ dedicated servers.

Uses the bundled bercon.py (native async UDP BattlEye RCON v2).
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from app.plugins.base import GamePlugin, PlayerInfo, ServerStatus, CommandDef, ServerOption
except ImportError:
    from dataclasses import dataclass, field
    from abc import ABC, abstractmethod

    @dataclass
    class PlayerInfo:
        name: str
        steam_id: Optional[str] = None

    @dataclass
    class ServerStatus:
        online: bool
        player_count: int = 0
        version: Optional[str] = None
        extra: dict = field(default_factory=dict)

    @dataclass
    class CommandDef:
        name: str
        description: str
        category: str
        params: list = field(default_factory=list)
        admin_only: bool = False
        example: str = ""

    @dataclass
    class ServerOption:
        name: str
        value: str
        option_type: str
        category: str = "General"
        description: str = ""

    class GamePlugin(ABC):
        PLUGIN_API_VERSION = 1
        custom_connection: bool = False

        @property
        @abstractmethod
        def game_type(self) -> str: ...

        @property
        @abstractmethod
        def display_name(self) -> str: ...

        @abstractmethod
        async def parse_players(self, raw_response: str) -> list: ...

        @abstractmethod
        async def get_status(self, send_command) -> ServerStatus: ...

        @abstractmethod
        def get_commands(self) -> list: ...

        def format_command(self, command: str) -> str:
            return command

        async def kick_player(self, send_command, name: str, reason: str = "") -> str:
            return await send_command(f"kick {name} {reason}".strip())

        async def ban_player(self, send_command, name: str, reason: str = "") -> str:
            return await send_command(f"ban {name} {reason}".strip())

        async def unban_player(self, send_command, name: str) -> str:
            return await send_command(f"removeBan {name}")

        async def get_options(self, send_command) -> list:
            return []

        async def set_option(self, send_command, name: str, value: str) -> str:
            return "Not supported"

        async def connect_custom(self, host: str, port: int, password: str) -> None:
            pass

        async def disconnect_custom(self) -> None:
            pass

        async def send_command_custom(self, command: str, content: str = "") -> str:
            raise NotImplementedError


from bercon import BERConConnection

_PLAYER_LINE_RE = re.compile(
    r"^\s*(\d+)\s+"            # index
    r"(\d+\.\d+\.\d+\.\d+)"   # IP
    r":(\d+)\s+"               # port
    r"(\d+)\s+"                # ping
    r"([0-9a-fA-F]{32}|-)(?:\([^)]+\))?\s+"  # BE GUID or - (with optional status like (OK))
    r"(.+?)"                   # player name
    r"(?:\s+\(Lobby\))?\s*$",
    re.MULTILINE,
)


class DayZPlugin(GamePlugin):
    """Garrison plugin for DayZ dedicated servers (BattlEye RCON)."""

    custom_connection = True

    def __init__(self):
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._password: Optional[str] = None
        self._rcon: Optional[BERConConnection] = None

    @property
    def game_type(self) -> str:
        return "dayz"

    @property
    def display_name(self) -> str:
        return "DayZ"

    async def connect_custom(self, host: str, port: int, password: str) -> None:
        loop = asyncio.get_running_loop()
        resolved = await loop.run_in_executor(None, lambda: socket.gethostbyname(host))
        self._host = resolved
        self._port = port
        self._password = password
        self._rcon = BERConConnection(resolved, port, password)
        try:
            ok = await asyncio.wait_for(self._rcon.connect(), timeout=10)
            if not ok:
                self._rcon = None
                raise RuntimeError("BattlEye RCON login failed — check host, port, and password")
        except asyncio.TimeoutError:
            self._rcon = None
            raise RuntimeError(f"Timed out connecting to DayZ RCON at {resolved}:{port}")

    async def disconnect_custom(self) -> None:
        if self._rcon:
            self._rcon.close()
            self._rcon = None

    async def send_command_custom(self, command: str, content: str = "") -> str:
        if not self._rcon:
            raise RuntimeError("Not connected — call connect_custom first")
        return await asyncio.wait_for(self._rcon.send_command(command), timeout=10)

    async def parse_players(self, raw_response: str) -> list:
        players = []
        for m in _PLAYER_LINE_RE.finditer(raw_response):
            guid = m.group(5) if m.group(5) != "-" else None
            players.append(PlayerInfo(
                name=m.group(6).strip(),
                steam_id=guid,
            ))
        return players

    async def get_status(self, send_command) -> ServerStatus:
        try:
            raw = await self.send_command_custom("players")
            players = await self.parse_players(raw)
            return ServerStatus(online=True, player_count=len(players))
        except Exception as e:
            logger.warning("DayZ status check failed: %s", e)
            return ServerStatus(online=False, player_count=0)

    async def kick_player(self, send_command, name: str, reason: str = "") -> str:
        return await self.send_command_custom(f"kick {name} {reason}".strip())

    async def ban_player(self, send_command, name: str, reason: str = "") -> str:
        return await self.send_command_custom(f"ban {name} {reason}".strip())

    async def unban_player(self, send_command, name: str) -> str:
        return await self.send_command_custom(f"removeBan {name}")

    def get_commands(self) -> list:
        try:
            from schema import get_commands
            return get_commands()
        except ImportError:
            return []

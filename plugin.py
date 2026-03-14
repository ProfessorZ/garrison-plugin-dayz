"""
Garrison game plugin for DayZ dedicated servers.

Uses BattlEye RCON v2 (UDP) to communicate with the server.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from bercon import BERConConnection

logger = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    """Represents a connected DayZ player."""
    index: int
    name: str
    ip: str
    port: int
    ping: int
    be_guid: Optional[str]
    in_lobby: bool
    steam_id: Optional[str] = field(default=None)

    def __post_init__(self):
        # BE GUID serves as the steam identity reference
        if self.be_guid and not self.steam_id:
            self.steam_id = self.be_guid


@dataclass
class ServerStatus:
    """Current server status snapshot."""
    online: bool
    player_count: int
    players: list[PlayerInfo]


class GamePlugin:
    """Garrison plugin for DayZ dedicated servers."""

    game_type = "dayz"
    display_name = "DayZ"
    custom_connection = True

    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self._rcon: Optional[BERConConnection] = None

    async def connect(self) -> bool:
        """Establish the RCON connection."""
        self._rcon = BERConConnection(self.host, self.port, self.password)
        return await self._rcon.connect()

    def disconnect(self):
        """Close the RCON connection."""
        if self._rcon:
            self._rcon.close()
            self._rcon = None

    async def _send(self, cmd: str) -> str:
        if not self._rcon:
            raise RuntimeError("Not connected")
        return await self._rcon.send_command(cmd)

    # ------------------------------------------------------------------
    # Player parsing
    # ------------------------------------------------------------------

    _PLAYER_LINE_RE = re.compile(
        r"^\s*(\d+)\s+"           # index
        r"(\d+\.\d+\.\d+\.\d+)"  # IP
        r":(\d+)\s+"              # port
        r"(\d+)\s+"               # ping
        r"([0-9a-fA-F]+|-)\s+"   # BE GUID (or - if not yet assigned)
        r"(.+?)"                  # player name
        r"(?:\s+\(Lobby\))?\s*$", # optional lobby indicator
        re.MULTILINE,
    )

    def _parse_players(self, raw: str) -> list[PlayerInfo]:
        """Parse the output of the `players` command."""
        players = []
        for m in self._PLAYER_LINE_RE.finditer(raw):
            guid = m.group(5) if m.group(5) != "-" else None
            in_lobby = "(Lobby)" in m.group(0)
            players.append(PlayerInfo(
                index=int(m.group(1)),
                name=m.group(6).strip(),
                ip=m.group(2),
                port=int(m.group(3)),
                ping=int(m.group(4)),
                be_guid=guid,
                in_lobby=in_lobby,
            ))
        return players

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_players(self) -> list[PlayerInfo]:
        """Fetch and parse the current player list."""
        raw = await self._send("players")
        return self._parse_players(raw)

    async def get_status(self) -> ServerStatus:
        """Return current server status."""
        try:
            players = await self.get_players()
            return ServerStatus(online=True, player_count=len(players), players=players)
        except Exception:
            logger.exception("Failed to get server status")
            return ServerStatus(online=False, player_count=0, players=[])

    async def kick_player(self, name: str, reason: str = "") -> str:
        """Kick a player by name."""
        player = await self._find_player(name)
        if not player:
            return f"Player '{name}' not found"
        cmd = f"kick {player.index} {reason}".strip()
        return await self._send(cmd)

    async def ban_player(self, name: str, reason: str = "", duration: int = 0) -> str:
        """Ban a player by name. Uses BE GUID when available, otherwise index."""
        player = await self._find_player(name)
        if not player:
            return f"Player '{name}' not found"
        if player.be_guid:
            cmd = f"addBan {player.be_guid} {duration} {reason}".strip()
        else:
            cmd = f"ban {player.index} {reason}".strip()
        return await self._send(cmd)

    async def unban_player(self, identifier: str) -> str:
        """Unban a player by finding their entry in the ban list.

        `identifier` can be a name or GUID substring.
        """
        bans_raw = await self._send("bans")
        # Ban list lines: "N  GUID  duration  reason"
        for line in bans_raw.splitlines():
            if identifier.lower() in line.lower():
                match = re.match(r"^\s*(\d+)\s+", line)
                if match:
                    ban_index = match.group(1)
                    return await self._send(f"removeBan {ban_index}")
        return f"No ban entry matching '{identifier}' found"

    async def say(self, message: str, player_index: int = -1) -> str:
        """Broadcast a message to all players (default) or a specific player."""
        return await self._send(f"say {player_index} {message}")

    async def shutdown(self) -> str:
        """Shut down the DayZ server."""
        return await self._send("shutdown")

    async def _find_player(self, name: str) -> Optional[PlayerInfo]:
        """Look up a player by name (case-insensitive)."""
        players = await self.get_players()
        name_lower = name.lower()
        for p in players:
            if p.name.lower() == name_lower:
                return p
        # Partial match fallback
        for p in players:
            if name_lower in p.name.lower():
                return p
        return None

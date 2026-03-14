"""
Command schema definitions for the DayZ RCON plugin.

Each CommandDef describes a command exposed through the Garrison interface.
"""

from dataclasses import dataclass, field


@dataclass
class ParamDef:
    """A single command parameter."""
    name: str
    description: str
    required: bool = True
    param_type: str = "string"
    default: str | None = None


@dataclass
class CommandDef:
    """Definition of an RCON command for the Garrison UI/API."""
    name: str
    description: str
    category: str
    params: list[ParamDef] = field(default_factory=list)
    rcon_template: str = ""


COMMANDS: list[CommandDef] = [
    CommandDef(
        name="players",
        description="List all connected players with index, IP, ping, BE GUID, and name.",
        category="players",
        rcon_template="players",
    ),
    CommandDef(
        name="kick",
        description="Kick a player by their index number.",
        category="players",
        params=[
            ParamDef(name="index", description="Player index number", param_type="int"),
            ParamDef(name="reason", description="Kick reason", required=False, default=""),
        ],
        rcon_template="kick {index} {reason}",
    ),
    CommandDef(
        name="ban",
        description="Ban a connected player by index (adds to BattlEye ban list).",
        category="players",
        params=[
            ParamDef(name="index", description="Player index number", param_type="int"),
            ParamDef(name="reason", description="Ban reason", required=False, default=""),
        ],
        rcon_template="ban {index} {reason}",
    ),
    CommandDef(
        name="addBan",
        description="Add a ban by BattlEye GUID with optional duration.",
        category="bans",
        params=[
            ParamDef(name="guid", description="BattlEye GUID"),
            ParamDef(name="duration", description="Ban duration in minutes (0 = permanent)", param_type="int", default="0"),
            ParamDef(name="reason", description="Ban reason", required=False, default=""),
        ],
        rcon_template="addBan {guid} {duration} {reason}",
    ),
    CommandDef(
        name="removeBan",
        description="Remove a ban by its index in the ban list.",
        category="bans",
        params=[
            ParamDef(name="index", description="Ban list index number", param_type="int"),
        ],
        rcon_template="removeBan {index}",
    ),
    CommandDef(
        name="bans",
        description="Show all entries in the BattlEye ban list.",
        category="bans",
        rcon_template="bans",
    ),
    CommandDef(
        name="shutdown",
        description="Shut down the DayZ server.",
        category="server",
        rcon_template="shutdown",
    ),
    CommandDef(
        name="say",
        description="Send a message to all players or a specific player.",
        category="server",
        params=[
            ParamDef(name="player_index", description="Player index (-1 for broadcast)", param_type="int", default="-1"),
            ParamDef(name="message", description="Message text"),
        ],
        rcon_template="say {player_index} {message}",
    ),
    CommandDef(
        name="RConPassword",
        description="Change the RCON password.",
        category="server",
        params=[
            ParamDef(name="password", description="New RCON password"),
        ],
        rcon_template="RConPassword {password}",
    ),
]

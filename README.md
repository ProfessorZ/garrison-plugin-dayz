# garrison-plugin-dayz

RCON plugin for DayZ dedicated servers using the standard BattlEye RCON v2 protocol (UDP).

## Features

- Full BattlEye RCON v2 implementation (login, command/response, multi-packet reassembly)
- Automatic server message ACK (prevents client disconnect after 10s)
- 30-second keepalive to maintain connection
- Player list parsing with index, IP, ping, BE GUID, name, and lobby status
- Kick, ban (by index or BE GUID), and unban support
- Chat broadcast to all players or direct message to individual players
- Server shutdown command

## DayZ vs Reforger

DayZ provides significantly richer player identity data through BattlEye RCON compared to Arma Reforger:

| Feature | DayZ | Reforger |
|---------|------|----------|
| Player name | Yes | Yes |
| Steam identity | BE GUID (derived from Steam ID) | No |
| IP address | Yes | No |
| Ping | Yes | No |
| Player index (for kick/say) | Yes | No |
| Chat broadcast | `say -1 <msg>` | No |
| Direct message | `say N <msg>` | No |
| Ban by GUID | Yes (persistent across sessions) | No |

The BE GUID is a hash derived from the player's Steam64 ID, enabling persistent bans that survive name changes and reconnects.

## DayZ RCON Setup

### Server Configuration

DayZ RCON is configured in the BattlEye server config file, typically located at:

```
<server_profile>/battleye/BEServer_x64.cfg
```

Contents:

```
RConPassword mySecretPassword
RConPort 2302
```

**Important:** DayZ uses the **game port** for RCON (default 2302 UDP). There is no separate RCON port — the game and RCON traffic share the same port.

### Default Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 2302 | UDP | Game + RCON |
| 27016 | UDP | Steam query |

## BattlEye Bans vs In-Game Bans

- **BE Bans** (`ban`, `addBan`): Stored in BattlEye's ban list (`bans.txt`). Uses BE GUIDs for persistent identification. Managed via RCON `bans`, `addBan`, `removeBan` commands.
- **In-game bans**: Some DayZ server frameworks may have their own ban systems, but the standard RCON interface only manages BE bans.

BE bans are preferred because they use the GUID (tied to Steam ID), so players cannot evade by changing their name.

## Player Tracking

The plugin tracks players via:

1. **Player index** — assigned on connect, used for `kick` and `say` commands
2. **BE GUID** — persistent identifier tied to Steam account, used for `ban` and `addBan`
3. **IP address** — available for logging and IP-based tracking
4. **Ping** — available for monitoring connection quality

## Installation

1. Copy the plugin files into your Garrison plugins directory:

```
garrison/plugins/dayz/
├── manifest.json
├── bercon.py
├── plugin.py
└── schema.py
```

2. Configure the connection in your Garrison server settings:

```json
{
  "host": "your-server-ip",
  "port": 2302,
  "password": "your-rcon-password"
}
```

3. Restart Garrison to load the plugin.

## Commands

| Command | Description |
|---------|-------------|
| `players` | List connected players |
| `kick <index> [reason]` | Kick player by index |
| `ban <index> [reason]` | Ban player by index |
| `addBan <GUID> <duration> [reason]` | Ban by BE GUID (duration=0 for permanent) |
| `removeBan <index>` | Remove ban by ban list index |
| `bans` | Show all bans |
| `say <index> <message>` | Message player (use -1 for broadcast) |
| `shutdown` | Shut down server |
| `RConPassword <password>` | Change RCON password |

## License

MIT

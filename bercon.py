"""
Async UDP BattlEye RCON v2 connection for DayZ dedicated servers.

Implements the standard BattlEye RCON protocol over UDP with login,
command/response (including multi-packet reassembly), server message
auto-ACK, and keepalive.
"""

import asyncio
import struct
import zlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Header constants
HEADER_BE = b"\x42\x45"  # "BE"
HEADER_FF = 0xFF

# Packet types
PACKET_LOGIN = 0x00
PACKET_COMMAND = 0x01
PACKET_SERVER_MSG = 0x02

# Timings
KEEPALIVE_INTERVAL = 30
RESPONSE_TIMEOUT = 3
MAX_RETRIES = 1


def _build_packet(payload: bytes) -> bytes:
    """Build a BattlEye RCON packet with header, CRC32, and 0xFF prefix."""
    body = bytes([HEADER_FF]) + payload
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return HEADER_BE + struct.pack("<I", crc) + body


def _verify_packet(data: bytes) -> Optional[bytes]:
    """Verify and strip the BE header+CRC, returning the payload after 0xFF."""
    if len(data) < 7:
        return None
    if data[:2] != HEADER_BE:
        return None
    crc_received = struct.unpack("<I", data[2:6])[0]
    body = data[6:]
    crc_computed = zlib.crc32(body) & 0xFFFFFFFF
    if crc_received != crc_computed:
        logger.warning("CRC mismatch: received %08x, computed %08x", crc_received, crc_computed)
        return None
    if body[0] != HEADER_FF:
        return None
    return body[1:]  # payload after 0xFF


class BERConConnection:
    """Async BattlEye RCON v2 UDP connection."""

    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional["_BERConProtocol"] = None
        self._seq: int = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._multipart: dict[int, dict] = {}
        self._keepalive_task: Optional[asyncio.Task] = None
        self._logged_in = False
        self._on_server_message = None

    async def connect(self) -> bool:
        """Connect and authenticate with the RCON server."""
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _BERConProtocol(self),
            remote_addr=(self.host, self.port),
        )
        self._transport = transport
        self._protocol = protocol

        # Send login packet
        login_payload = bytes([PACKET_LOGIN]) + self.password.encode("ascii")
        packet = _build_packet(login_payload)

        login_future = loop.create_future()
        self._pending[-1] = login_future  # sentinel key for login response
        self._transport.sendto(packet)

        try:
            result = await asyncio.wait_for(login_future, timeout=RESPONSE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error("Login timed out")
            self.close()
            return False

        if result:
            self._logged_in = True
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            logger.info("Logged in to %s:%d", self.host, self.port)
            return True

        logger.error("Login failed (bad password)")
        self.close()
        return False

    async def send_command(self, cmd: str) -> str:
        """Send an RCON command and return the response string.

        Handles multi-packet reassembly. Retries once on timeout.
        """
        if not self._logged_in:
            raise RuntimeError("Not connected")

        for attempt in range(1 + MAX_RETRIES):
            try:
                return await self._send_command_once(cmd)
            except asyncio.TimeoutError:
                if attempt < MAX_RETRIES:
                    logger.warning("Command '%s' timed out, retrying...", cmd)
                else:
                    raise asyncio.TimeoutError(f"Command '{cmd}' timed out after {1 + MAX_RETRIES} attempts")

    async def _send_command_once(self, cmd: str) -> str:
        loop = asyncio.get_running_loop()
        seq = self._seq % 256
        self._seq += 1

        payload = bytes([PACKET_COMMAND, seq]) + cmd.encode("ascii")
        packet = _build_packet(payload)

        future = loop.create_future()
        self._pending[seq] = future
        self._transport.sendto(packet)

        result = await asyncio.wait_for(future, timeout=RESPONSE_TIMEOUT)
        return result

    def _ack_server_message(self, seq: int):
        """Send ACK for a server message (type 0x02)."""
        payload = bytes([PACKET_SERVER_MSG, seq])
        packet = _build_packet(payload)
        self._transport.sendto(packet)

    async def _keepalive_loop(self):
        """Send empty command packets every 30s to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self._logged_in and self._transport:
                    seq = self._seq % 256
                    self._seq += 1
                    payload = bytes([PACKET_COMMAND, seq])
                    packet = _build_packet(payload)
                    self._transport.sendto(packet)
                    logger.debug("Keepalive sent (seq %d)", seq)
        except asyncio.CancelledError:
            pass

    def _handle_data(self, data: bytes):
        """Process an incoming packet from the server."""
        payload = _verify_packet(data)
        if payload is None:
            logger.warning("Received invalid packet (%d bytes)", len(data))
            return

        if len(payload) < 1:
            return

        ptype = payload[0]

        if ptype == PACKET_LOGIN:
            # Login response: 0x00 + 0x01 (success) or 0x00 (fail)
            success = len(payload) >= 2 and payload[1] == 0x01
            future = self._pending.pop(-1, None)
            if future and not future.done():
                future.set_result(success)

        elif ptype == PACKET_COMMAND:
            if len(payload) < 2:
                return
            seq = payload[1]
            body = payload[2:]

            # Check for multi-packet response
            if len(body) >= 3 and body[0] == 0x00:
                total = body[1]
                index = body[2]
                part_data = body[3:]
                self._handle_multipart(seq, total, index, part_data)
            else:
                # Single-packet response
                future = self._pending.pop(seq, None)
                if future and not future.done():
                    future.set_result(body.decode("ascii", errors="replace"))

        elif ptype == PACKET_SERVER_MSG:
            if len(payload) < 2:
                return
            seq = payload[1]
            message = payload[2:].decode("ascii", errors="replace")
            self._ack_server_message(seq)
            logger.info("Server message [seq %d]: %s", seq, message)
            if self._on_server_message:
                self._on_server_message(seq, message)

    def _handle_multipart(self, seq: int, total: int, index: int, data: bytes):
        """Reassemble multi-packet command responses."""
        if seq not in self._multipart:
            self._multipart[seq] = {"total": total, "parts": {}}

        entry = self._multipart[seq]
        entry["parts"][index] = data

        if len(entry["parts"]) == total:
            # All parts received — reassemble in order
            full = b"".join(entry["parts"][i] for i in range(total))
            del self._multipart[seq]
            future = self._pending.pop(seq, None)
            if future and not future.done():
                future.set_result(full.decode("ascii", errors="replace"))

    def close(self):
        """Close the connection and cancel background tasks."""
        self._logged_in = False
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self._transport:
            self._transport.close()
            self._transport = None
        # Cancel pending futures
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        self._multipart.clear()


class _BERConProtocol(asyncio.DatagramProtocol):
    """asyncio datagram protocol handler for BERCon."""

    def __init__(self, connection: BERConConnection):
        self._conn = connection

    def datagram_received(self, data: bytes, addr):
        self._conn._handle_data(data)

    def error_received(self, exc):
        logger.error("UDP error: %s", exc)

    def connection_lost(self, exc):
        if exc:
            logger.warning("Connection lost: %s", exc)

"""BoostNet Hybrid Session Proxy (Approach B).

Lineage & Architectural Heritage:
- Morhaus/dispatch-proxy & extremecoders-re/go-dispatch-proxy: Multi-interface SOCKS5 load
  balancing, zero-copy async stream piping with backpressure, and contention-ratio weighted scheduling.
- QUIC-to-TCP auto-fallback: SOCKS5 UDP ASSOCIATE (0x03) rejection with 0x07 (Command not supported),
  forcing Chrome and web browsers to fall back to TCP connections that can be distributed.
- Zero-MITM Domain Affinity: Sticky host hashing for banking, college ERP, and GitHub logins,
  combined with stateless multi-phone striping for YouTube (googlevideo.com), pip, npm, and CDNs.
- Dead-interface instant failover: SOCKS5 connect timeout (>2.5s) marks degraded and shifts traffic.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import ipaddress
import logging
import socket
import struct
import time
from typing import Any, Dict, List, Optional
import zlib

from backend.config import (
    CONNECT_FAILOVER_TIMEOUT_SEC,
    PROXY_HOST,
    PROXY_PORT,
    STATELESS_CDN_DOMAINS,
)
from backend.engine.congestion_detector import congestion_detector
from backend.engine.node_manager import NodeManager, NodeStatus, PhoneNode, node_manager

logger = logging.getLogger("boostnet.session_proxy")


@dataclass
class ProxySession:
    session_id: str
    client_addr: str
    target_host: str
    target_port: int
    assigned_node_id: str
    carrier: str
    accent_color: str
    routing_type: str                  # "⚡ Striped CDN" or "🔒 Sticky Auth Host"
    bytes_in: int = 0
    bytes_out: int = 0
    start_time: float = field(default_factory=time.time)
    status: str = "ACTIVE"             # "ACTIVE", "CLOSED", "FAILED"

    @property
    def total_bytes(self) -> int:
        return self.bytes_in + self.bytes_out


class SessionProxy:
    """Asynchronous SOCKS5 & HTTP CONNECT load balancer with intelligent domain routing."""

    def __init__(self, manager: Optional[NodeManager] = None) -> None:
        self.node_manager = manager or node_manager
        self.host = PROXY_HOST
        self.port = PROXY_PORT
        self.server: Optional[asyncio.Server] = None
        self._sticky_cache: Dict[str, str] = {} # domain -> node_id
        self._active_sessions: Dict[str, ProxySession] = {}
        self._session_counter = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Starts local SOCKS5 proxy server."""
        if self.server:
            return
        self.server = await asyncio.start_server(
            self._handle_client_connection, self.host, self.port, reuse_address=True
        )
        logger.info(f"BoostNet Session Proxy (Approach B) listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("BoostNet Session Proxy stopped.")

    def get_active_sessions_telemetry(self) -> List[Dict[str, Any]]:
        # Return last 30 active or recent sessions
        sessions = sorted(
            self._active_sessions.values(), key=lambda s: s.start_time, reverse=True
        )[:30]
        return [
            {
                "session_id": s.session_id,
                "host": f"{s.target_host}:{s.target_port}",
                "node_id": s.assigned_node_id,
                "carrier": s.carrier,
                "accent_color": s.accent_color,
                "routing_type": s.routing_type,
                "bytes": s.total_bytes,
                "status": s.status,
                "duration_sec": round(time.time() - s.start_time, 1),
            }
            for s in sessions
        ]

    async def _handle_client_connection(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        """Handles incoming client connection (SOCKS5 handshake or HTTP CONNECT)."""
        client_addr = client_writer.get_extra_info("peername")
        client_ip = f"{client_addr[0]}:{client_addr[1]}" if client_addr else "127.0.0.1:0"

        try:
            # Peek first byte to check if SOCKS5 (0x05) or HTTP (e.g. 'C' for CONNECT, 'G' for GET)
            first_byte = await client_reader.read(1)
            if not first_byte:
                client_writer.close()
                return

            if first_byte == b"\x05":
                # SOCKS5 Protocol
                await self._handle_socks5(first_byte, client_reader, client_writer, client_ip)
            elif first_byte in (b"C", b"G", b"P", b"H"):
                # HTTP CONNECT / Plain HTTP Proxy Tunnel
                rest = await client_reader.readuntil(b"\r\n")
                first_line = (first_byte + rest).decode("latin-1", errors="ignore")
                await self._handle_http_connect(first_line, client_reader, client_writer, client_ip)
            else:
                logger.warning(f"Unsupported proxy protocol byte: {first_byte}")
                client_writer.close()

        except Exception as e:
            logger.debug(f"Connection handling error from {client_ip}: {e}")
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception:
                pass

    async def _handle_socks5(
        self,
        first_byte: bytes,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        client_ip: str,
    ) -> None:
        """Full SOCKS5 protocol handler with QUIC rejection and upstream dispatching."""
        # 1. Read authentication methods
        nmethods_byte = await client_reader.read(1)
        if not nmethods_byte:
            return
        nmethods = nmethods_byte[0]
        methods = await client_reader.read(nmethods)

        # Reply: NO AUTH REQUIRED (0x05, 0x00)
        client_writer.write(b"\x05\x00")
        await client_writer.drain()

        # 2. Read SOCKS5 Request
        req_header = await client_reader.read(4)
        if len(req_header) < 4:
            return

        ver, cmd, rsv, atyp = req_header

        # Edge Case 1: QUIC / HTTP/3 UDP ASSOCIATE Rejection!
        if cmd == 0x03:
            # 0x03 = UDP ASSOCIATE
            # Reply 0x07 = Command not supported. Forces Chrome to fall back to TCP!
            logger.info("Chrome attempted SOCKS5 UDP ASSOCIATE (QUIC). Returning 0x07 (Force TCP Fallback).")
            client_writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            await client_writer.drain()
            client_writer.close()
            return

        if cmd != 0x01:
            # Only TCP CONNECT (0x01) supported
            client_writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            await client_writer.drain()
            client_writer.close()
            return

        # 3. Parse Destination Host and Port
        target_host: str = ""
        if atyp == 0x01:
            # IPv4 (4 bytes)
            ip_bytes = await client_reader.read(4)
            target_host = socket.inet_ntoa(ip_bytes)
        elif atyp == 0x03:
            # Domain name (1-byte length followed by string)
            domain_len_byte = await client_reader.read(1)
            domain_len = domain_len_byte[0]
            domain_bytes = await client_reader.read(domain_len)
            target_host = domain_bytes.decode("latin-1", errors="ignore")
        elif atyp == 0x04:
            # IPv6 (16 bytes)
            ip_bytes = await client_reader.read(16)
            target_host = socket.inet_ntop(socket.AF_INET6, ip_bytes)
        else:
            client_writer.write(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            await client_writer.drain()
            client_writer.close()
            return

        port_bytes = await client_reader.read(2)
        target_port = struct.unpack("!H", port_bytes)[0]

        # 4. Dispatch traffic through best phone node
        await self._dispatch_and_pipe(
            client_reader,
            client_writer,
            client_ip,
            target_host,
            target_port,
            is_socks5=True,
        )

    async def _handle_http_connect(
        self,
        first_line: str,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        client_ip: str,
    ) -> None:
        """Handles HTTP CONNECT target_host:port HTTP/1.1 tunnels."""
        parts = first_line.strip().split()
        if len(parts) >= 2 and parts[0].upper() == "CONNECT":
            host_port = parts[1]
            if ":" in host_port:
                target_host, port_str = host_port.split(":", 1)
                target_port = int(port_str)
            else:
                target_host = host_port
                target_port = 443

            # Consume headers until empty line \r\n\r\n
            while True:
                line = await client_reader.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break

            await self._dispatch_and_pipe(
                client_reader,
                client_writer,
                client_ip,
                target_host,
                target_port,
                is_socks5=False,
            )
        else:
            client_writer.close()

    def _determine_routing(self, target_host: str) -> Tuple[PhoneNode, str]:
        """Decides routing type: ⚡ Striped CDN vs 🔒 Sticky Auth Host."""
        active_nodes = self.node_manager.get_active_nodes()
        if not active_nodes:
            # Fallback mock/direct node if none active
            default_node = PhoneNode(
                node_id="127.0.0.1:direct",
                device_name="Direct Laptop Wi-Fi",
                carrier="Local Wi-Fi",
                host="127.0.0.1",
                port=0,
                accent_color="#38bdf8",
            )
            return default_node, "⚡ Direct Host"

        # Check if stateless CDN domain
        is_stateless_cdn = any(
            target_host.lower().endswith(cdn_dom) or target_host.lower() == cdn_dom
            for cdn_dom in STATELESS_CDN_DOMAINS
        )

        if is_stateless_cdn:
            # Use go-dispatch-proxy weighted contention scheduling
            node = self.node_manager.select_next_node_weighted() or active_nodes[0]
            return node, "⚡ Striped CDN"
        else:
            # Sticky Host Pinning
            root_domain = ".".join(target_host.split(".")[-2:]) if "." in target_host else target_host
            if root_domain in self._sticky_cache:
                cached_id = self._sticky_cache[root_domain]
                node = self.node_manager.get_node(cached_id)
                if node and node.is_eligible():
                    return node, "🔒 Sticky Auth Host"

            # Deterministic hash: crc32(root_domain) % len(active_nodes)
            hash_idx = zlib.crc32(root_domain.encode()) % len(active_nodes)
            node = active_nodes[hash_idx]
            self._sticky_cache[root_domain] = node.node_id
            return node, "🔒 Sticky Auth Host"

    async def _dispatch_and_pipe(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        client_ip: str,
        target_host: str,
        target_port: int,
        is_socks5: bool,
    ) -> None:
        """Bridges client socket with upstream phone node proxy using zero-copy async pipes."""
        self._session_counter += 1
        session_id = f"sess_{self._session_counter}"

        node, routing_type = self._determine_routing(target_host)

        session = ProxySession(
            session_id=session_id,
            client_addr=client_ip,
            target_host=target_host,
            target_port=target_port,
            assigned_node_id=node.node_id,
            carrier=node.carrier,
            accent_color=node.accent_color,
            routing_type=routing_type,
        )

        async with self._lock:
            self._active_sessions[session_id] = session

        upstream_reader: Optional[asyncio.StreamReader] = None
        upstream_writer: Optional[asyncio.StreamWriter] = None

        try:
            # Connect to upstream phone node proxy
            upstream_reader, upstream_writer = await self._connect_upstream_with_failover(
                node, target_host, target_port
            )

            # Upstream connected! Notify client of success
            if is_socks5:
                # SOCKS5 success reply: 0x05, 0x00 (SUCCESS), 0x00, 0x01, 0.0.0.0:0
                client_writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
                await client_writer.drain()
            else:
                # HTTP CONNECT 200 Connection Established
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()

            node.active_connections += 1

            # Bi-directional zero-copy piping with backpressure (dispatch-proxy lineage)
            pipe_out = asyncio.create_task(self._pipe(client_reader, upstream_writer, session, is_inbound=False))
            pipe_in = asyncio.create_task(self._pipe(upstream_reader, client_writer, session, is_inbound=True))
            done, pending = await asyncio.wait([pipe_out, pipe_in], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()

            session.status = "CLOSED"

        except Exception as e:
            logger.debug(f"Session {session_id} to {target_host}:{target_port} failed: {e}")
            session.status = "FAILED"
            if is_socks5:
                try:
                    # 0x05 = Connection refused / Host unreachable
                    client_writer.write(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
                    await client_writer.drain()
                except Exception:
                    pass
        finally:
            node.active_connections = max(0, node.active_connections - 1)
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception:
                pass
            if upstream_writer:
                try:
                    upstream_writer.close()
                    await upstream_writer.wait_closed()
                except Exception:
                    pass

    async def _connect_upstream_with_failover(
        self, node: PhoneNode, target_host: str, target_port: int
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connects to phone node proxy with failover on timeout / failure."""
        attempts = 0
        candidate_node = node

        while attempts < 3:
            attempts += 1
            if candidate_node.port == 0:
                # Direct connection without proxy
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port),
                    timeout=CONNECT_FAILOVER_TIMEOUT_SEC,
                )
                return reader, writer

            try:
                # Connect to phone's SOCKS5 port
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(candidate_node.host, candidate_node.port),
                    timeout=CONNECT_FAILOVER_TIMEOUT_SEC,
                )

                # Upstream SOCKS5 handshake
                writer.write(b"\x05\x01\x00")
                await writer.drain()

                resp = await reader.read(2)
                if len(resp) < 2 or resp != b"\x05\x00":
                    writer.close()
                    raise ConnectionError("Upstream SOCKS5 handshake rejected")

                # Send target request to upstream
                host_bytes = target_host.encode("idna")
                req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + struct.pack("!H", target_port)
                writer.write(req)
                await writer.drain()

                conn_resp = await reader.read(4)
                if len(conn_resp) < 4 or conn_resp[1] != 0x00:
                    writer.close()
                    raise ConnectionError(f"Upstream CONNECT failed with code {conn_resp[1] if len(conn_resp)>1 else 'EOF'}")

                # Read remainder of bind address
                bind_atyp = conn_resp[3]
                if bind_atyp == 0x01:
                    await reader.read(4 + 2)
                elif bind_atyp == 0x03:
                    domain_len = (await reader.read(1))[0]
                    await reader.read(domain_len + 2)
                elif bind_atyp == 0x04:
                    await reader.read(16 + 2)

                return reader, writer

            except Exception as e:
                logger.warning(
                    f"Upstream connection failed on node {candidate_node.device_name} ({e}). Marking DEGRADED and failing over..."
                )
                candidate_node.status = NodeStatus.DEGRADED
                # Select alternative active node
                active_alternatives = [
                    n for n in self.node_manager.get_active_nodes() if n.node_id != candidate_node.node_id
                ]
                if active_alternatives:
                    candidate_node = active_alternatives[0]
                else:
                    raise

        raise ConnectionError("All upstream candidate nodes failed")

    async def _pipe(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session: ProxySession,
        is_inbound: bool,
    ) -> None:
        """Bidirectional zero-copy async stream pipe with backpressure."""
        try:
            while True:
                data = await reader.read(32 * 1024)
                if not data:
                    break
                writer.write(data)
                await writer.drain()

                chunk_len = len(data)
                if is_inbound:
                    session.bytes_in += chunk_len
                else:
                    session.bytes_out += chunk_len

                # Update node usage
                node = self.node_manager.get_node(session.assigned_node_id)
                if node:
                    node.bytes_transferred += chunk_len

        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug(f"Piping exception: {e}")


# Singleton instance
session_proxy = SessionProxy()

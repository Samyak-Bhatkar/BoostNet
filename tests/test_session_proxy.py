"""Test 5: SOCKS5 Hybrid Session Proxy, QUIC Rejection & Domain Affinity.

Verifies:
1. SOCKS5 UDP ASSOCIATE (0x03) rejection with 0x07 (Command not supported) for QUIC-to-TCP auto-fallback.
2. Routing intelligence: Stateless CDN striping vs Sticky Host domain affinity.
3. End-to-end TCP CONNECT forwarding through the upstream virtual node proxy.
"""

import asyncio
import socket
import struct
import pytest

from backend.config import MOCK_CDN_PORT, PROXY_HOST, PROXY_PORT
from backend.engine.session_proxy import session_proxy


@pytest.mark.asyncio
async def test_session_proxy_quic_and_routing(active_cluster):
    # Ensure session proxy is running
    await session_proxy.stop()
    await session_proxy.start()

    try:
        # --- Part 1: SOCKS5 QUIC-to-TCP Auto-Fallback ---
        reader, writer = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)

        # 1. Greeting
        writer.write(b"\x05\x01\x00")
        await writer.drain()
        resp = await reader.read(2)
        assert resp == b"\x05\x00", "SOCKS5 greeting failed"

        # 2. Send UDP ASSOCIATE (0x03)
        writer.write(b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

        reply = await reader.read(10)
        assert len(reply) >= 2, "Expected reply from SOCKS5 proxy"
        assert reply[0] == 0x05, "SOCKS5 version mismatch"
        assert reply[1] == 0x07, f"Expected 0x07 (Command not supported) to force TCP fallback, got {reply[1]}"

        writer.close()
        await writer.wait_closed()
        print("\n[Test 5.1 Passed] QUIC UDP ASSOCIATE correctly rejected with 0x07 (Clean TCP fallback).")

        # --- Part 2: Routing Intelligence (Stateless CDN vs Sticky Auth Host) ---
        node_cdn, route_type_cdn = session_proxy._determine_routing("r1---sn-4g5ednks.googlevideo.com")
        assert "Striped" in route_type_cdn

        node_auth1, route_type_auth1 = session_proxy._determine_routing("github.com")
        assert "Sticky" in route_type_auth1

        node_auth2, route_type_auth2 = session_proxy._determine_routing("api.github.com")
        assert node_auth1.node_id == node_auth2.node_id, "Expected domain pinning for auth host"
        print(f"\n[Test 5.2 Passed] Domain affinity verified: github.com pinned to {node_auth1.node_id}")

        # --- Part 3: End-to-End TCP CONNECT Forwarding ---
        reader2, writer2 = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)
        writer2.write(b"\x05\x01\x00")
        await writer2.drain()
        await reader2.read(2)

        # Request CONNECT to 127.0.0.1:MOCK_CDN_PORT
        host_bytes = b"127.0.0.1"
        req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + struct.pack("!H", MOCK_CDN_PORT)
        writer2.write(req)
        await writer2.drain()

        conn_resp = await reader2.read(10)
        assert conn_resp[1] == 0x00, f"Upstream CONNECT failed with code {conn_resp[1]}"

        # Send plain HTTP request over established tunnel
        http_req = b"GET /api/hashes HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
        writer2.write(http_req)
        await writer2.drain()

        http_resp = await reader2.read(1024)
        assert b"200 OK" in http_resp
        assert b"sha256_16mb" in http_resp

        writer2.close()
        await writer2.wait_closed()
        print("\n[Test 5.3 Passed] End-to-end SOCKS5 tunnel forwarding confirmed.")

    finally:
        await session_proxy.stop()

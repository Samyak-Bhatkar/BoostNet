package net.boostnet.donor

import android.net.Network
import android.util.Log
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread

/**
 * BoostNet Cellular SOCKS5 Bridge for Android.
 *
 * Lineage & Dual-Transport Architecture:
 * - Listens on local Wi-Fi interface (talks to laptop over hotspot).
 * - Explicitly binds ALL outbound sockets to cellularNetwork.bindSocket(socket),
 *   forcing 100% of proxy traffic through the phone's 4G/5G modem (TRANSPORT_CELLULAR)
 *   even while connected to Wi-Fi.
 * - Tracks exact bytes transferred to strictly enforce donor data cap.
 */
class CellularSocksBridge(
    private val localWifiNetwork: Network,
    private val cellularNetwork: Network,
    private val maxDataCapBytes: Long = 250L * 1024L * 1024L
) {
    private val tag = "CellularSocksBridge"
    private var serverSocket: ServerSocket? = null
    private val isRunning = AtomicBoolean(false)
    val totalBytesRelayed = AtomicLong(0L)

    fun start(port: Int = 1080): Int {
        isRunning.set(true)
        // Bind to local Wi-Fi interface address on port 1080
        serverSocket = ServerSocket(port, 50, InetAddress.getByName("0.0.0.0"))
        val boundPort = serverSocket!!.localPort

        thread(name = "BoostNet-SocksServer") {
            Log.i(tag, "SOCKS5 cellular bridge listening on port $boundPort")
            while (isRunning.get()) {
                try {
                    val clientSocket = serverSocket?.accept() ?: break
                    thread(name = "BoostNet-ClientWorker") {
                        handleClient(clientSocket)
                    }
                } catch (e: Exception) {
                    if (isRunning.get()) Log.e(tag, "Accept error", e)
                }
            }
        }
        return boundPort
    }

    fun stop() {
        isRunning.set(false)
        try {
            serverSocket?.close()
        } catch (ignored: Exception) {}
    }

    private fun handleClient(clientSocket: Socket) {
        var upstreamSocket: Socket? = null
        try {
            val clientIn = clientSocket.getInputStream()
            val clientOut = clientSocket.getOutputStream()

            // 1. SOCKS5 Greeting Handshake
            val ver = clientIn.read()
            if (ver != 0x05) {
                clientSocket.close()
                return
            }
            val nMethods = clientIn.read()
            val methods = ByteArray(nMethods)
            clientIn.read(methods)

            // Reply: NO_AUTH_REQUIRED (0x05, 0x00)
            clientOut.write(byteArrayOf(0x05, 0x00))
            clientOut.flush()

            // 2. Read Request
            val req = ByteArray(4)
            clientIn.read(req)
            val cmd = req[1].toInt()
            val atyp = req[3].toInt()

            if (cmd != 0x01) { // Only TCP CONNECT supported
                clientOut.write(byteArrayOf(0x05, 0x07, 0x00, 0x01, 0, 0, 0, 0, 0, 0))
                clientOut.flush()
                clientSocket.close()
                return
            }

            // Resolve target host
            val targetHost: String = when (atyp) {
                0x01 -> { // IPv4
                    val ip = ByteArray(4)
                    clientIn.read(ip)
                    InetAddress.getByAddress(ip).hostAddress ?: ""
                }
                0x03 -> { // Domain name
                    val len = clientIn.read()
                    val domainBytes = ByteArray(len)
                    clientIn.read(domainBytes)
                    String(domainBytes)
                }
                else -> {
                    clientSocket.close()
                    return
                }
            }

            val portBuf = ByteArray(2)
            clientIn.read(portBuf)
            val targetPort = ByteBuffer.wrap(portBuf).short.toInt() and 0xFFFF

            // 3. Connect to target host via CELLULAR MODEM
            // Critical: cellularNetwork.socketFactory binds socket descriptor to 4G/5G!
            upstreamSocket = cellularNetwork.socketFactory.createSocket(targetHost, targetPort)
            cellularNetwork.bindSocket(upstreamSocket)

            val upstreamIn = upstreamSocket.getInputStream()
            val upstreamOut = upstreamSocket.getOutputStream()

            // Reply SOCKS5 SUCCESS
            clientOut.write(byteArrayOf(0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0))
            clientOut.flush()

            // 4. Bidirectional stream pipe with hard data cap guard
            val t1 = thread { pipeStream(clientIn, upstreamOut) }
            val t2 = thread { pipeStream(upstreamIn, clientOut) }

            t1.join()
            t2.join()

        } catch (e: Exception) {
            Log.d(tag, "Session closed: ${e.message}")
        } finally {
            try { clientSocket.close() } catch (ignored: Exception) {}
            try { upstreamSocket?.close() } catch (ignored: Exception) {}
        }
    }

    private fun pipeStream(input: InputStream, output: OutputStream) {
        val buffer = ByteArray(16384)
        try {
            while (isRunning.get()) {
                val read = input.read(buffer)
                if (read == -1) break
                output.write(buffer, 0, read)
                output.flush()

                val used = totalBytesRelayed.addAndGet(read.toLong())
                // Enforce strict donor data cap cutoff
                if (used >= maxDataCapBytes) {
                    Log.w(tag, "Donor data cap reached ($maxDataCapBytes bytes). Terminating socket.")
                    break
                }
            }
        } catch (ignored: Exception) {}
    }
}

package net.boostnet.donor

import android.content.Context
import android.net.*
import android.net.wifi.WifiNetworkSpecifier
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.annotation.RequiresApi
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * BoostNet Zero-Config QR Code Pairing Manager for Android 10+ (API 29+).
 *
 * Flow:
 * 1. Parses boostnet://pair?ssid=...&pass=...&host=...&port=...&token=...
 * 2. Requests cellular network handle (TRANSPORT_CELLULAR).
 * 3. Joins local hotspot via WifiNetworkSpecifier WITHOUT NET_CAPABILITY_INTERNET,
 *    keeping 4G/5G mobile data active for WhatsApp, calls, and proxy sockets.
 * 4. Starts CellularSocksBridge and auto-registers with laptop daemon via HTTP POST.
 */
class QrPairingManager(private val context: Context) {
    private val tag = "QrPairingManager"

    @RequiresApi(Build.VERSION_CODES.Q)
    fun pairFromQrUri(qrUriString: String, onConnected: (nodeId: String) -> Unit) {
        val uri = Uri.parse(qrUriString)
        val ssid = uri.getQueryParameter("ssid") ?: return
        val pass = uri.getQueryParameter("pass") ?: return
        val laptopHost = uri.getQueryParameter("host") ?: return
        val laptopPort = uri.getQueryParameter("port")?.toIntOrNull() ?: 9051
        val token = uri.getQueryParameter("token") ?: return

        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

        // 1. Request Cellular Handle
        val cellReq = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()

        cm.requestNetwork(cellReq, object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(cellularNetwork: Network) {
                Log.i(tag, "Cellular 4G/5G network handle acquired.")

                // 2. Request Peer-to-Peer Wi-Fi connection
                val specifier = WifiNetworkSpecifier.Builder()
                    .setSsid(ssid)
                    .setWpa2Passphrase(pass)
                    .build()

                val wifiReq = NetworkRequest.Builder()
                    .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                    .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) // Wi-Fi is local only!
                    .setNetworkSpecifier(specifier)
                    .build()

                cm.requestNetwork(wifiReq, object : ConnectivityManager.NetworkCallback() {
                    override fun onAvailable(localWifiNetwork: Network) {
                        Log.i(tag, "Local Wi-Fi connection established to $ssid")

                        // 3. Start local SOCKS5 proxy
                        val bridge = CellularSocksBridge(localWifiNetwork, cellularNetwork)
                        val socksPort = bridge.start(1080)

                        // 4. Send auto-check-in registration to Laptop Control Plane
                        thread {
                            try {
                                val url = URL("http://$laptopHost:$laptopPort/api/v1/nodes/register")
                                val conn = (localWifiNetwork.openConnection(url) as HttpURLConnection).apply {
                                    requestMethod = "POST"
                                    doOutput = true
                                    setRequestProperty("Content-Type", "application/json")
                                    connectTimeout = 4000
                                }

                                val body = """
                                    {
                                        "token": "$token",
                                        "device_name": "${Build.MANUFACTURER} ${Build.MODEL}",
                                        "carrier": "Mobile 5G",
                                        "socks_port": $socksPort,
                                        "data_cap_mb": 250,
                                        "battery_level": 85
                                    }
                                """.trimIndent()

                                conn.outputStream.use { it.write(body.toByteArray()) }
                                val code = conn.responseCode
                                if (code == 200) {
                                    Log.i(tag, "Successfully paired with BoostNet Laptop Control Plane!")
                                    onConnected("$laptopHost:$socksPort")
                                }
                            } catch (e: Exception) {
                                Log.e(tag, "Check-in registration failed", e)
                            }
                        }
                    }
                })
            }
        })
    }
}

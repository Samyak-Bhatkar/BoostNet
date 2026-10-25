package net.boostnet.donor

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat

/**
 * BoostNet Android Foreground Service.
 *
 * Prevents OEM power-savers (Samsung/Xiaomi/Vivo) from dropping background sockets
 * by acquiring:
 * 1. PARTIAL_WAKE_LOCK (CPU stays awake)
 * 2. WIFI_MODE_FULL_HIGH_PERF (low-latency local Wi-Fi radio)
 * 3. Ongoing Notification with live throughput and battery cutoff.
 */
class BoostNetForegroundService : Service() {
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    companion object {
        const val CHANNEL_ID = "boostnet_donor_channel"
        const val NOTIFICATION_ID = 9051
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        // 1. Acquire WakeLock
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BoostNet:DonorCpuLock").apply {
            setReferenceCounted(false)
            acquire(4 * 60 * 60 * 1000L) // 4 hours max
        }

        // 2. Acquire High-Performance Wi-Fi Lock
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "BoostNet:DonorWifiLock").apply {
            setReferenceCounted(false)
            acquire()
        }

        // 3. Start Foreground
        val notification = buildNotification("BoostNet Donor Node Active", "Sharing cellular bandwidth with laptop...")
        startForeground(NOTIFICATION_ID, notification)
    }

    private fun buildNotification(title: String, text: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "BoostNet Donor Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps BoostNet cellular proxy active in the background"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        try { wakeLock?.release() } catch (ignored: Exception) {}
        try { wifiLock?.release() } catch (ignored: Exception) {}
    }
}

package com.agenda.movil

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.tasks.await

private const val launchMeetingExtra = "meeting_id"

object MeetingLaunchBus {
    private val _meetingId = MutableStateFlow<Int?>(null)
    val meetingId: StateFlow<Int?> = _meetingId.asStateFlow()

    fun publishFromIntent(intent: Intent?) {
        val extras = intent?.extras
        val meetingIdStr = extras?.getString(launchMeetingExtra) ?: extras?.get(launchMeetingExtra)?.toString()
        val meetingId = meetingIdStr?.toIntOrNull() ?: intent?.getIntExtra(launchMeetingExtra, 0) ?: 0
        if (meetingId > 0) {
            _meetingId.value = meetingId
        }
    }

    fun clear() {
        _meetingId.value = null
    }
}

object NotificationChannels {
    const val meetings = "reuniones"
    const val reminders = "recordatorios"
    const val urgent = "urgentes"

    fun ensure(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        val channels = listOf(
            NotificationChannel(meetings, "Reuniones", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Nuevas reuniones y cambios relevantes."
                enableVibration(true)
            },
            NotificationChannel(reminders, "Recordatorios", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Recordatorios previos al inicio de reuniones."
                enableVibration(true)
            },
            NotificationChannel(urgent, "Urgentes", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Cancelaciones y alertas urgentes."
                enableVibration(true)
            },
        )
        manager.createNotificationChannels(channels)
    }
}

object NotificationRegistrar {
    suspend fun sync(context: Context): String {
        val sessionStore = SessionStore(context)
        if (sessionStore.token().isNullOrBlank()) {
            val status = "Sin sesion para registrar notificaciones."
            sessionStore.savePushStatus(status)
            return status
        }
        val app = FirebaseApp.initializeApp(context)
        if (app == null) {
            val status = "Firebase no configurado en esta compilacion."
            sessionStore.savePushStatus(status)
            return status
        }
        val token = FirebaseMessaging.getInstance().token.await()
        return syncSpecificToken(context, token)
    }

    suspend fun syncSpecificToken(context: Context, token: String): String {
        val sessionStore = SessionStore(context)
        if (sessionStore.token().isNullOrBlank()) {
            val status = "Token FCM disponible pero sin sesion activa."
            sessionStore.savePushStatus(status)
            return status
        }
        MobileRepository(sessionStore).registerDeviceToken(token)
        
        val status = if (!NotificationPermissionHelper.isGranted(context)) {
            "Permiso de notificaciones denegado."
        } else {
            "Dispositivo listo para notificaciones."
        }
        
        sessionStore.savePushStatus(status)
        return status
    }
}

object NotificationPermissionHelper {
    fun isGranted(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    }
}

object MeetingNotificationCenter {
    fun showMeetingNotification(
        context: Context,
        meetingId: Int,
        title: String,
        body: String,
        channelId: String,
    ) {
        NotificationChannels.ensure(context)
        if (!NotificationPermissionHelper.isGranted(context)) return

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(launchMeetingExtra, meetingId)
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            meetingId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .build()
        NotificationManagerCompat.from(context).notify(meetingId, notification)
    }
}

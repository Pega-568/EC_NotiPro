package com.agenda.movil

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class AgendaFirebaseMessagingService : FirebaseMessagingService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        scope.launch {
            runCatching {
                NotificationRegistrar.syncSpecificToken(applicationContext, token)
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        val meetingId = data["meeting_id"]?.toIntOrNull() ?: return
        val title = data["title"] ?: "Reunion institucional"
        val body = data["body"] ?: "Tiene una actualizacion de reunion."
        val channelId = data["channel_id"] ?: NotificationChannels.meetings
        MeetingNotificationCenter.showMeetingNotification(
            applicationContext,
            meetingId = meetingId,
            title = title,
            body = body,
            channelId = channelId,
        )
    }
}

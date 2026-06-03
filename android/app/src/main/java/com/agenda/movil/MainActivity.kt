package com.agenda.movil

import android.app.Application
import android.content.Context
import android.content.Context.MODE_PRIVATE
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query as RoomQuery
import androidx.room.Room
import androidx.room.RoomDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.google.gson.JsonParseException
import com.google.gson.JsonSyntaxException
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import okhttp3.Interceptor
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query as QueryParam
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private val ecuBlue = Color(0xFF003091)
private val ecuCyan = Color(0xFF48C9E3)
private val ecuAccent = Color(0xFF0057FF)
private val ecuWhite = Color(0xFFFFFFFF)
private val ecuGray = Color(0xFFF3F3F3)
private val ecuMidGray = Color(0xFFC0C0C0)
private val ecuDarkGray = Color(0xFF4D4D4D)
private val danger = Color(0xFFB42318)
private val success = Color(0xFF067647)
private val warning = Color(0xFFB54708)
private val localeEc = Locale("es", "EC")
private val dateLabel = DateTimeFormatter.ofPattern("dd/MM/yyyy", localeEc)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        NotificationChannels.ensure(this)
        MeetingLaunchBus.publishFromIntent(intent)
        val sessionStore = SessionStore(this)
        setContent {
            MaterialTheme(
                colorScheme = MaterialTheme.colorScheme.copy(
                    primary = ecuBlue,
                    secondary = ecuAccent,
                    tertiary = ecuCyan,
                    background = ecuGray,
                    surface = ecuWhite,
                    onPrimary = ecuWhite,
                    onSurface = ecuDarkGray,
                    onBackground = ecuDarkGray,
                ),
                typography = MaterialTheme.typography.copy(
                    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 28.sp),
                    headlineSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 22.sp),
                    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 19.sp),
                    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 16.sp),
                    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 15.sp),
                    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 14.sp),
                    bodySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 12.sp),
                )
            ) {
                val vm: CorporateAppViewModel = viewModel(
                    factory = CorporateAppViewModelFactory(application, sessionStore)
                )
                CorporateApp(vm)
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        MeetingLaunchBus.publishFromIntent(intent)
    }
}

internal class SessionStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("agenda_mobile", MODE_PRIVATE)

    fun baseUrl(): String = prefs.getString("base_url", "http://192.168.0.136:8000") ?: "http://192.168.0.136:8000"
    fun saveBaseUrl(value: String) {
        prefs.edit().putString("base_url", value.trim().removeSuffix("/")).apply()
    }
    fun token(): String? = prefs.getString("access_token", null)
    fun saveToken(value: String) {
        prefs.edit().putString("access_token", value).apply()
    }
    fun clearToken() {
        prefs.edit().remove("access_token").apply()
    }
    fun pushStatus(): String? = prefs.getString("push_status", null)
    fun savePushStatus(value: String) {
        prefs.edit().putString("push_status", value).apply()
    }
    fun lastSync(): String? = prefs.getString("last_sync", null)
    fun saveLastSync(value: String) {
        prefs.edit().putString("last_sync", value).apply()
    }
}

@Entity(tableName = "meetings")
data class MeetingEntity(
    @PrimaryKey val id: Int,
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val horaInicio: String,
    val horaFin: String,
    val estado: String,
    val prioridad: String,
    val zonaNombre: String,
    val zonaUbicacion: String,
    val creadorNombre: String,
    val miRespuesta: String,
    val miRazonRechazo: String?,
    val participantesResumen: String,
    val updatedAt: String,
)

@Entity(tableName = "meeting_requests")
data class RequestEntity(
    @PrimaryKey val localId: String,
    val serverId: Int?,
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val horaInicio: String,
    val horaFin: String,
    val estado: String,
    val prioridad: String,
    val zonaId: Int?,
    val zonaNombre: String,
    val participantes: String,
    val isDraft: Boolean,
    val pendingSync: Boolean,
    val updatedAt: String,
)

@Dao
interface MobileDao {
    @RoomQuery("SELECT * FROM meetings ORDER BY fecha, horaInicio")
    suspend fun meetings(): List<MeetingEntity>

    @RoomQuery("SELECT * FROM meetings WHERE id = :id LIMIT 1")
    suspend fun meeting(id: Int): MeetingEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertMeetings(items: List<MeetingEntity>)

    @RoomQuery("SELECT * FROM meeting_requests ORDER BY updatedAt DESC")
    suspend fun requests(): List<RequestEntity>

    @RoomQuery("SELECT * FROM meeting_requests WHERE localId = :id LIMIT 1")
    suspend fun request(id: String): RequestEntity?

    @RoomQuery("SELECT * FROM meeting_requests WHERE pendingSync = 1 ORDER BY updatedAt")
    suspend fun pendingRequests(): List<RequestEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRequests(items: List<RequestEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRequest(item: RequestEntity)
}

@Database(entities = [MeetingEntity::class, RequestEntity::class], version = 1, exportSchema = false)
abstract class MobileDatabase : RoomDatabase() {
    abstract fun dao(): MobileDao

    companion object {
        @Volatile private var instance: MobileDatabase? = null
        fun get(context: Context): MobileDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    MobileDatabase::class.java,
                    "ec_notipro_mobile.db",
                ).build().also { instance = it }
            }
    }
}

internal data class AreaDto(val id: Int, val nombre: String)
internal data class ZoneDto(val id: Int, val nombre: String, val ubicacion: String = "", val capacidad: Int? = null)
internal data class CreatorDto(val id: Int, val nombre: String)
internal data class UserDto(val id: Int, val nombre: String, val correo: String, val estado: String = "Activo", val role: String = "", val area: AreaDto = AreaDto(0, "-"))
internal data class ParticipantDto(val usuario_id: Int, val nombre: String, val correo: String = "", val estado_respuesta: String = "Pendiente", val razon_rechazo: String? = null)
internal data class ResponseSummaryDto(val aceptadas: Int = 0, val rechazadas: Int = 0, val pendientes: Int = 0)
internal data class MeetingDto(
    val id: Int,
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val hora_inicio: String,
    val hora_fin: String,
    val estado: String,
    val estado_visual: String? = null,
    val prioridad: String = "Media",
    val zona: ZoneDto = ZoneDto(0, "-"),
    val creador: CreatorDto = CreatorDto(0, "-"),
    val mi_respuesta: String? = "Pendiente",
    val mi_razon_rechazo: String? = null,
    val resumen_respuestas: ResponseSummaryDto = ResponseSummaryDto(),
    val participantes: List<ParticipantDto> = emptyList(),
)
internal data class MeetingRequestDto(
    val id: Int,
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val hora_inicio: String,
    val hora_fin: String,
    val estado: String,
    val prioridad: String = "Media",
    val zona: ZoneDto = ZoneDto(0, "-"),
    val participantes: List<ParticipantDto> = emptyList(),
)
internal data class LoginRequest(val correo: String, val password: String)
internal data class LoginResponse(val access_token: String, val token_type: String, val expires_in_minutes: Int, val user: UserDto)
internal data class MeResponse(val user: UserDto)
internal data class MeetingsResponse(val items: List<MeetingDto> = emptyList())
internal data class RequestsResponse(val items: List<MeetingRequestDto> = emptyList())
internal data class DeviceTokenRequest(val token: String, val app_version: String, val debug_ui: Boolean)
internal data class RejectRequest(val razon: String)
internal data class AvailabilityResponse(val zonas: List<ZoneDto> = emptyList(), val usuarios: List<UserDto> = emptyList())
internal data class PolicyResponse(val offline_enabled: Boolean = true, val corporate_network_required: Boolean = true)
internal data class SyncResponse(val reuniones: List<MeetingDto> = emptyList(), val solicitudes: List<MeetingRequestDto> = emptyList(), val server_time: String? = null)
internal data class HealthResponse(val status: String = "", val database: String = "")
internal data class CreateRequestBody(
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val hora_inicio: String,
    val hora_fin: String,
    val zona_id: Int,
    val participant_ids: List<Int>,
    val prioridad: String,
)

private interface MobileApi {
    @GET("/health")
    suspend fun health(): HealthResponse

    @POST("/api/mobile/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("/api/mobile/auth/me")
    suspend fun me(): MeResponse

    @POST("/api/mobile/auth/logout")
    suspend fun logout(): Map<String, String>

    @GET("/api/mobile/reuniones")
    suspend fun meetings(): MeetingsResponse

    @GET("/api/mobile/reuniones/{id}")
    suspend fun meetingDetail(@Path("id") id: Int): MeetingDto

    @POST("/api/mobile/reuniones/{id}/aceptar")
    suspend fun accept(@Path("id") id: Int): MeetingDto

    @POST("/api/mobile/reuniones/{id}/rechazar")
    suspend fun reject(@Path("id") id: Int, @Body request: RejectRequest): MeetingDto

    @GET("/api/mobile/sync")
    suspend fun sync(): SyncResponse

    @GET("/api/mobile/policy")
    suspend fun policy(): PolicyResponse

    @GET("/api/mobile/availability")
    suspend fun availability(@QueryParam("fecha") fecha: String, @QueryParam("hora_inicio") inicio: String, @QueryParam("hora_fin") fin: String): AvailabilityResponse

    @GET("/api/mobile/areas")
    suspend fun areas(): List<AreaDto>

    @GET("/api/mobile/zonas")
    suspend fun zonas(): List<ZoneDto>

    @GET("/api/mobile/usuarios/buscar")
    suspend fun buscarUsuarios(@QueryParam("q") q: String, @QueryParam("area_id") areaId: Int? = null): List<UserDto>

    @GET("/api/mobile/solicitudes")
    suspend fun solicitudes(): RequestsResponse

    @POST("/api/mobile/solicitudes")
    suspend fun crearSolicitud(@Body request: CreateRequestBody): MeetingRequestDto

    @GET("/api/mobile/solicitudes/{id}")
    suspend fun solicitudDetalle(@Path("id") id: Int): MeetingRequestDto

    @POST("/api/mobile/solicitudes/{id}/cancelar")
    suspend fun cancelarSolicitud(@Path("id") id: Int): MeetingRequestDto

    @POST("/api/mobile/device-token")
    suspend fun registerDeviceToken(@Body request: DeviceTokenRequest): Map<String, String>
}

private class UnauthorizedException : RuntimeException()
private class FriendlyException(
    override val message: String,
    val technical: String? = null,
    val backendStillConnected: Boolean = false,
) : RuntimeException(message)

internal class MobileRepository(private val sessionStore: SessionStore) {
    private fun api(baseUrl: String = sessionStore.baseUrl()): MobileApi {
        val authInterceptor = Interceptor { chain ->
            val request = chain.request().newBuilder()
            sessionStore.token()?.let { request.addHeader("Authorization", "Bearer $it") }
            chain.proceed(request.build())
        }
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG_UI) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .build()
        return Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .addConverterFactory(GsonConverterFactory.create())
            .client(client)
            .build()
            .create(MobileApi::class.java)
    }

    suspend fun isBackendHealthy(baseUrl: String = sessionStore.baseUrl()): Boolean {
        return try {
            val response = api(baseUrl).health()
            response.status == "ok" && response.database == "ok"
        } catch (_: IllegalArgumentException) {
            false
        } catch (_: UnknownHostException) {
            false
        } catch (_: ConnectException) {
            false
        } catch (_: SocketTimeoutException) {
            false
        } catch (_: IOException) {
            false
        } catch (_: HttpException) {
            false
        } catch (_: JsonParseException) {
            false
        } catch (_: Exception) {
            false
        }
    }

    suspend fun login(correo: String, password: String): UserDto {
        val response = api().login(LoginRequest(correo.trim(), password))
        sessionStore.saveToken(response.access_token)
        return response.user
    }
    suspend fun me(): UserDto = handle { api().me().user }
    suspend fun logout() { runCatching { handle { api().logout() } }; sessionStore.clearToken() }
    suspend fun meetings(): List<MeetingDto> = handle { api().meetings().items }
    suspend fun meetingDetail(id: Int): MeetingDto = handle { api().meetingDetail(id) }
    suspend fun accept(id: Int): MeetingDto = handle { api().accept(id) }
    suspend fun reject(id: Int, reason: String): MeetingDto = handle { api().reject(id, RejectRequest(reason)) }
    suspend fun sync(): SyncResponse = handle { api().sync() }
    suspend fun policy(): PolicyResponse = handle { api().policy() }
    suspend fun zones(): List<ZoneDto> = handle { api().zonas() }
    suspend fun users(query: String): List<UserDto> = handle { api().buscarUsuarios(query) }
    suspend fun requests(): List<MeetingRequestDto> = handle { api().solicitudes().items }
    suspend fun createRequest(body: CreateRequestBody): MeetingRequestDto = handle { api().crearSolicitud(body) }
    suspend fun cancelRequest(id: Int): MeetingRequestDto = handle { api().cancelarSolicitud(id) }
    suspend fun registerDeviceToken(token: String) {
        handle {
            api().registerDeviceToken(DeviceTokenRequest(token, BuildConfig.VERSION_NAME, BuildConfig.DEBUG_UI))
        }
    }

    private suspend fun <T> handle(block: suspend () -> T): T {
        try {
            return block()
        } catch (exc: HttpException) {
            if (exc.code() == 401) {
                sessionStore.clearToken()
                throw UnauthorizedException()
            }
            val message = when (exc.code()) {
                403 -> "No tiene permiso para realizar esta accion."
                404 -> "Backend conectado, pero sincronizacion no disponible."
                409 -> "Existe un conflicto con la agenda."
                422 -> "Credenciales invalidas."
                else -> "El backend corporativo no respondio correctamente."
            }
            throw FriendlyException(message, "HTTP ${exc.code()} ${exc.message()}", backendStillConnected = exc.code() == 404)
        } catch (exc: UnauthorizedException) {
            throw exc
        } catch (exc: IllegalArgumentException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: UnknownHostException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: ConnectException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: SocketTimeoutException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: IOException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: JsonParseException) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        } catch (exc: Exception) {
            throw FriendlyException("No se pudo conectar con el servidor.", exc.message)
        }
    }
}

private enum class Screen {
    LOGIN,
    SERVER_CONFIG,
    DASHBOARD,
    MEETINGS,
    MEETING_DETAIL,
    RESPOND,
    REQUESTS,
    REQUEST_DETAIL,
    CREATE_GENERAL,
    CREATE_TIME,
    CREATE_ROOM,
    CREATE_PARTICIPANTS,
    CREATE_SUMMARY,
    OFFLINE_DRAFT,
    NO_CONNECTION,
    SYNCING,
    EMPTY,
    SESSION_EXPIRED,
}

private data class RequestDraft(
    val titulo: String = "",
    val motivo: String = "",
    val prioridad: String = "Media",
    val fecha: String = LocalDate.now().plusDays(1).toString(),
    val horaInicio: String = "09:00",
    val horaFin: String = "10:00",
    val zonaId: Int? = null,
    val zonaNombre: String = "",
    val participantes: List<UserDto> = emptyList(),
)

private data class AppUiState(
    val screen: Screen = Screen.LOGIN,
    val currentUser: UserDto? = null,
    val baseUrl: String = "",
    val meetings: List<MeetingEntity> = emptyList(),
    val requests: List<RequestEntity> = emptyList(),
    val selectedMeeting: MeetingEntity? = null,
    val selectedRequest: RequestEntity? = null,
    val zones: List<ZoneDto> = emptyList(),
    val users: List<UserDto> = emptyList(),
    val draft: RequestDraft = RequestDraft(),
    val isLoading: Boolean = false,
    val isOnline: Boolean = false,
    val isCorporateApiAvailable: Boolean = false,
    val lastSync: String? = null,
    val message: String? = null,
    val technicalMessage: String? = null,
    val pushStatus: String? = null,
)

private class CorporateAppViewModel(
    application: Application,
    private val sessionStore: SessionStore,
) : AndroidViewModel(application) {
    private val dao = MobileDatabase.get(application).dao()
    private val repository = MobileRepository(sessionStore)
    private val appContext = application.applicationContext
    private val _uiState = MutableStateFlow(
        AppUiState(
            baseUrl = sessionStore.baseUrl(),
            isOnline = isNetworkAvailable(appContext),
            lastSync = sessionStore.lastSync(),
            pushStatus = sessionStore.pushStatus(),
        )
    )
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            loadCache()
            if (!sessionStore.token().isNullOrBlank()) refreshSession()
        }
    }

    fun navigate(screen: Screen) {
        _uiState.value = _uiState.value.copy(screen = screen, message = null, technicalMessage = null)
    }

    fun updateBaseUrl(value: String) {
        _uiState.value = _uiState.value.copy(baseUrl = value)
    }

    fun saveBaseUrl(value: String) {
        val normalizedUrl = try {
            normalizeServerUrl(value)
        } catch (exc: IllegalArgumentException) {
            _uiState.value = _uiState.value.copy(message = exc.message, technicalMessage = null)
            return
        }
        viewModelScope.launch {
            val online = isNetworkAvailable(appContext)
            val healthy = online && repository.isBackendHealthy(normalizedUrl)
            if (healthy) {
                sessionStore.saveBaseUrl(normalizedUrl)
            }
            _uiState.value = _uiState.value.copy(
                baseUrl = if (healthy) sessionStore.baseUrl() else normalizedUrl,
                isOnline = online,
                isCorporateApiAvailable = healthy,
                message = if (healthy) "Servidor actualizado" else "No se pudo conectar con el servidor. Verifique la URL o la red.",
            )
        }
    }

    fun login(correo: String, password: String) {
        viewModelScope.launch {
            Log.d("EC_NOTIPRO_LOGIN", "login start baseUrl=${sessionStore.baseUrl()}")
            _uiState.value = _uiState.value.copy(isLoading = true, technicalMessage = null)
            try {
                require(correo.isNotBlank()) { "Ingrese su correo corporativo." }
                require(password.isNotBlank()) { "Ingrese su contrasena." }
                val user = repository.login(correo, password)
                Log.d("EC_NOTIPRO_LOGIN", "login ok user=${user.correo}")

                Log.d("EC_NOTIPRO_LOGIN", "loadCache start")
                val cacheLoaded = runCatching { loadCache() }
                    .onSuccess { Log.d("EC_NOTIPRO_LOGIN", "loadCache ok") }
                    .onFailure { Log.e("EC_NOTIPRO_LOGIN", "loadCache failed", it) }
                    .isSuccess

                val backendHealthy = isNetworkAvailable(appContext) && repository.isBackendHealthy()
                Log.d("EC_NOTIPRO_LOGIN", "navigate dashboard backendHealthy=$backendHealthy cacheLoaded=$cacheLoaded")
                _uiState.value = _uiState.value.copy(
                    currentUser = user,
                    screen = Screen.DASHBOARD,
                    isOnline = isNetworkAvailable(appContext),
                    isCorporateApiAvailable = backendHealthy,
                    message = if (cacheLoaded) {
                        "Sesion iniciada. Sincronizacion movil pendiente."
                    } else {
                        "Sesion iniciada. Cache local pendiente."
                    },
                    technicalMessage = null,
                )
            } catch (exc: HttpException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                val message = if (exc.code() == 401 || exc.code() == 403) {
                    "Credenciales invalidas."
                } else {
                    "Login fallo: HTTP ${exc.code()}"
                }
                _uiState.value = _uiState.value.copy(message = message, technicalMessage = "HTTP ${exc.code()} ${exc.message()}")
            } catch (exc: ConnectException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "No se pudo conectar con el servidor.", technicalMessage = exc.stackTraceToString())
            } catch (exc: UnknownHostException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "No se pudo conectar con el servidor.", technicalMessage = exc.stackTraceToString())
            } catch (exc: SocketTimeoutException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "No se pudo conectar con el servidor.", technicalMessage = exc.stackTraceToString())
            } catch (exc: IOException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "No se pudo conectar con el servidor.", technicalMessage = exc.stackTraceToString())
            } catch (exc: JsonSyntaxException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "Respuesta de login incompatible.", technicalMessage = exc.stackTraceToString())
            } catch (exc: JsonParseException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = "Respuesta de login incompatible.", technicalMessage = exc.stackTraceToString())
            } catch (exc: FriendlyException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = exc.message, technicalMessage = exc.technical)
            } catch (exc: IllegalArgumentException) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                _uiState.value = _uiState.value.copy(message = exc.message, technicalMessage = exc.stackTraceToString())
            } catch (exc: Exception) {
                Log.e("EC_NOTIPRO_LOGIN", "login failed", exc)
                val message = if (BuildConfig.DEBUG_UI) {
                    "Error interno login: ${exc::class.java.simpleName}"
                } else {
                    "No se pudo conectar con el servidor."
                }
                _uiState.value = _uiState.value.copy(message = message, technicalMessage = exc.stackTraceToString())
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false, isOnline = isNetworkAvailable(appContext))
            }
        }
    }

    fun enterOfflineMode() {
        viewModelScope.launch {
            loadCache()
            _uiState.value = _uiState.value.copy(
                currentUser = UserDto(0, "Consulta offline", "offline@ecuamatriz.local", role = "Offline"),
                screen = Screen.DASHBOARD,
                isOnline = isNetworkAvailable(appContext),
                isCorporateApiAvailable = false,
                message = "Modo offline activo. No se enviaran solicitudes oficiales.",
            )
        }
    }

    fun refreshSession() {
        launchSafe {
            val user = repository.me()
            _uiState.value = _uiState.value.copy(currentUser = user)
            syncNow()
        }
    }

    fun syncNow() {
        launchSafe(showSync = true) {
            if (!isNetworkAvailable(appContext)) {
                loadCache()
                _uiState.value = _uiState.value.copy(screen = Screen.NO_CONNECTION, isOnline = false, isCorporateApiAvailable = false)
                return@launchSafe
            }
            if (!repository.isBackendHealthy()) {
                loadCache()
                _uiState.value = _uiState.value.copy(
                    screen = _uiState.value.screen.takeUnless { it == Screen.SYNCING } ?: Screen.DASHBOARD,
                    isOnline = true,
                    isCorporateApiAvailable = false,
                    message = "No se pudo conectar con el servidor. Verifique la URL o la red.",
                )
                return@launchSafe
            }

            _uiState.value = _uiState.value.copy(isOnline = true, isCorporateApiAvailable = true)
            runCatching { repository.sync() }
                .onSuccess { sync ->
                    dao.upsertMeetings(sync.reuniones.map { it.toEntity() })
                    dao.upsertRequests(sync.solicitudes.map { it.toEntity() })
                    val now = LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm"))
                    sessionStore.saveLastSync(now)
                    loadCache()
                    _uiState.value = _uiState.value.copy(
                        screen = Screen.DASHBOARD,
                        isOnline = true,
                        isCorporateApiAvailable = true,
                        lastSync = now,
                        message = "Sincronizacion completada.",
                    )
                }
                .onFailure { exc ->
                    loadCache()
                    _uiState.value = _uiState.value.copy(
                        screen = Screen.DASHBOARD,
                        isOnline = true,
                        isCorporateApiAvailable = true,
                        message = "Sincronizacion pendiente / funcion no disponible.",
                        technicalMessage = when (exc) {
                            is FriendlyException -> exc.technical
                            else -> exc.message
                        },
                    )
                }
        }
    }

    fun openMeeting(item: MeetingEntity) {
        _uiState.value = _uiState.value.copy(selectedMeeting = item, screen = Screen.MEETING_DETAIL)
    }

    fun openMeetingFromPush(id: Int) {
        viewModelScope.launch {
            dao.meeting(id)?.let { openMeeting(it) }
            MeetingLaunchBus.clear()
        }
    }

    fun openRespond() {
        _uiState.value = _uiState.value.copy(screen = Screen.RESPOND)
    }

    fun respondMeeting(accept: Boolean, reason: String = "") {
        val meeting = _uiState.value.selectedMeeting ?: return
        launchSafe {
            if (!isNetworkAvailable(appContext)) {
                _uiState.value = _uiState.value.copy(screen = Screen.NO_CONNECTION, message = "La respuesta oficial requiere red corporativa.")
                return@launchSafe
            }
            val updated = if (accept) repository.accept(meeting.id) else repository.reject(meeting.id, reason)
            dao.upsertMeetings(listOf(updated.toEntity()))
            loadCache()
            _uiState.value = _uiState.value.copy(selectedMeeting = updated.toEntity(), screen = Screen.MEETING_DETAIL)
        }
    }

    fun openRequest(item: RequestEntity) {
        _uiState.value = _uiState.value.copy(selectedRequest = item, screen = Screen.REQUEST_DETAIL)
    }

    fun startRequest() {
        _uiState.value = _uiState.value.copy(draft = RequestDraft(), screen = Screen.CREATE_GENERAL)
    }

    fun updateDraft(change: (RequestDraft) -> RequestDraft) {
        _uiState.value = _uiState.value.copy(draft = change(_uiState.value.draft))
    }

    fun loadZones() {
        launchSafe {
            val zones = if (isNetworkAvailable(appContext)) repository.zones() else emptyList()
            _uiState.value = _uiState.value.copy(zones = zones.ifEmpty { demoZones() })
        }
    }

    fun searchUsers(query: String) {
        launchSafe {
            val users = if (query.isBlank()) emptyList() else repository.users(query)
            _uiState.value = _uiState.value.copy(users = users.ifEmpty { demoUsers().filter { it.nombre.contains(query, ignoreCase = true) } })
        }
    }

    fun saveDraftOffline() {
        viewModelScope.launch {
            val draft = _uiState.value.draft
            val entity = draft.toEntity(isDraft = true, pendingSync = true)
            dao.upsertRequest(entity)
            loadCache()
            _uiState.value = _uiState.value.copy(screen = Screen.OFFLINE_DRAFT, selectedRequest = entity, message = "Borrador guardado en este dispositivo.")
        }
    }

    fun submitRequest() {
        launchSafe {
            val draft = _uiState.value.draft
            if (!isNetworkAvailable(appContext) || !_uiState.value.isCorporateApiAvailable) {
                saveDraftOffline()
                return@launchSafe
            }
            val zoneId = draft.zonaId ?: throw IllegalArgumentException("Seleccione una sala.")
            val created = repository.createRequest(
                CreateRequestBody(
                    titulo = draft.titulo,
                    motivo = draft.motivo,
                    fecha = draft.fecha,
                    hora_inicio = draft.horaInicio,
                    hora_fin = draft.horaFin,
                    zona_id = zoneId,
                    participant_ids = draft.participantes.map { it.id },
                    prioridad = draft.prioridad,
                )
            )
            dao.upsertRequests(listOf(created.toEntity()))
            loadCache()
            _uiState.value = _uiState.value.copy(screen = Screen.REQUESTS, message = "Solicitud enviada a Secretaria.")
        }
    }

    fun cancelRequest(item: RequestEntity) {
        launchSafe {
            val serverId = item.serverId ?: throw IllegalArgumentException("Solo puede cancelar solicitudes ya sincronizadas.")
            val updated = repository.cancelRequest(serverId)
            dao.upsertRequests(listOf(updated.toEntity()))
            loadCache()
            _uiState.value = _uiState.value.copy(screen = Screen.REQUEST_DETAIL, selectedRequest = updated.toEntity())
        }
    }

    fun logout() {
        viewModelScope.launch {
            repository.logout()
            _uiState.value = AppUiState(baseUrl = sessionStore.baseUrl(), screen = Screen.LOGIN)
        }
    }

    fun setPushStatus(status: String) {
        _uiState.value = _uiState.value.copy(pushStatus = status)
    }

    private suspend fun loadCache() {
        val meetings = withContext(Dispatchers.IO) { dao.meetings() }.ifEmpty { demoMeetings() }
        val requests = withContext(Dispatchers.IO) { dao.requests() }.ifEmpty { demoRequests() }
        _uiState.value = _uiState.value.copy(meetings = meetings, requests = requests)
    }

    private fun launchSafe(showSync: Boolean = false, block: suspend () -> Unit) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, screen = if (showSync) Screen.SYNCING else _uiState.value.screen)
            try {
                block()
            } catch (exc: UnauthorizedException) {
                _uiState.value = _uiState.value.copy(screen = Screen.SESSION_EXPIRED, currentUser = null)
            } catch (exc: FriendlyException) {
                loadCache()
                _uiState.value = _uiState.value.copy(
                    message = exc.message,
                    technicalMessage = exc.technical,
                    isCorporateApiAvailable = if (exc.backendStillConnected) _uiState.value.isCorporateApiAvailable else false,
                )
            } catch (exc: IllegalArgumentException) {
                _uiState.value = _uiState.value.copy(message = exc.message)
            } catch (exc: Exception) {
                loadCache()
                _uiState.value = _uiState.value.copy(
                    message = "No se pudo conectar con el servidor. Verifique la URL o la red.",
                    technicalMessage = exc.message,
                    isCorporateApiAvailable = false,
                )
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false, isOnline = isNetworkAvailable(appContext))
            }
        }
    }
}

private class CorporateAppViewModelFactory(
    private val application: Application,
    private val sessionStore: SessionStore,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = CorporateAppViewModel(application, sessionStore) as T
}

@Composable
private fun CorporateApp(viewModel: CorporateAppViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        scope.launch {
            runCatching { NotificationRegistrar.sync(context) }
                .onSuccess { viewModel.setPushStatus(it) }
                .onFailure { viewModel.setPushStatus(if (granted) "No se pudo registrar FCM." else "Permiso de notificaciones denegado.") }
        }
    }
    val launchMeetingId by MeetingLaunchBus.meetingId.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.message) {
        uiState.message?.let { snackbarHostState.showSnackbar(it) }
    }
    LaunchedEffect(Unit) {
        NotificationChannels.ensure(context)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            permissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
        } else {
            runCatching { NotificationRegistrar.sync(context) }
        }
    }
    LaunchedEffect(launchMeetingId) {
        launchMeetingId?.let { viewModel.openMeetingFromPush(it) }
    }

    val showChrome = uiState.screen !in setOf(Screen.LOGIN, Screen.SESSION_EXPIRED)
    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            if (showChrome) CorporateTopBar(uiState, viewModel)
        },
        bottomBar = {
            if (showChrome) CorporateBottomBar(uiState.screen, viewModel)
        },
        floatingActionButton = {
            if (uiState.screen in setOf(Screen.DASHBOARD, Screen.REQUESTS, Screen.MEETINGS)) {
                FloatingActionButton(onClick = { viewModel.startRequest() }, containerColor = ecuBlue, contentColor = ecuWhite, shape = CircleShape) {
                    Text("+", fontSize = 24.sp, fontWeight = FontWeight.Bold)
                }
            }
        },
        containerColor = ecuGray,
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (uiState.screen) {
                Screen.LOGIN -> LoginScreen(uiState, viewModel)
                Screen.SERVER_CONFIG -> ServerConfigScreen(uiState, viewModel)
                Screen.DASHBOARD -> DashboardScreen(uiState, viewModel)
                Screen.MEETINGS -> MeetingsScreen(uiState, viewModel)
                Screen.MEETING_DETAIL -> MeetingDetailScreen(uiState, viewModel)
                Screen.RESPOND -> RespondAttendanceScreen(uiState, viewModel)
                Screen.REQUESTS -> RequestsScreen(uiState, viewModel)
                Screen.REQUEST_DETAIL -> RequestDetailScreen(uiState, viewModel)
                Screen.CREATE_GENERAL -> CreateGeneralScreen(uiState, viewModel)
                Screen.CREATE_TIME -> CreateTimeScreen(uiState, viewModel)
                Screen.CREATE_ROOM -> CreateRoomScreen(uiState, viewModel)
                Screen.CREATE_PARTICIPANTS -> CreateParticipantsScreen(uiState, viewModel)
                Screen.CREATE_SUMMARY -> CreateSummaryScreen(uiState, viewModel, offline = false)
                Screen.OFFLINE_DRAFT -> OfflineDraftScreen(uiState, viewModel)
                Screen.NO_CONNECTION -> NoConnectionScreen(uiState, viewModel)
                Screen.SYNCING -> SyncingScreen(uiState)
                Screen.EMPTY -> EmptyStateScreen("No hay informacion disponible", "Cuando existan reuniones o solicitudes apareceran aqui.", "Actualizar") { viewModel.syncNow() }
                Screen.SESSION_EXPIRED -> SessionExpiredScreen(viewModel)
            }
            if (uiState.isLoading && uiState.screen != Screen.SYNCING) {
                Box(Modifier.fillMaxSize().background(ecuWhite.copy(alpha = 0.55f)), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = ecuBlue)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CorporateTopBar(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    TopAppBar(
        title = {
            Column {
                Text("EC_NotiPro", color = ecuBlue, fontWeight = FontWeight.Bold)
                Text(
                    if (uiState.isCorporateApiAvailable) "API corporativa conectada" else "Consulta offline disponible",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (uiState.isCorporateApiAvailable) success else warning,
                )
            }
        },
        actions = {
            TextButton(onClick = { viewModel.syncNow() }) { Text("Sync", color = ecuAccent, fontWeight = FontWeight.Bold) }
        }
    )
}

@Composable
private fun CorporateBottomBar(screen: Screen, viewModel: CorporateAppViewModel) {
    NavigationBar(containerColor = ecuWhite) {
        listOf(
            Screen.DASHBOARD to "Inicio",
            Screen.MEETINGS to "Reuniones",
            Screen.REQUESTS to "Solicitudes",
            Screen.SERVER_CONFIG to "Servidor",
        ).forEach { (target, label) ->
            NavigationBarItem(
                selected = screen == target,
                onClick = { viewModel.navigate(target) },
                icon = { Text(label.first().toString(), fontWeight = FontWeight.Bold) },
                label = { Text(label) },
            )
        }
    }
}

@Composable
private fun LoginScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    var correo by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().background(ecuGray).verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        BrandMark()
        Spacer(Modifier.height(24.dp))
        CorporateCard {
            Text("Ingreso corporativo", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Text("Acceda con sus credenciales institucionales.", color = ecuDarkGray)
            OutlinedTextField(correo, { correo = it }, label = { Text("Correo") }, modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
            OutlinedTextField(password, { password = it }, label = { Text("Contrasena") }, modifier = Modifier.fillMaxWidth(), visualTransformation = PasswordVisualTransformation())
            PrimaryButton("Ingresar") { viewModel.login(correo, password) }
            OutlinedButton(onClick = { viewModel.navigate(Screen.SERVER_CONFIG) }, modifier = Modifier.fillMaxWidth()) {
                Text("Configurar servidor", color = ecuAccent)
            }
            SecondaryButton("Entrar en modo offline") { viewModel.enterOfflineMode() }
            Text("Servidor: ${uiState.baseUrl}", style = MaterialTheme.typography.bodySmall, color = ecuDarkGray)
            if (BuildConfig.DEBUG_UI && uiState.technicalMessage != null) {
                Text("Diagnostico: ${uiState.technicalMessage}", style = MaterialTheme.typography.bodySmall, color = danger)
            }
        }
    }
}

@Composable
private fun ServerConfigScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    var url by remember(uiState.baseUrl) { mutableStateOf(uiState.baseUrl) }
    ScreenColumn {
        SectionTitle("Configuracion de servidor", "Defina el backend corporativo autorizado para operar en linea.")
        CorporateCard {
            OutlinedTextField(url, { url = it }, label = { Text("URL API corporativa") }, modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
            PrimaryButton("Guardar servidor") { viewModel.saveBaseUrl(url) }
            InfoRow("Estado de red", if (uiState.isOnline) "Con conectividad" else "Sin conexion")
            InfoRow("Ultima sincronizacion", uiState.lastSync ?: "Sin sincronizar")
            InfoRow("FCM", uiState.pushStatus ?: "Pendiente de registro")
            if (BuildConfig.DEBUG_UI && uiState.technicalMessage != null) InfoRow("Diagnostico", uiState.technicalMessage)
        }
        SecondaryButton("Volver al inicio") { viewModel.navigate(if (uiState.currentUser == null) Screen.LOGIN else Screen.DASHBOARD) }
    }
}

@Composable
private fun DashboardScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val pending = uiState.meetings.count { it.miRespuesta == "Pendiente" }
    val drafts = uiState.requests.count { it.isDraft }
    ScreenColumn {
        SectionTitle("Panel operativo", "Resumen para consulta movil y gestion de solicitudes.")
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            StatCard("Reuniones", uiState.meetings.size.toString(), Modifier.weight(1f))
            StatCard("Pendientes", pending.toString(), Modifier.weight(1f))
            StatCard("Borradores", drafts.toString(), Modifier.weight(1f))
        }
        SyncBanner(uiState)
        SectionHeader("Proximas reuniones")
        if (uiState.meetings.isEmpty()) {
            EmptyInline("No hay reuniones cacheadas.")
        } else {
            uiState.meetings.take(3).forEach { MeetingCard(it) { viewModel.openMeeting(it) } }
        }
        SectionHeader("Solicitudes recientes")
        if (uiState.requests.isEmpty()) EmptyInline("No existen solicitudes.") else uiState.requests.take(2).forEach { RequestCard(it) { viewModel.openRequest(it) } }
        PrimaryButton("Crear solicitud") { viewModel.startRequest() }
    }
}

@Composable
private fun MeetingsScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    ScreenList(
        title = "Mis reuniones",
        subtitle = "Consulta disponible aun sin conexion.",
    ) {
        items(uiState.meetings) { MeetingCard(it) { viewModel.openMeeting(it) } }
    }
}

@Composable
private fun MeetingDetailScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val meeting = uiState.selectedMeeting ?: return EmptyStateScreen("Seleccione una reunion", "Abra una reunion desde el listado.", "Ir a reuniones") { viewModel.navigate(Screen.MEETINGS) }
    ScreenColumn {
        TextButton(onClick = { viewModel.navigate(Screen.MEETINGS) }) { Text("Volver", color = ecuAccent) }
        CorporateCard {
            Text(meeting.titulo, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusBadge(meeting.miRespuesta)
                StatusBadge(meeting.prioridad)
            }
            InfoRow("Fecha", friendlyDate(meeting.fecha))
            InfoRow("Horario", "${meeting.horaInicio} - ${meeting.horaFin}")
            InfoRow("Sala", "${meeting.zonaNombre} ${meeting.zonaUbicacion}".trim())
            InfoRow("Creador", meeting.creadorNombre)
            InfoRow("Motivo", meeting.motivo)
        }
        CorporateCard {
            SectionHeader("Participantes")
            Text(meeting.participantesResumen.ifBlank { "Sin participantes sincronizados." }, color = ecuDarkGray)
        }
        PrimaryButton("Responder asistencia") { viewModel.openRespond() }
    }
}

@Composable
private fun RespondAttendanceScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val meeting = uiState.selectedMeeting ?: return
    var reason by remember { mutableStateOf("") }
    ScreenColumn {
        SectionTitle("Responder asistencia", meeting.titulo)
        CorporateCard {
            InfoRow("Horario", "${friendlyDate(meeting.fecha)} ${meeting.horaInicio} - ${meeting.horaFin}")
            InfoRow("Estado actual", meeting.miRespuesta)
            Text("La respuesta oficial requiere conexion con la API corporativa.", color = ecuDarkGray)
            OutlinedTextField(reason, { reason = it }, label = { Text("Razon si rechaza") }, modifier = Modifier.fillMaxWidth(), minLines = 4)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { viewModel.respondMeeting(true) }, modifier = Modifier.weight(1f), colors = ButtonDefaults.buttonColors(containerColor = ecuBlue), shape = RoundedCornerShape(8.dp)) { Text("Aceptar") }
                OutlinedButton(onClick = { viewModel.respondMeeting(false, reason) }, modifier = Modifier.weight(1f), shape = RoundedCornerShape(8.dp)) { Text("Rechazar", color = danger) }
            }
        }
    }
}

@Composable
private fun RequestsScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    ScreenList(
        title = "Mis solicitudes",
        subtitle = if (uiState.isOnline) "Solicitudes oficiales y borradores locales." else "Modo offline: puede consultar y guardar borradores.",
        action = { PrimaryButton("Nueva solicitud") { viewModel.startRequest() } },
    ) {
        items(uiState.requests) { RequestCard(it) { viewModel.openRequest(it) } }
    }
}

@Composable
private fun RequestDetailScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val request = uiState.selectedRequest ?: return
    ScreenColumn {
        TextButton(onClick = { viewModel.navigate(Screen.REQUESTS) }) { Text("Volver", color = ecuAccent) }
        CorporateCard {
            Text(request.titulo, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusBadge(if (request.isDraft) "Borrador" else request.estado)
                if (request.pendingSync) StatusBadge("Pendiente sync")
            }
            InfoRow("Fecha", friendlyDate(request.fecha))
            InfoRow("Horario", "${request.horaInicio} - ${request.horaFin}")
            InfoRow("Sala", request.zonaNombre.ifBlank { "Sin sala seleccionada" })
            InfoRow("Participantes", request.participantes.ifBlank { "Sin participantes" })
            InfoRow("Motivo", request.motivo)
        }
        if (!request.isDraft && request.estado == "Pendiente") {
            SecondaryButton("Cancelar solicitud") { viewModel.cancelRequest(request) }
        }
    }
}

@Composable
private fun CreateGeneralScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val draft = uiState.draft
    ScreenColumn {
        StepHeader(1, "Datos generales")
        DraftTextField("Titulo", draft.titulo) { value -> viewModel.updateDraft { it.copy(titulo = value) } }
        DraftTextField("Motivo", draft.motivo, minLines = 4) { value -> viewModel.updateDraft { it.copy(motivo = value) } }
        PrioritySelector(draft.prioridad) { value -> viewModel.updateDraft { it.copy(prioridad = value) } }
        WizardActions(back = { viewModel.navigate(Screen.REQUESTS) }, next = { viewModel.navigate(Screen.CREATE_TIME) })
    }
}

@Composable
private fun CreateTimeScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val draft = uiState.draft
    ScreenColumn {
        StepHeader(2, "Fecha y hora")
        DraftTextField("Fecha AAAA-MM-DD", draft.fecha) { value -> viewModel.updateDraft { it.copy(fecha = value) } }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            Box(Modifier.weight(1f)) { DraftTextField("Inicio", draft.horaInicio) { value -> viewModel.updateDraft { it.copy(horaInicio = value) } } }
            Box(Modifier.weight(1f)) { DraftTextField("Fin", draft.horaFin) { value -> viewModel.updateDraft { it.copy(horaFin = value) } } }
        }
        WizardActions(back = { viewModel.navigate(Screen.CREATE_GENERAL) }, next = { viewModel.loadZones(); viewModel.navigate(Screen.CREATE_ROOM) })
    }
}

@Composable
private fun CreateRoomScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    val zones = uiState.zones.ifEmpty { demoZones() }
    ScreenColumn {
        StepHeader(3, "Sala")
        zones.forEach { zone ->
            SelectCard(
                title = zone.nombre,
                subtitle = zone.ubicacion.ifBlank { "Sala corporativa" },
                selected = uiState.draft.zonaId == zone.id,
            ) { viewModel.updateDraft { it.copy(zonaId = zone.id, zonaNombre = zone.nombre) } }
        }
        WizardActions(back = { viewModel.navigate(Screen.CREATE_TIME) }, next = { viewModel.navigate(Screen.CREATE_PARTICIPANTS) })
    }
}

@Composable
private fun CreateParticipantsScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    var query by remember { mutableStateOf("") }
    val selected = uiState.draft.participantes
    ScreenColumn {
        StepHeader(4, "Participantes")
        OutlinedTextField(query, { query = it; viewModel.searchUsers(it) }, label = { Text("Buscar usuario") }, modifier = Modifier.fillMaxWidth())
        if (selected.isNotEmpty()) {
            CorporateCard {
                Text("Seleccionados", fontWeight = FontWeight.Bold, color = ecuBlue)
                selected.forEach { Text(it.nombre, color = ecuDarkGray) }
            }
        }
        uiState.users.ifEmpty { demoUsers() }.forEach { user ->
            SelectCard(user.nombre, user.correo, selected.any { it.id == user.id }) {
                viewModel.updateDraft {
                    if (selected.any { selectedUser -> selectedUser.id == user.id }) it.copy(participantes = selected.filterNot { selectedUser -> selectedUser.id == user.id })
                    else it.copy(participantes = selected + user)
                }
            }
        }
        WizardActions(back = { viewModel.navigate(Screen.CREATE_ROOM) }, next = { viewModel.navigate(Screen.CREATE_SUMMARY) })
    }
}

@Composable
private fun CreateSummaryScreen(uiState: AppUiState, viewModel: CorporateAppViewModel, offline: Boolean) {
    val draft = uiState.draft
    ScreenColumn {
        StepHeader(5, if (offline) "Resumen offline" else "Resumen")
        CorporateCard {
            InfoRow("Titulo", draft.titulo.ifBlank { "Sin titulo" })
            InfoRow("Fecha", friendlyDate(draft.fecha))
            InfoRow("Horario", "${draft.horaInicio} - ${draft.horaFin}")
            InfoRow("Sala", draft.zonaNombre.ifBlank { "Sin sala" })
            InfoRow("Participantes", draft.participantes.joinToString { it.nombre }.ifBlank { "Sin participantes" })
            InfoRow("Prioridad", draft.prioridad)
            Text(
                if (uiState.isOnline) "Se enviara como solicitud oficial al backend corporativo." else "Sin conexion: solo se guardara como borrador local.",
                color = if (uiState.isOnline) success else warning,
            )
        }
        PrimaryButton(if (uiState.isOnline) "Enviar solicitud" else "Guardar borrador offline") { viewModel.submitRequest() }
        SecondaryButton("Guardar borrador") { viewModel.saveDraftOffline() }
        WizardActions(back = { viewModel.navigate(Screen.CREATE_PARTICIPANTS) }, next = null)
    }
}

@Composable
private fun OfflineDraftScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    ScreenColumn {
        SectionTitle("Borrador guardado", "La solicitud queda en Room y se sincronizara cuando la API corporativa este disponible.")
        uiState.selectedRequest?.let { RequestCard(it) { viewModel.openRequest(it) } }
        PrimaryButton("Ver mis solicitudes") { viewModel.navigate(Screen.REQUESTS) }
        SecondaryButton("Intentar sincronizar") { viewModel.syncNow() }
    }
}

@Composable
private fun NoConnectionScreen(uiState: AppUiState, viewModel: CorporateAppViewModel) {
    ScreenColumn {
        SectionTitle("Sin conexion", "Puede consultar informacion guardada y crear borradores offline.")
        SyncBanner(uiState)
        PrimaryButton("Ver reuniones guardadas") { viewModel.navigate(Screen.MEETINGS) }
        SecondaryButton("Crear borrador") { viewModel.startRequest() }
        SecondaryButton("Reintentar sincronizacion") { viewModel.syncNow() }
    }
}

@Composable
private fun SyncingScreen(uiState: AppUiState) {
    Box(Modifier.fillMaxSize().background(ecuGray), contentAlignment = Alignment.Center) {
        CorporateCard(modifier = Modifier.padding(24.dp)) {
            CircularProgressIndicator(color = ecuBlue)
            Text("Sincronizando", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Text("Validando API corporativa y actualizando datos locales.", color = ecuDarkGray, textAlign = TextAlign.Center)
            Text("Ultima sincronizacion: ${uiState.lastSync ?: "sin registro"}", style = MaterialTheme.typography.bodySmall, color = ecuDarkGray)
        }
    }
}

@Composable
private fun SessionExpiredScreen(viewModel: CorporateAppViewModel) {
    Column(Modifier.fillMaxSize().background(ecuGray).padding(20.dp), verticalArrangement = Arrangement.Center) {
        BrandMark()
        Spacer(Modifier.height(24.dp))
        CorporateCard {
            Text("Sesion expirada", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Text("Por seguridad debe ingresar nuevamente.", color = ecuDarkGray)
            PrimaryButton("Volver al login") { viewModel.logout() }
        }
    }
}

@Composable
private fun ScreenColumn(content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        content = content,
    )
}

@Composable
private fun ScreenList(
    title: String,
    subtitle: String,
    action: (@Composable () -> Unit)? = null,
    content: LazyListScope.() -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionTitle(title, subtitle)
            action?.invoke()
        }
        content()
        item {
            Spacer(Modifier.height(72.dp))
        }
    }
}

@Composable
private fun EmptyStateScreen(title: String, body: String, action: String, onAction: () -> Unit) {
    Box(Modifier.fillMaxSize().background(ecuGray).padding(24.dp), contentAlignment = Alignment.Center) {
        CorporateCard {
            Box(Modifier.size(68.dp).background(ecuCyan.copy(alpha = 0.3f), CircleShape), contentAlignment = Alignment.Center) {
                Text("i", color = ecuBlue, fontWeight = FontWeight.Bold, fontSize = 28.sp)
            }
            Text(title, style = MaterialTheme.typography.headlineSmall, color = ecuBlue, textAlign = TextAlign.Center)
            Text(body, color = ecuDarkGray, textAlign = TextAlign.Center)
            PrimaryButton(action, onAction)
        }
    }
}

@Composable
private fun CorporateCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = ecuWhite),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = BorderStroke(1.dp, ecuMidGray.copy(alpha = 0.35f)),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
private fun BrandMark() {
    Column(horizontalAlignment = Alignment.Start) {
        Box(Modifier.width(84.dp).height(8.dp).background(ecuCyan, RoundedCornerShape(8.dp)))
        Text("ECUAMATRIZ", color = ecuBlue, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp)
        Text("EC_NotiPro", color = ecuDarkGray, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun SectionTitle(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
        Text(subtitle, color = ecuDarkGray)
    }
}

@Composable
private fun SectionHeader(label: String) {
    Text(label, style = MaterialTheme.typography.titleMedium, color = ecuBlue)
}

@Composable
private fun PrimaryButton(label: String, onClick: () -> Unit) {
    Button(onClick = onClick, modifier = Modifier.fillMaxWidth().height(48.dp), colors = ButtonDefaults.buttonColors(containerColor = ecuBlue), shape = RoundedCornerShape(8.dp)) {
        Text(label, color = ecuWhite, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun SecondaryButton(label: String, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(8.dp), border = BorderStroke(1.dp, ecuAccent)) {
        Text(label, color = ecuAccent, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun WizardActions(back: () -> Unit, next: (() -> Unit)?) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = back, modifier = Modifier.weight(1f).height(48.dp), shape = RoundedCornerShape(8.dp)) { Text("Atras", color = ecuAccent) }
        if (next != null) Button(onClick = next, modifier = Modifier.weight(1f).height(48.dp), colors = ButtonDefaults.buttonColors(containerColor = ecuBlue), shape = RoundedCornerShape(8.dp)) { Text("Siguiente") }
    }
}

@Composable
private fun StepHeader(step: Int, title: String) {
    SectionTitle("Crear solicitud", "Paso $step de 5: $title")
}

@Composable
private fun DraftTextField(label: String, value: String, minLines: Int = 1, onValue: (String) -> Unit) {
    OutlinedTextField(value = value, onValueChange = onValue, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), minLines = minLines)
}

@Composable
private fun PrioritySelector(selected: String, onSelected: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        listOf("Baja", "Media", "Alta").forEach { item ->
            Button(
                onClick = { onSelected(item) },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = if (selected == item) ecuBlue else ecuWhite, contentColor = if (selected == item) ecuWhite else ecuBlue),
                border = BorderStroke(1.dp, if (selected == item) ecuBlue else ecuMidGray),
                shape = RoundedCornerShape(8.dp),
            ) { Text(item) }
        }
    }
}

@Composable
private fun SelectCard(title: String, subtitle: String, selected: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onClick() },
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = if (selected) ecuCyan.copy(alpha = 0.16f) else ecuWhite),
        border = BorderStroke(1.dp, if (selected) ecuBlue else ecuMidGray.copy(alpha = 0.5f)),
    ) {
        Row(Modifier.padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(18.dp).background(if (selected) ecuBlue else ecuWhite, CircleShape).border(1.dp, ecuBlue, CircleShape))
            Column {
                Text(title, fontWeight = FontWeight.Bold, color = ecuDarkGray)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = ecuDarkGray)
            }
        }
    }
}

@Composable
private fun MeetingCard(meeting: MeetingEntity, onClick: () -> Unit) {
    CorporateListCard(onClick) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.width(6.dp).height(76.dp).background(statusColor(meeting.miRespuesta), RoundedCornerShape(8.dp)))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(meeting.titulo, fontWeight = FontWeight.Bold, color = ecuDarkGray)
                Text("${friendlyDate(meeting.fecha)} · ${meeting.horaInicio} - ${meeting.horaFin}", color = ecuDarkGray)
                Text(meeting.zonaNombre, color = ecuDarkGray)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    StatusBadge(meeting.miRespuesta)
                    StatusBadge(meeting.prioridad)
                }
            }
        }
    }
}

@Composable
private fun RequestCard(request: RequestEntity, onClick: () -> Unit) {
    CorporateListCard(onClick) {
        Text(request.titulo, fontWeight = FontWeight.Bold, color = ecuDarkGray)
        Text("${friendlyDate(request.fecha)} · ${request.horaInicio} - ${request.horaFin}", color = ecuDarkGray)
        Text(request.zonaNombre.ifBlank { "Sala pendiente" }, color = ecuDarkGray)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusBadge(if (request.isDraft) "Borrador" else request.estado)
            if (request.pendingSync) StatusBadge("Offline")
        }
    }
}

@Composable
private fun CorporateListCard(onClick: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onClick() },
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = ecuWhite),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp), content = content)
    }
}

@Composable
private fun StatusBadge(label: String) {
    val color = statusColor(label)
    Box(Modifier.background(color.copy(alpha = 0.16f), RoundedCornerShape(100.dp)).padding(horizontal = 10.dp, vertical = 5.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = if (color == ecuCyan) ecuBlue else color, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = ecuAccent, fontWeight = FontWeight.Bold)
        Text(value, color = ecuDarkGray)
    }
    HorizontalDivider(color = ecuGray)
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier) {
    Card(modifier = modifier, shape = RoundedCornerShape(8.dp), colors = CardDefaults.cardColors(containerColor = ecuWhite)) {
        Column(Modifier.padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Text(label, style = MaterialTheme.typography.bodySmall, color = ecuDarkGray, textAlign = TextAlign.Center)
        }
    }
}

@Composable
private fun SyncBanner(uiState: AppUiState) {
    CorporateCard {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(12.dp).background(if (uiState.isCorporateApiAvailable) success else warning, CircleShape))
            Column {
                Text(if (uiState.isCorporateApiAvailable) "Backend conectado" else "Modo offline seguro", color = ecuBlue, fontWeight = FontWeight.Bold)
                Text("Sincronizacion: ${uiState.lastSync ?: "pendiente / funcion no disponible"}", style = MaterialTheme.typography.bodySmall, color = ecuDarkGray)
            }
        }
    }
}

@Composable
private fun EmptyInline(text: String) {
    CorporateCard { Text(text, color = ecuDarkGray, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
}

private fun MeetingDto.toEntity(): MeetingEntity = MeetingEntity(
    id = id,
    titulo = titulo,
    motivo = motivo,
    fecha = fecha,
    horaInicio = hora_inicio,
    horaFin = hora_fin,
    estado = estado,
    prioridad = prioridad,
    zonaNombre = zona.nombre,
    zonaUbicacion = zona.ubicacion,
    creadorNombre = creador.nombre,
    miRespuesta = mi_respuesta ?: estado_visual ?: estado,
    miRazonRechazo = mi_razon_rechazo,
    participantesResumen = participantes.joinToString { "${it.nombre} (${it.estado_respuesta})" },
    updatedAt = LocalDateTime.now().toString(),
)

private fun MeetingRequestDto.toEntity(): RequestEntity = RequestEntity(
    localId = "server-$id",
    serverId = id,
    titulo = titulo,
    motivo = motivo,
    fecha = fecha,
    horaInicio = hora_inicio,
    horaFin = hora_fin,
    estado = estado,
    prioridad = prioridad,
    zonaId = zona.id,
    zonaNombre = zona.nombre,
    participantes = participantes.joinToString { it.nombre },
    isDraft = false,
    pendingSync = false,
    updatedAt = LocalDateTime.now().toString(),
)

private fun RequestDraft.toEntity(isDraft: Boolean, pendingSync: Boolean): RequestEntity = RequestEntity(
    localId = "draft-${System.currentTimeMillis()}",
    serverId = null,
    titulo = titulo.ifBlank { "Solicitud sin titulo" },
    motivo = motivo,
    fecha = fecha,
    horaInicio = horaInicio,
    horaFin = horaFin,
    estado = if (isDraft) "Borrador" else "Pendiente",
    prioridad = prioridad,
    zonaId = zonaId,
    zonaNombre = zonaNombre,
    participantes = participantes.joinToString { it.nombre },
    isDraft = isDraft,
    pendingSync = pendingSync,
    updatedAt = LocalDateTime.now().toString(),
)

private fun statusColor(label: String): Color = when (label) {
    "Aceptada", "Aceptado", "Aprobada", "Sincronizado" -> success
    "Rechazada", "Rechazado", "Cancelada" -> danger
    "Pendiente", "Borrador", "Offline", "Pendiente sync" -> warning
    "Alta" -> ecuAccent
    else -> ecuCyan
}

private fun friendlyDate(value: String): String = runCatching { LocalDate.parse(value).format(dateLabel) }.getOrDefault(value)

private fun normalizeServerUrl(value: String): String {
    val trimmed = value.trim().trimEnd('/')
    require(trimmed.isNotBlank()) { "Ingrese la URL del servidor." }
    require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) { "La URL debe iniciar con http:// o https://." }
    try {
        trimmed.toHttpUrl()
    } catch (_: IllegalArgumentException) {
        throw IllegalArgumentException("La URL del servidor no es valida.")
    }
    return trimmed
}

private fun isNetworkAvailable(context: Context): Boolean {
    val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val network = manager.activeNetwork ?: return false
    val capabilities = manager.getNetworkCapabilities(network) ?: return false
    return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
}

private fun demoZones(): List<ZoneDto> = listOf(
    ZoneDto(1, "Sala Principal", "Piso 1", 20),
    ZoneDto(2, "Sala Contabilidad", "Piso 2", 8),
    ZoneDto(3, "Sala Ejecutiva", "Administracion", 10),
)

private fun demoUsers(): List<UserDto> = listOf(
    UserDto(3, "Usuario 1", "usuario1.contabilidad@empresa.local"),
    UserDto(4, "Usuario 2", "usuario2.contabilidad@empresa.local"),
    UserDto(5, "Usuario Mercado", "usuario1.mercado@empresa.local"),
)

private fun demoMeetings(): List<MeetingEntity> = listOf(
    MeetingEntity(1, "Revision operativa", "Seguimiento semanal de indicadores.", LocalDate.now().plusDays(1).toString(), "09:00", "10:00", "Pendiente", "Media", "Sala Principal", "Piso 1", "Secretaria", "Pendiente", null, "Usuario 1 (Pendiente), Usuario 2 (Aceptada)", LocalDateTime.now().toString()),
    MeetingEntity(2, "Comite comercial", "Alinear prioridades del area.", LocalDate.now().plusDays(2).toString(), "14:00", "15:00", "Confirmada", "Alta", "Sala Ejecutiva", "Administracion", "Admin", "Aceptada", null, "Usuario Mercado (Aceptada)", LocalDateTime.now().toString()),
)

private fun demoRequests(): List<RequestEntity> = listOf(
    RequestEntity("demo-1", 1, "Capacitacion interna", "Planificar agenda de capacitacion.", LocalDate.now().plusDays(3).toString(), "11:00", "12:00", "Pendiente", "Media", 1, "Sala Principal", "Usuario 1, Usuario 2", false, false, LocalDateTime.now().toString()),
)

package com.agenda.movil

import android.content.Context
import android.content.Context.MODE_PRIVATE
import android.os.Build
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle as JavaTextStyle
import java.util.Locale

private val ecuBlue = Color(0xFF003091)
private val ecuBlueLight = Color(0xFF0057FF)
private val ecuAccent = Color(0xFF48C9E3)
private val ecuBg = Color(0xFFF3F3F3)
private val ecuText = Color(0xFF4D4D4D)
private val ecuBorder = Color(0xFFC0C0C0)
private val pendingColor = Color(0xFFFFD166)
private val acceptedColor = Color(0xFF72D38B)
private val rejectedColor = Color(0xFFFF8A80)
private val canceledColor = Color(0xFFC0C0C0)
private val institutionalFont = FontFamily.SansSerif
private val localeEs = Locale("es", "EC")
private val isoDateFormatter = DateTimeFormatter.ISO_LOCAL_DATE
private val dayNumberFormatter = DateTimeFormatter.ofPattern("d", localeEs)
private val longDateFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy", localeEs)
private val monthTitleFormatter = DateTimeFormatter.ofPattern("MMMM yyyy", localeEs)

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
                    secondary = ecuBlueLight,
                    tertiary = ecuAccent,
                    background = ecuBg,
                    surface = Color.White,
                    onSurface = ecuText,
                    onBackground = ecuText
                ),
                typography = MaterialTheme.typography.copy(
                    headlineLarge = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp),
                    headlineSmall = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp),
                    titleLarge = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.Bold, fontSize = 20.sp),
                    titleMedium = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.Bold, fontSize = 16.sp),
                    bodyLarge = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.Normal, fontSize = 15.sp),
                    bodyMedium = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.Normal, fontSize = 14.sp),
                    bodySmall = TextStyle(fontFamily = institutionalFont, fontWeight = FontWeight.Normal, fontSize = 12.sp)
                )
            ) {
                val vm: AppViewModel = viewModel(factory = AppViewModelFactory(sessionStore))
                AppRoot(vm)
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        MeetingLaunchBus.publishFromIntent(intent)
    }
}

internal data class UserDto(
    val id: Int,
    val nombre: String,
    val correo: String,
    val estado: String,
    val role: String,
    val area: AreaDto
)

internal data class AreaDto(val id: Int, val nombre: String)
internal data class ZoneDto(val id: Int, val nombre: String, val ubicacion: String)
internal data class CreatorDto(val id: Int, val nombre: String)

internal data class ParticipantDto(
    val usuario_id: Int,
    val nombre: String,
    val correo: String,
    val estado_respuesta: String,
    val razon_rechazo: String?
)

internal data class ResponseSummaryDto(
    val aceptadas: Int = 0,
    val rechazadas: Int = 0,
    val pendientes: Int = 0,
)

internal data class MeetingDto(
    val id: Int,
    val titulo: String,
    val motivo: String,
    val fecha: String,
    val hora_inicio: String,
    val hora_fin: String,
    val estado: String,
    val estado_visual: String? = null,
    val prioridad: String,
    val zona: ZoneDto,
    val creador: CreatorDto,
    val mi_respuesta: String?,
    val mi_razon_rechazo: String?,
    val resumen_respuestas: ResponseSummaryDto = ResponseSummaryDto(),
    val participantes: List<ParticipantDto>
) {
    fun localDate(): LocalDate = LocalDate.parse(fecha, isoDateFormatter)
    fun dateLabel(): String = localDate().format(longDateFormatter)
    fun timeRange(): String = "$hora_inicio - $hora_fin"
    fun displayStatus(): String = mi_respuesta ?: estado_visual ?: estado
    fun responseSummaryLabel(): String =
        "${resumen_respuestas.aceptadas} aceptadas · ${resumen_respuestas.pendientes} pendientes"
}

internal data class MeetingsResponse(val items: List<MeetingDto>)
internal data class LoginRequest(val correo: String, val password: String)
internal data class LoginResponse(val access_token: String, val token_type: String, val expires_in_minutes: Int, val user: UserDto)
internal data class MeResponse(val user: UserDto)
internal data class RejectRequest(val razon: String)
internal data class DeviceTokenRequest(val token: String, val app_version: String, val debug_ui: Boolean)

private interface MobileApi {
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

    @POST("/api/mobile/device-token")
    suspend fun registerDeviceToken(@Body request: DeviceTokenRequest): Map<String, String>
}

private class UnauthorizedException : RuntimeException()

private class FriendlyException(
    override val message: String,
    val technicalMessage: String? = null
) : RuntimeException(message)

internal class SessionStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("agenda_mobile", MODE_PRIVATE)

    fun baseUrl(): String = prefs.getString("base_url", "http://192.168.0.139:5000") ?: "http://192.168.0.139:5000"
    fun saveBaseUrl(value: String) { prefs.edit().putString("base_url", value.trim().removeSuffix("/")).apply() }
    fun token(): String? = prefs.getString("access_token", null)
    fun saveToken(value: String) { prefs.edit().putString("access_token", value).apply() }
    fun clearToken() { prefs.edit().remove("access_token").apply() }
    fun pushStatus(): String? = prefs.getString("push_status", null)
    fun savePushStatus(value: String) { prefs.edit().putString("push_status", value).apply() }
}

internal class MobileRepository(private val sessionStore: SessionStore) {
    private fun api(): MobileApi {
        val authInterceptor = Interceptor { chain ->
            val builder = chain.request().newBuilder()
            sessionStore.token()?.let { builder.addHeader("Authorization", "Bearer $it") }
            chain.proceed(builder.build())
        }
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG_UI) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .build()

        return Retrofit.Builder()
            .baseUrl(ensureBaseUrl(sessionStore.baseUrl()))
            .addConverterFactory(GsonConverterFactory.create())
            .client(client)
            .build()
            .create(MobileApi::class.java)
    }

    private fun ensureBaseUrl(value: String): String = if (value.endsWith("/")) value else "$value/"

    suspend fun login(correo: String, password: String): UserDto {
        val response = api().login(LoginRequest(correo.trim(), password))
        sessionStore.saveToken(response.access_token)
        return response.user
    }

    suspend fun me(): UserDto = handleUnauthorized { api().me().user }
    suspend fun logout() { try { handleUnauthorized { api().logout() } } finally { sessionStore.clearToken() } }
    suspend fun meetings(): List<MeetingDto> = handleUnauthorized { api().meetings().items.sortedBy { it.localDate().toString() + it.hora_inicio } }
    suspend fun meetingDetail(id: Int): MeetingDto = handleUnauthorized { api().meetingDetail(id) }
    suspend fun accept(id: Int): MeetingDto = handleUnauthorized { api().accept(id) }
    suspend fun reject(id: Int, reason: String): MeetingDto = handleUnauthorized { api().reject(id, RejectRequest(reason)) }
    suspend fun registerDeviceToken(token: String) {
        handleUnauthorized {
            api().registerDeviceToken(
                DeviceTokenRequest(
                    token = token,
                    app_version = BuildConfig.VERSION_NAME,
                    debug_ui = BuildConfig.DEBUG_UI,
                )
            )
        }
    }

    private suspend fun <T> handleUnauthorized(block: suspend () -> T): T {
        try {
            return block()
        } catch (exc: HttpException) {
            if (exc.code() == 401) {
                sessionStore.clearToken()
                throw UnauthorizedException()
            }
            throw mapHttpException(exc)
        } catch (exc: Exception) {
            if (exc is FriendlyException) throw exc
            throw FriendlyException(
                message = "No se pudo completar la operación. Revise su conexión e intente nuevamente.",
                technicalMessage = exc.message
            )
        }
    }

    private fun mapHttpException(exc: HttpException): FriendlyException {
        val message = when (exc.code()) {
            403 -> "No tiene permiso para realizar esta acción."
            404 -> "La información solicitada ya no está disponible."
            409 -> "Existe un conflicto con la reunión seleccionada."
            422 -> "Los datos enviados no son válidos."
            else -> "Ocurrió un problema con el servidor."
        }
        return FriendlyException(message, technicalMessage = "HTTP ${exc.code()} ${exc.message()}")
    }
}

private enum class CalendarMode {
    MONTH, AGENDA
}

private enum class Screen {
    LOGIN, HOME, PENDING, CALENDAR, HISTORY, DETAIL, REJECT, PROFILE
}

private data class AppUiState(
    val currentScreen: Screen = Screen.LOGIN,
    val currentUser: UserDto? = null,
    val meetings: List<MeetingDto> = emptyList(),
    val selectedMeeting: MeetingDto? = null,
    val selectedCalendarDay: LocalDate = LocalDate.now(),
    val calendarMonth: YearMonth = YearMonth.now(),
    val calendarMode: CalendarMode = CalendarMode.MONTH,
    val baseUrl: String = "http://192.168.0.139:5000",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val lastTechnicalError: String? = null,
    val pushStatus: String? = null,
)

private class AppViewModel(private val sessionStore: SessionStore) : ViewModel() {
    private val repository = MobileRepository(sessionStore)
    private val _uiState = MutableStateFlow(
        AppUiState(
            baseUrl = sessionStore.baseUrl(),
            pushStatus = sessionStore.pushStatus(),
        )
    )
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    init {
        if (!sessionStore.token().isNullOrBlank()) refreshSession()
    }

    fun updateBaseUrl(value: String) { _uiState.value = _uiState.value.copy(baseUrl = value) }
    fun saveBaseUrl(value: String) { sessionStore.saveBaseUrl(value); _uiState.value = _uiState.value.copy(baseUrl = sessionStore.baseUrl()) }
    fun navigate(screen: Screen) { _uiState.value = _uiState.value.copy(currentScreen = screen, errorMessage = null) }
    fun previousMonth() { _uiState.value = _uiState.value.copy(calendarMonth = _uiState.value.calendarMonth.minusMonths(1)) }
    fun nextMonth() { _uiState.value = _uiState.value.copy(calendarMonth = _uiState.value.calendarMonth.plusMonths(1)) }
    fun selectCalendarDay(day: LocalDate) { _uiState.value = _uiState.value.copy(selectedCalendarDay = day) }
    fun setCalendarMode(mode: CalendarMode) { _uiState.value = _uiState.value.copy(calendarMode = mode) }
    fun setPushStatus(status: String) { _uiState.value = _uiState.value.copy(pushStatus = status) }

    fun login(correo: String, password: String) {
        launchSafe {
            require(correo.isNotBlank()) { "Ingrese su correo institucional." }
            require(password.isNotBlank()) { "Ingrese su contraseña." }
            val user = repository.login(correo, password)
            _uiState.value = _uiState.value.copy(currentUser = user, currentScreen = Screen.HOME, errorMessage = null)
            loadMeetings()
        }
    }

    fun refreshSession() {
        launchSafe {
            val user = repository.me()
            _uiState.value = _uiState.value.copy(currentUser = user, currentScreen = Screen.HOME)
            loadMeetings()
        }
    }

    fun loadMeetings() {
        launchSafe {
            val meetings = repository.meetings()
            _uiState.value = _uiState.value.copy(
                meetings = meetings,
                currentScreen = if (_uiState.value.currentScreen == Screen.LOGIN) Screen.HOME else _uiState.value.currentScreen,
                selectedCalendarDay = LocalDate.now()
            )
        }
    }

    fun openMeeting(id: Int) {
        launchSafe {
            val detail = repository.meetingDetail(id)
            _uiState.value = _uiState.value.copy(selectedMeeting = detail, currentScreen = Screen.DETAIL)
        }
    }

    fun acceptMeeting(id: Int) {
        launchSafe {
            val detail = repository.accept(id)
            replaceMeeting(detail)
            _uiState.value = _uiState.value.copy(selectedMeeting = detail, currentScreen = Screen.DETAIL)
        }
    }

    fun openRejectScreen() { _uiState.value = _uiState.value.copy(currentScreen = Screen.REJECT, errorMessage = null) }

    fun rejectMeeting(id: Int, reason: String) {
        launchSafe {
            require(reason.isNotBlank()) { "Debe indicar una razón para rechazar la reunión." }
            val detail = repository.reject(id, reason)
            replaceMeeting(detail)
            _uiState.value = _uiState.value.copy(selectedMeeting = detail, currentScreen = Screen.DETAIL)
        }
    }

    fun backToPrimary() {
        val meeting = _uiState.value.selectedMeeting
        val target = when {
            _uiState.value.currentScreen == Screen.PROFILE -> Screen.HOME
            meeting?.mi_respuesta == "Pendiente" -> Screen.PENDING
            else -> Screen.HISTORY
        }
        _uiState.value = _uiState.value.copy(currentScreen = target, errorMessage = null)
    }

    fun logout() {
        launchSafe {
            repository.logout()
            _uiState.value = AppUiState(baseUrl = sessionStore.baseUrl(), pushStatus = sessionStore.pushStatus())
        }
    }

    private fun replaceMeeting(detail: MeetingDto) {
        val updated = _uiState.value.meetings.toMutableList()
        val index = updated.indexOfFirst { it.id == detail.id }
        if (index >= 0) updated[index] = detail else updated.add(detail)
        _uiState.value = _uiState.value.copy(meetings = updated.sortedBy { it.localDate().toString() + it.hora_inicio })
    }

    private fun launchSafe(block: suspend () -> Unit) {
        viewModelScope.launch {
            try {
                _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
                block()
                _uiState.value = _uiState.value.copy(isLoading = false)
            } catch (exc: UnauthorizedException) {
                sessionStore.clearToken()
                _uiState.value = AppUiState(
                    currentScreen = Screen.LOGIN,
                    baseUrl = sessionStore.baseUrl(),
                    errorMessage = "Su sesión expiró. Inicie sesión nuevamente.",
                    lastTechnicalError = "401 unauthorized",
                    pushStatus = sessionStore.pushStatus(),
                )
            } catch (exc: IllegalArgumentException) {
                _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = exc.message, lastTechnicalError = exc.message)
            } catch (exc: FriendlyException) {
                _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = exc.message, lastTechnicalError = exc.technicalMessage)
            } catch (exc: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Ocurrió un error inesperado. Intente nuevamente.",
                    lastTechnicalError = exc.message
                )
            }
        }
    }
}

private class AppViewModelFactory(private val sessionStore: SessionStore) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T = AppViewModel(sessionStore) as T
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppRoot(viewModel: AppViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val notificationPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted -> 
        coroutineScope.launch {
            if (uiState.currentUser != null) {
                val status = runCatching { NotificationRegistrar.sync(context) }
                    .getOrElse { "No fue posible preparar notificaciones." }
                viewModel.setPushStatus(status)
            }
        }
    }
    val launchMeetingId by MeetingLaunchBus.meetingId.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.errorMessage) {
        uiState.errorMessage?.let { snackbarHostState.showSnackbar(it) }
    }

    LaunchedEffect(uiState.currentUser?.id) {
        NotificationChannels.ensure(context)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !NotificationPermissionHelper.isGranted(context)) {
            notificationPermissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
        }
        if (uiState.currentUser != null) {
            val status = runCatching { NotificationRegistrar.sync(context) }
                .getOrElse { "No fue posible preparar notificaciones." }
            viewModel.setPushStatus(status)
        }
    }

    LaunchedEffect(launchMeetingId, uiState.currentUser?.id) {
        if (launchMeetingId != null && uiState.currentUser != null) {
            viewModel.openMeeting(launchMeetingId!!)
            MeetingLaunchBus.clear()
        }
    }

    val showBottomBar = uiState.currentScreen in setOf(Screen.HOME, Screen.PENDING, Screen.CALENDAR, Screen.HISTORY, Screen.PROFILE)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(screenTitle(uiState.currentScreen), color = ecuBlue, fontWeight = FontWeight.ExtraBold) }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = {
            if (showBottomBar) {
                NavigationBar(containerColor = Color.White) {
                    listOf(
                        Screen.HOME to "Inicio",
                        Screen.PENDING to "Pendientes",
                        Screen.CALENDAR to "Calendario",
                        Screen.HISTORY to "Historial",
                        Screen.PROFILE to "Perfil"
                    ).forEach { (screen, label) ->
                        NavigationBarItem(
                            selected = uiState.currentScreen == screen,
                            onClick = { viewModel.navigate(screen) },
                            icon = { Text(label.take(1), fontWeight = FontWeight.Bold) },
                            label = { Text(label) }
                        )
                    }
                }
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(ecuBg)
        ) {
            when (uiState.currentScreen) {
                Screen.LOGIN -> LoginScreen(uiState, viewModel)
                Screen.HOME -> HomeScreen(uiState, viewModel)
                Screen.PENDING -> PendingScreen(uiState, viewModel)
                Screen.CALENDAR -> CalendarScreen(uiState, viewModel)
                Screen.HISTORY -> HistoryScreen(uiState, viewModel)
                Screen.DETAIL -> MeetingDetailScreen(uiState, viewModel)
                Screen.REJECT -> RejectMeetingScreen(uiState, viewModel)
                Screen.PROFILE -> ProfileScreen(uiState, viewModel)
            }

            if (uiState.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = ecuBlueLight)
            }
        }
    }
}

private fun screenTitle(screen: Screen): String = when (screen) {
    Screen.LOGIN -> "Ecuamatriz"
    Screen.HOME -> "Inicio"
    Screen.PENDING -> "Pendientes"
    Screen.CALENDAR -> "Calendario"
    Screen.HISTORY -> "Historial"
    Screen.DETAIL -> "Detalle de reunión"
    Screen.REJECT -> "Rechazar reunión"
    Screen.PROFILE -> "Perfil"
}

@Composable
private fun LoginScreen(uiState: AppUiState, viewModel: AppViewModel) {
    var correo by remember { mutableStateOf("usuario1.contabilidad@empresa.local") }
    var password by remember { mutableStateOf("Usuario123!") }
    var baseUrl by remember(uiState.baseUrl) { mutableStateOf(uiState.baseUrl) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        BrandHeader()
        Spacer(modifier = Modifier.height(24.dp))
        Surface(shape = RoundedCornerShape(24.dp), color = Color.White, shadowElevation = 8.dp) {
            Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Ingreso institucional", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
                Text("Acceda a sus reuniones y respuestas pendientes.", color = ecuText)
                if (BuildConfig.DEBUG_UI) {
                    OutlinedTextField(
                        value = baseUrl,
                        onValueChange = {
                            baseUrl = it
                            viewModel.updateBaseUrl(it)
                        },
                        label = { Text("Base URL backend") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text(
                        "Ejemplos: http://10.0.2.2:5000 | http://192.168.0.139:5000 | https://tu-ngrok.ngrok-free.app",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                OutlinedTextField(value = correo, onValueChange = { correo = it }, label = { Text("Correo") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Contraseña") },
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = {
                        if (BuildConfig.DEBUG_UI) viewModel.saveBaseUrl(baseUrl)
                        viewModel.login(correo, password)
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = ecuBlueLight)
                ) { Text("Ingresar") }
                if (BuildConfig.DEBUG_UI) {
                    DebugBlock(uiState)
                }
            }
        }
    }
}

@Composable
private fun BrandHeader() {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
        Box(
            modifier = Modifier
                .size(82.dp)
                .background(ecuBlue, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Text("E", color = Color.White, fontSize = 40.sp, fontWeight = FontWeight.ExtraBold)
        }
        Spacer(modifier = Modifier.height(12.dp))
        Text("Ecuamatriz", style = MaterialTheme.typography.headlineLarge, color = ecuBlue, textAlign = TextAlign.Center)
        Text("Agenda institucional", color = ecuText)
    }
}

@Composable
private fun HomeScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val today = LocalDate.now()
    val todaysMeetings = uiState.meetings.filter { it.localDate() == today }
    val pending = uiState.meetings.filter { it.mi_respuesta == "Pendiente" }
    val nextMeeting = uiState.meetings.filter { it.localDate() >= today }.minByOrNull { it.localDate().toString() + it.hora_inicio }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Surface(shape = RoundedCornerShape(28.dp), color = ecuBlue) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Hola, ${uiState.currentUser?.nombre ?: ""}", color = Color.White, style = MaterialTheme.typography.headlineSmall)
                    Text("Revise sus reuniones de hoy y responda oportunamente.", color = Color.White.copy(alpha = 0.88f))
                    if (BuildConfig.DEBUG_UI) {
                        Text("Versión ${BuildConfig.VERSION_NAME}", color = ecuAccent, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                SummaryCard("Hoy", todaysMeetings.size.toString(), "reuniones", Modifier.weight(1f))
                SummaryCard("Pendientes", pending.size.toString(), "por responder", Modifier.weight(1f))
            }
        }
        item {
            if (nextMeeting != null) {
                HeroMeetingCard(title = "Próxima reunión", meeting = nextMeeting, onClick = { viewModel.openMeeting(nextMeeting.id) })
            } else {
                EmptyCard("No hay reuniones próximas registradas.")
            }
        }
        item {
            SectionHeader("Reuniones de hoy", action = "Ver pendientes") { viewModel.navigate(Screen.PENDING) }
        }
        if (todaysMeetings.isEmpty()) {
            item { EmptyCard("Hoy no tiene reuniones programadas.") }
        } else {
            items(todaysMeetings) { meeting -> AgendaMeetingCard(meeting, onClick = { viewModel.openMeeting(meeting.id) }) }
        }
        item {
            SectionHeader("Accesos", action = "Calendario") { viewModel.navigate(Screen.CALENDAR) }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                QuickAction("Pendientes", ecuBlueLight, Modifier.weight(1f)) { viewModel.navigate(Screen.PENDING) }
                QuickAction("Calendario", ecuAccent, Modifier.weight(1f)) { viewModel.navigate(Screen.CALENDAR) }
            }
        }
        item {
            QuickAction("Historial", ecuBlue, Modifier.fillMaxWidth()) { viewModel.navigate(Screen.HISTORY) }
        }
    }
}

@Composable
private fun SummaryCard(title: String, value: String, subtitle: String, modifier: Modifier = Modifier) {
    Card(modifier = modifier, colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, color = ecuText)
            Text(value, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = ecuText)
        }
    }
}

@Composable
private fun HeroMeetingCard(title: String, meeting: MeetingDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, color = ecuBlueLight, fontWeight = FontWeight.Bold)
            Text(meeting.titulo, style = MaterialTheme.typography.titleLarge, color = ecuText)
            Text("${meeting.dateLabel()} · ${meeting.timeRange()}", color = ecuText)
            Text(meeting.zona.nombre, color = ecuText)
            StatusPill(meeting.displayStatus())
        }
    }
}

@Composable
private fun EmptyCard(message: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Text(message, modifier = Modifier.padding(16.dp), color = ecuText)
    }
}

@Composable
private fun SectionHeader(title: String, action: String? = null, onAction: (() -> Unit)? = null) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = MaterialTheme.typography.titleLarge, color = ecuBlue)
        if (action != null && onAction != null) {
            TextButton(onClick = onAction) { Text(action) }
        }
    }
}

@Composable
private fun QuickAction(label: String, color: Color, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Button(onClick = onClick, modifier = modifier, colors = ButtonDefaults.buttonColors(containerColor = color)) {
        Text(label, color = if (color == ecuAccent) ecuBlue else Color.White, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun PendingScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val pendingMeetings = uiState.meetings.filter { it.mi_respuesta == "Pendiente" && it.estado != "Cancelada" }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Pendientes de responder", style = MaterialTheme.typography.titleLarge, color = ecuBlue)
                TextButton(onClick = { viewModel.loadMeetings() }) { Text("Actualizar") }
            }
        }
        if (pendingMeetings.isEmpty()) {
            item { EmptyCard("No tiene reuniones pendientes.") }
        } else {
            items(pendingMeetings) { meeting ->
                AgendaMeetingCard(meeting = meeting, onClick = { viewModel.openMeeting(meeting.id) })
            }
        }
    }
}

@Composable
private fun HistoryScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val today = LocalDate.now()
    val historyMeetings = uiState.meetings.filter {
        it.mi_respuesta != "Pendiente" || it.estado in setOf("Cancelada", "Finalizada") || it.localDate() < today
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Historial de reuniones", style = MaterialTheme.typography.titleLarge, color = ecuBlue)
                TextButton(onClick = { viewModel.loadMeetings() }) { Text("Actualizar") }
            }
        }
        if (historyMeetings.isEmpty()) {
            item { EmptyCard("Todavía no hay reuniones en su historial.") }
        } else {
            items(historyMeetings.sortedByDescending { it.localDate().toString() + it.hora_inicio }) { meeting ->
                AgendaMeetingCard(meeting = meeting, onClick = { viewModel.openMeeting(meeting.id) })
            }
        }
    }
}

@Composable
private fun AgendaMeetingCard(meeting: MeetingDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        border = BorderStroke(1.dp, ecuBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                modifier = Modifier
                    .width(8.dp)
                    .height(72.dp)
                    .background(meetingStatusColor(meeting), RoundedCornerShape(100.dp))
            )
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(meeting.titulo, style = MaterialTheme.typography.titleMedium, color = ecuText)
                Text("${meeting.dateLabel()} · ${meeting.timeRange()}", color = ecuText)
                Text(meeting.zona.nombre, color = ecuText)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    StatusPill(meeting.displayStatus())
                    PriorityPill(meeting.prioridad)
                }
                Text(meeting.responseSummaryLabel(), style = MaterialTheme.typography.bodySmall, color = ecuText)
                if (BuildConfig.DEBUG_UI) {
                    Text("ID ${meeting.id}", style = MaterialTheme.typography.bodySmall, color = ecuBlueLight)
                }
            }
        }
    }
}

@Composable
private fun CalendarScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val month = uiState.calendarMonth
    val meetingsByDate = uiState.meetings.groupBy { it.localDate() }
    val days = buildMonthGrid(month)
    val selectedMeetings = meetingsByDate[uiState.selectedCalendarDay].orEmpty()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { viewModel.previousMonth() }) { Text("◀") }
            Text(month.format(monthTitleFormatter).replaceFirstChar { it.titlecase(localeEs) }, style = MaterialTheme.typography.titleLarge, color = ecuBlue)
            TextButton(onClick = { viewModel.nextMonth() }) { Text("▶") }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            OutlinedButton(
                onClick = { viewModel.setCalendarMode(CalendarMode.MONTH) },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = if (uiState.calendarMode == CalendarMode.MONTH) ecuBlueLight else ecuBlue
                )
            ) { Text("Mes") }
            OutlinedButton(
                onClick = { viewModel.setCalendarMode(CalendarMode.AGENDA) },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = if (uiState.calendarMode == CalendarMode.AGENDA) ecuBlueLight else ecuBlue
                )
            ) { Text("Agenda") }
        }
        Spacer(modifier = Modifier.height(8.dp))
        if (uiState.calendarMode == CalendarMode.MONTH) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                listOf("L", "M", "X", "J", "V", "S", "D").forEach { label ->
                    Text(label, modifier = Modifier.weight(1f), textAlign = TextAlign.Center, color = ecuText, fontWeight = FontWeight.Bold)
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            days.chunked(7).forEach { week ->
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    week.forEach { day ->
                        CalendarDayCell(
                            day = day,
                            month = month,
                            hasMeetings = day != null && meetingsByDate[day].orEmpty().isNotEmpty(),
                            isSelected = day == uiState.selectedCalendarDay,
                            onClick = { if (day != null) viewModel.selectCalendarDay(day) },
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
            }
            Spacer(modifier = Modifier.height(16.dp))
            SectionHeader("Reuniones del ${uiState.selectedCalendarDay.format(longDateFormatter)}")
            if (selectedMeetings.isEmpty()) {
                EmptyCard("No hay reuniones para el día seleccionado.")
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    selectedMeetings.forEach { meeting -> AgendaMeetingCard(meeting, onClick = { viewModel.openMeeting(meeting.id) }) }
                }
            }
        } else {
            SectionHeader("Agenda institucional")
            if (uiState.meetings.isEmpty()) {
                EmptyCard("No hay reuniones registradas.")
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    uiState.meetings.forEach { meeting -> AgendaMeetingCard(meeting, onClick = { viewModel.openMeeting(meeting.id) }) }
                }
            }
        }
    }
}

@Composable
private fun CalendarDayCell(
    day: LocalDate?,
    month: YearMonth,
    hasMeetings: Boolean,
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val inCurrentMonth = day?.month == month.month
    Surface(
        modifier = modifier
            .height(58.dp)
            .clickable(enabled = day != null) { onClick() },
        shape = RoundedCornerShape(16.dp),
        color = if (isSelected) ecuBlueLight else Color.White,
        border = BorderStroke(1.dp, ecuBorder)
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text(
                text = day?.format(dayNumberFormatter) ?: "",
                color = when {
                    day == null -> Color.Transparent
                    isSelected -> Color.White
                    !inCurrentMonth -> ecuBorder
                    else -> ecuText
                },
                fontWeight = FontWeight.Bold
            )
            if (hasMeetings) {
                Box(
                    modifier = Modifier
                        .padding(top = 4.dp)
                        .size(7.dp)
                        .background(if (isSelected) Color.White else ecuAccent, CircleShape)
                )
            } else {
                Spacer(modifier = Modifier.height(11.dp))
            }
        }
    }
}

@Composable
private fun MeetingDetailScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val meeting = uiState.selectedMeeting ?: return
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        TextButton(onClick = { viewModel.backToPrimary() }) { Text("Volver") }
        Surface(shape = RoundedCornerShape(24.dp), color = Color.White, tonalElevation = 3.dp) {
            Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(meeting.titulo, style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    StatusPill(meeting.displayStatus())
                    PriorityPill(meeting.prioridad)
                }
                DetailRow("Fecha", meeting.dateLabel())
                DetailRow("Horario", meeting.timeRange())
                DetailRow("Zona", "${meeting.zona.nombre} · ${meeting.zona.ubicacion}")
                DetailRow("Creador", meeting.creador.nombre)
                DetailRow("Motivo", meeting.motivo)
                if (BuildConfig.DEBUG_UI) {
                    DetailRow("ID reunión", meeting.id.toString())
                }
            }
        }
        if (meeting.mi_razon_rechazo != null) {
            Surface(shape = RoundedCornerShape(18.dp), color = rejectedColor.copy(alpha = 0.18f)) {
                Text("Razón registrada: ${meeting.mi_razon_rechazo}", modifier = Modifier.padding(16.dp), color = ecuText)
            }
        }
        if (meeting.mi_respuesta == "Pendiente") {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                Button(
                    onClick = { viewModel.acceptMeeting(meeting.id) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = ecuBlueLight)
                ) { Text("Aceptar") }
                OutlinedButton(
                    onClick = { viewModel.openRejectScreen() },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = ecuBlue)
                ) { Text("Rechazar") }
            }
        }
        SectionHeader("Participantes")
        meeting.participantes.forEach { participant ->
            Card(colors = CardDefaults.cardColors(containerColor = Color.White), border = BorderStroke(1.dp, ecuBorder)) {
                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(participant.nombre, fontWeight = FontWeight.Bold, color = ecuText)
                    Text(participant.correo, color = ecuText)
                    StatusPill(participant.estado_respuesta)
                    if (!participant.razon_rechazo.isNullOrBlank()) {
                        Text("Razón: ${participant.razon_rechazo}", style = MaterialTheme.typography.bodySmall, color = ecuText)
                    }
                    if (BuildConfig.DEBUG_UI) {
                        Text("ID participante: ${participant.usuario_id}", style = MaterialTheme.typography.bodySmall, color = ecuBlueLight)
                    }
                }
            }
        }
    }
}

@Composable
private fun RejectMeetingScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val meeting = uiState.selectedMeeting ?: return
    var reason by remember { mutableStateOf("") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        TextButton(onClick = { viewModel.openMeeting(meeting.id) }) { Text("Volver al detalle") }
        Text("Rechazar reunión", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
        Text("Explique claramente por qué no podrá asistir.", color = ecuText)
        OutlinedTextField(
            value = reason,
            onValueChange = { reason = it },
            label = { Text("Razón obligatoria") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 5
        )
        Button(
            onClick = { viewModel.rejectMeeting(meeting.id, reason) },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = ecuBlueLight)
        ) { Text("Confirmar rechazo") }
    }
}

@Composable
private fun ProfileScreen(uiState: AppUiState, viewModel: AppViewModel) {
    val user = uiState.currentUser
    var baseUrl by remember(uiState.baseUrl) { mutableStateOf(uiState.baseUrl) }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Surface(shape = RoundedCornerShape(24.dp), color = Color.White) {
            Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(user?.nombre ?: "-", style = MaterialTheme.typography.headlineSmall, color = ecuBlue)
                DetailRow("Correo", user?.correo ?: "-")
                DetailRow("Área", user?.area?.nombre ?: "-")
                DetailRow("Rol", user?.role ?: "-")
                if (BuildConfig.DEBUG_UI) {
                    DetailRow("Base URL", uiState.baseUrl)
                    DetailRow("Versión", BuildConfig.VERSION_NAME)
                    DetailRow("Estado push", uiState.pushStatus ?: "Sin diagnostico")
                    if (uiState.lastTechnicalError != null) {
                        DetailRow("Último error técnico", uiState.lastTechnicalError)
                    }
                    OutlinedTextField(
                        value = baseUrl,
                        onValueChange = { baseUrl = it },
                        label = { Text("URL backend") },
                        modifier = Modifier.fillMaxWidth(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
                    )
                    Button(onClick = { viewModel.saveBaseUrl(baseUrl) }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = ecuBlueLight)) {
                        Text("Guardar URL")
                    }
                }
            }
        }
        OutlinedButton(onClick = { viewModel.logout() }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.outlinedButtonColors(contentColor = ecuBlue)) {
            Text("Cerrar sesión")
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = ecuBlueLight, fontWeight = FontWeight.Bold)
        Text(value, style = MaterialTheme.typography.bodyLarge, color = ecuText)
    }
}

@Composable
private fun StatusPill(status: String) {
    val color = when (status) {
        "Pendiente" -> pendingColor
        "Aceptada", "Aceptado" -> acceptedColor
        "Rechazada", "Rechazado" -> rejectedColor
        "Cancelada" -> canceledColor
        else -> ecuAccent
    }
    Box(modifier = Modifier.background(color.copy(alpha = 0.28f), RoundedCornerShape(30.dp)).padding(horizontal = 10.dp, vertical = 5.dp)) {
        Text(status, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = ecuText)
    }
}

@Composable
private fun PriorityPill(priority: String) {
    Box(modifier = Modifier.background(ecuBlue.copy(alpha = 0.12f), RoundedCornerShape(30.dp)).padding(horizontal = 10.dp, vertical = 5.dp)) {
        Text(priority, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = ecuBlue)
    }
}

@Composable
private fun DebugBlock(uiState: AppUiState) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FBFF)), border = BorderStroke(1.dp, ecuBorder)) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Modo debug activo", color = ecuBlue, fontWeight = FontWeight.Bold)
            Text("Versión ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)
            Text("URL ${uiState.baseUrl}", style = MaterialTheme.typography.bodySmall)
            Text("Push ${uiState.pushStatus ?: "sin estado"}", style = MaterialTheme.typography.bodySmall)
            if (uiState.lastTechnicalError != null) {
                Text("Último error: ${uiState.lastTechnicalError}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun meetingStatusColor(meeting: MeetingDto): Color = when (meeting.displayStatus()) {
    "Pendiente" -> pendingColor
    "Parcialmente respondida" -> ecuAccent
    "Aceptada" -> acceptedColor
    "Rechazada" -> rejectedColor
    "Cancelada" -> canceledColor
    else -> ecuAccent
}

private fun buildMonthGrid(month: YearMonth): List<LocalDate?> {
    val firstDay = month.atDay(1)
    val shift = when (firstDay.dayOfWeek) {
        DayOfWeek.MONDAY -> 0
        DayOfWeek.TUESDAY -> 1
        DayOfWeek.WEDNESDAY -> 2
        DayOfWeek.THURSDAY -> 3
        DayOfWeek.FRIDAY -> 4
        DayOfWeek.SATURDAY -> 5
        DayOfWeek.SUNDAY -> 6
    }
    val cells = mutableListOf<LocalDate?>()
    repeat(shift) { cells.add(null) }
    for (day in 1..month.lengthOfMonth()) cells.add(month.atDay(day))
    while (cells.size % 7 != 0) cells.add(null)
    return cells
}

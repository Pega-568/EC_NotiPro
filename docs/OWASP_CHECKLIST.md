# Checklist OWASP aplicado

- [x] Autenticacion robusta con Argon2id.
- [x] Sesion con cookie `HttpOnly` y `SameSite`.
- [x] Token CSRF para operaciones mutantes autenticadas.
- [x] Autorizacion por rol y por objeto en backend.
- [x] No se exponen `password_hash`, tokens ni secretos en JSON.
- [x] Validacion server-side de area, estado, propiedad y agenda.
- [x] Respuestas de error publicas sin stack trace ni SQL interno.
- [x] CORS restringido a origenes permitidos.
- [x] Logs de auditoria para login, fallos, cambios e intentos no autorizados.
- [x] ORM con queries parametrizadas y restricciones relacionales.


# Modelo de datos

- `roles`: catalogo de roles validos.
- `areas`: areas organizacionales.
- `usuarios`: usuario, rol, area, estado y control de intentos.
- `zonas_reunion`: salas con capacidad, estado y margen operativo.
- `reuniones`: cabecera de agenda con creador, area origen, zona, fecha y horario.
- `reunion_participantes`: participantes y su respuesta.
- `configuracion`: valores operativos parametrizables.
- `sesiones`: sesiones web activas con token opaco y expiracion.
- `logs_sistema`: auditoria segura de acciones y rechazos.

Controles de integridad:

- llaves foraneas
- correo unico
- estados y prioridades con `CHECK`
- indice de busqueda sobre reuniones y logs
- sesiones revocables


# BUILDPC3D: preparación para Render Free

Carpeta autónoma preparada para un repositorio público. No se ha creado
ningún servicio ni se han conectado cuentas. Es una copia independiente del
backend; futuras correcciones deberán sincronizarse con `backend/`.

## Seguridad: no habilitar todavía

El Web Service de Render será público en cuanto se despliegue; no hay modo
de afirmar que la URL no está expuesta. `GROQ_ENABLED=false` impide llamadas
a Groq mientras se comprueban los controles. `/health` es público y solo
indica que el proceso responde; no prueba Redis ni Groq.

`ProxyFix(x_for=1)` usa el último valor `X-Forwarded-For`; el puerto de Render
no es directamente accesible desde Internet según su documentación, pero
otros servicios de la red privada pueden alcanzarlo. **No se ha demostrado**
qué cabecera establece Render ni si se puede falsificar por todas las rutas.
Antes de activar Groq, verificar con Render y con pruebas controladas desde
distintas redes, cabeceras falsificadas y red privada; restringir acceso interno
o mantener `GROQ_ENABLED=false` si no puede garantizarse. Sin Nginx no hay sus
límites adicionales; cuotas IP no son defensa completa contra bots o IPv6.

Cuotas Redis: 10/IP por hora, 100/día UTC, 2 concurrentes, configurables.
Se reservan antes de llamar a Groq; Redis inalcanzable devuelve 503 y cuotas
excedidas 429. Se usa `rediss://` con certificado y hostname verificados,
sin parámetros de URL capaces de deshabilitar TLS y sin reintentos de Redis.
Las reservas de concurrencia caducan a los 120 s: una llamada atascada más
tiempo puede solaparse. El timeout de red de Groq es 15 s por operación,
no un plazo global estricto; comprobarlo antes de habilitar.

Upstash documenta `EVAL` atómico y `TIME` en Lua. El script usa además una
clave diaria dinámica bajo el bloqueo global; esto puede aumentar latencia y
debe probarse contra Upstash real. Un error Lua no revierte escrituras ya
efectuadas; no se llama a Groq si Redis devuelve error. El reintento automático
ante resultado incierto podría consumir cuotas adicionales y está desactivado.
Comprobar persistencia, límites y comportamiento ante interrupciones reales.

## GitHub: revisión antes de publicar

No copie aquí archivos del proyecto completo. `.gitignore` usa lista explícita
de archivos, pero no garantiza que no existan secretos ya incluidos o en el
historial. Inspeccione manualmente todos los archivos y el historial antes de
subir; nunca añada `.env`, credenciales, claves, bases de datos ni APK.

Desde esta carpeta, tras revisión y consentimiento, iniciar un repositorio
independiente y examinar su contenido:

```bash
git init
git add .gitignore app.py production.py wsgi.py requirements.txt requirements-test.txt render.yaml README.md tests/test_render.py
git status --short
git diff --cached
```

Compruebe nuevamente que no hay secretos; no incluya salidas de comandos con
tokens en conversaciones. Este repositorio será público: nunca suba claves,
credenciales ni archivos de entorno, tampoco en el historial.

## Upstash Free

Tras la autorización, crear cuenta/base Redis eligiendo explícitamente Free,
la región compatible más cercana a Render y sin elegir Pay as You Go ni
productos adicionales. En el panel copiar **privadamente** la URL Redis TCP
con TLS (`rediss://`), no la URL/token REST. Pegarla solo como variable
secreta `REDIS_URL` en Render; no enviarla en mensajes ni guardarla en Git.
La URL y su contraseña son credenciales. No agregue tarjeta ni cambie de plan
sin revisar condiciones. Monitorice uso y vencimiento según el panel.

La página oficial consultada indica 250 MB y 500 000 comandos/mes para Free;
confirmar cifras y condiciones actuales. Los comandos internos de Lua pueden
contar, por lo que 100 solicitudes/día no equivale a 100 comandos/día.

## Render Free: configuración prevista, no ejecutar aún

Con el repositorio enlazado, crear Web Service Python y seleccionar
explícitamente plan **Free**. No agregar discos, bases ni otros servicios.
También puede revisarse `render.yaml` como Blueprint antes de aplicarlo;
crearlo/aplicarlo desplegaría un endpoint público.

- Build: `pip install -r requirements.txt`
- Start: `python start_render.py`
- Health check: `/health`

Variables en el panel:

- `GROQ_ENABLED=false` (después cambiar solo al aprobar seguridad).
- `GROQ_API_KEY` y `REDIS_URL`: secretos privados, sin valores en Git.
- `IP_PER_HOUR=10`, `GLOBAL_PER_DAY=100`, `MAX_CONCURRENT=2`.
- `GROQ_MODEL`: opcional; el backend tiene un valor predeterminado.
- `PORT`: asignado por Render; no configurarlo manualmente.
- `UPSTASH_STARTUP_CHECK`: opcional, `false` por defecto. Solo con
  `GROQ_ENABLED=false`, poner temporalmente `true` para probar TLS, PING y
  Lua aislado al arrancar. Comprobar en logs `UPSTASH_CHECK TLS_PING OK` y
  `UPSTASH_CHECK LUA_CONCURRENCIA_TTL OK`; un fallo no impide `/health`.
  Volver a `false` tras la prueba: si no, se repetirá en cada reinicio.

Render puede dormir tras 15 minutos de inactividad y tardar alrededor de un
minuto en despertar. No crear cron ni pings para impedir el reposo. El plan
Free no es adecuado para producción garantizada. Render indica 750 horas Free
por workspace/mes; ancho de banda y minutos de build tienen límites y podrían
generar cobros si hay método de pago. Upstash y Groq tienen límites y planes
propios; no es posible garantizar coste cero durante dos meses. Revise paneles,
cuotas, condiciones, alertas y método de pago antes de activar.

## Android y despertar bajo demanda

El APK actual tiene URL Android vacía y espera 18 s; no ejecuta calentamiento.
Cuando se implemente el cliente, al pulsar Interpretar enviar **una** petición
GET a `/health` con plazo suficiente (por ejemplo 90 s) y un indicador de
espera/cancelación. Solo después de un HTTP 200 válido enviar **un** POST
`/interpretar`. Si el GET falla, usar respaldo local; no repetir un POST tras
timeout o respuesta incierta, pues Groq podría haber sido invocado. Manejar
429/503 y ofrecer reintento manual informado. El GET puede despertar el servicio
y no usa cuota ni Groq; no debe programarse periódicamente. Verificar que solo
se acepten URLs HTTPS configuradas y que cancelar no desencadene el POST.
Esta modificación de Godot **no se ha implementado**.

## Pruebas pendientes

Probar en un entorno limitado, sin habilitar IA públicamente: certificado TLS
real y nombre de host Upstash; Lua `EVAL`/`TIME`, clave dinámica y concurrencia
entre procesos; caída y resultados inciertos de Redis; IP confiable y spoofing
por todas las rutas; suspensión de Render y despertar; protección frente a
abuso, costes y registros. Para usar Groq se requiere una prueba autorizada y
una decisión expresa de activar la variable. Las pruebas locales usan
fakeredis y no sustituyen esas comprobaciones.

Fuentes: https://render.com/docs/free,
https://render.com/docs/web-services,
https://upstash.com/docs/redis/commands/scripting/eval,
https://upstash.com/pricing/redis.

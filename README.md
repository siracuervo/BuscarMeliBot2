# Bot de búsqueda: Chevrolet Onix en Mercado Libre

Busca cada 30 minutos publicaciones de Chevrolet Onix en Mercado Libre Argentina
con transmisión automática, entre 10.000 y 55.000 km, año 2020 en adelante,
y te avisa por Telegram cuando aparece una nueva.

## 1. Crear el bot de Telegram (2 minutos)

1. Abrí Telegram y buscá **@BotFather**.
2. Enviale `/newbot`, elegí un nombre y un usuario (debe terminar en `bot`).
3. Te va a dar un **token** parecido a `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Guardalo.
4. Iniciá una conversación con tu bot recién creado (buscalo por su usuario y tocá "Start").

## 2. Obtener tu Chat ID

1. Enviale cualquier mensaje a tu bot (por ejemplo "hola").
2. Abrí en el navegador (reemplazando `<TOKEN>` por el tuyo):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Buscá el campo `"chat":{"id": ...}` en la respuesta. Ese número es tu `TELEGRAM_CHAT_ID`.

## 3. Subir este proyecto a GitHub

1. Creá un repositorio nuevo en GitHub (puede ser privado).
2. Subí todos estos archivos (`ml_bot.py`, `requirements.txt`, `seen_ids.json`,
   la carpeta `.github/workflows/ml_bot.yml`, y este README).

```bash
git init
git add .
git commit -m "Bot de búsqueda Onix Mercado Libre"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

## 4. Configurar los secrets en GitHub

En el repo: **Settings → Secrets and variables → Actions → New repository secret**

- `TELEGRAM_BOT_TOKEN` → el token del paso 1
- `TELEGRAM_CHAT_ID` → el número del paso 2

## 5. Activar el workflow

- Andá a la pestaña **Actions** del repo.
- Si te pide habilitar Actions, aceptá.
- Podés correrlo manualmente con el botón **Run workflow** para probarlo,
  o esperar a que corra solo cada 30 minutos según el cron configurado.

## Ajustar los filtros

Todo lo que es criterio de búsqueda (modelo, año, km, transmisión, frecuencia)
está al principio de `ml_bot.py` y en el `cron` de `.github/workflows/ml_bot.yml`.
No hace falta tocar el resto del código para cambiar esos valores.

## Notas importantes — leé esto

Este bot funciona leyendo la página web de resultados de Mercado Libre
(scraping), no la API oficial, porque desde abril de 2025 Mercado Libre
cerró el acceso público a su API de búsqueda. Esto tiene consecuencias:

- **Mercado Libre bloquea el scraping en su robots.txt.** El bot está armado
  para minimizar el riesgo (headers de navegador real, pausas entre pedidos,
  corre solo cada 3 horas), pero no hay garantía de que no te bloqueen la IP
  de GitHub Actions en algún momento. Si eso pasa, vas a ver errores 403 o
  captchas en los logs.
- **Es frágil ante cambios de diseño.** Si de un día para el otro el bot deja
  de encontrar publicaciones (`0 publicaciones encontradas` en el log) aunque
  sabés que hay autos publicados, lo más probable es que Mercado Libre haya
  cambiado el HTML de la página y haya que actualizar los selectores en la
  función `parse_cards()` de `ml_bot.py`.

### Cómo depurar si deja de funcionar

1. Corré el bot en tu compu (no en GitHub Actions) para poder inspeccionar:
   ```bash
   pip install -r requirements.txt
   python ml_bot.py
   ```
2. En `main()`, descomentá la línea `Path("debug.html").write_text(...)`.
   Esto guarda una copia del HTML real que devolvió Mercado Libre.
3. Abrí `debug.html` en el navegador o con "Ver código fuente", buscá el
   bloque de una publicación (Ctrl+F por el título de un auto que sepas que
   está publicado), y fijate qué clases CSS usa ese bloque ahora.
4. Actualizá `candidate_selectors` en `parse_cards()` con la clase nueva.

### Si cambiás los filtros de búsqueda

No edites parámetros sueltos en el código: andá a
`https://autos.mercadolibre.com.ar/chevrolet/onix/`, aplicá los filtros que
quieras desde la interfaz (año, precio, km, transmisión), copiá la URL
resultante de la barra de direcciones, y reemplazá el valor de `SEARCH_URL`
en `ml_bot.py` por esa URL nueva.

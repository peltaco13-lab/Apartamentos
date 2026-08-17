# Cali Arriendos V5

Agregador estático de apartamentos en arriendo en Cali. El sitio vive en GitHub Pages y GitHub Actions actualiza los datos de varias fuentes públicas de manera escalonada.

## Qué cambió en V5 (respecto a lo que subiste)

- **Se arregló la causa más probable de los workflows en rojo:** si hacías un commit manual en `main` mientras una corrida estaba trabajando, el `git push` final chocaba (non-fast-forward) y el workflow fallaba en segundos. Ahora el paso de guardado hace `git fetch` + `git rebase` y reintenta el push automáticamente.
- **Blindaje contra fuentes que fallan de forma inesperada:** antes, si una fuente rompía el parseo con un error no previsto (no solo de red), todo `collect.py` podía morir y tumbar el workflow. Ahora cada fuente está aislada: si una explota, se registra el error y las demás fuentes siguen su curso.
- **Reintento automático por página:** cada URL se reintenta una vez más si falla por timeout/conexión antes de darse por vencida.
- **Metrocuadrado vuelve a manual.** Confirmado (dos veces, con meses de diferencia) que su página de resultados carga los anuncios con JavaScript del lado del cliente — un `requests.get()` nunca ve un anuncio ahí. Dejarlo "automático" solo generaba falsos "0 encontrados".
- **Regex de Mercado Libre corregido.** Era demasiado amplio (`/[^/]*apartamento[^/]*`) y podía capturar páginas de categoría como si fueran anuncios. Ahora exige el patrón real de un anuncio individual (`/MCO-12345678`).
- **Dos fuentes nuevas automáticas: Nuroa y Yumblin.** Confirmé que ambas devuelven contenido de anuncios en HTML estático (sin JavaScript). Sus patrones de URL de anuncio individual son mi mejor estimación a partir de resultados de búsqueda, no los verifiqué anuncio por anuncio como sí hice con FincaRaíz/Ciencuadras — si alguna vez encuentras 0 resultados de ellas, es lo primero que revisaría.
- **`.gitignore` añadido** (faltaba, y por eso `__pycache__/` compilado terminaba viajando en tus ZIPs).
- **Sobre Facebook Marketplace:** sigue sin poder automatizarse. Bloquea accesos automatizados y exige sesión iniciada para ver el detalle de cualquier anuncio — no hay forma limpia de resolver eso sin violar sus términos de uso (login, CAPTCHA, evasión de anti-bot). Queda como enlace manual, igual que antes.

## Si un workflow vuelve a fallar en rojo

1. Entra a **Actions → (la corrida en rojo)** y mira qué paso específico falló (aparece con una ✗).
2. Si falló en **"Guardar datos actualizados"**: probablemente fue un choque de `git push` que el rebase automático no pudo resolver solo (por ejemplo, si editaste el mismo archivo `data/listings.json` a mano). Solución: no edites `data/listings.json` manualmente: es un archivo que solo debe tocar el bot.
3. Si falló en **"Actualizar apartamentos"**: copia el mensaje de error y pégamelo — con eso reviso el bug puntual en `scripts/`.
4. Si falló en **"Instalar dependencias"**: suele ser un problema temporal de PyPI; vuelve a correr el workflow con **Re-run jobs**.

## Qué cambia en V4

- **Sin precio máximo fijo.** El recolector guarda cualquier precio que detecte y cada visitante elige su presupuesto.
- **9 fuentes automáticas + Facebook Marketplace manual.**
- **Actualización escalonada** para reducir carga:
  - fuentes principales: cada 4 horas;
  - fuentes secundarias: cada 8 horas;
  - inmobiliarias locales: cada 12 horas.
- **Deduplicación conservadora:** si el mismo apartamento aparece en más de un portal, intenta agruparlo y mostrar varias fuentes.
- Conserva temporalmente avisos anteriores si una fuente falla o bloquea el runner.
- No inicia sesión, no resuelve CAPTCHA y no intenta evadir protecciones anti-bot.

## Fuentes configuradas

### Principales · cada 4 h
1. FincaRaíz
2. Ciencuadras
3. Mercado Libre Inmuebles

### Secundarias · cada 8 h
4. Arriendo.com
5. Unisa Inmobiliaria
6. Bienco
7. Nuroa
8. Yumblin

### Locales · cada 12 h
9. A&C Inmobiliarios
10. Metro Red Inmobiliaria

### Manual (no se pueden automatizar)
11. Metrocuadrado — carga los anuncios con JavaScript, un GET simple no ve nada.
12. Facebook Marketplace — exige sesión iniciada y bloquea accesos automatizados.

Estas dos quedan como enlace directo porque no corresponden a lo que un scraper estático puede leer, no porque falte esfuerzo en configurarlas.

## GitHub Actions

El workflow está en:

```text
.github/workflows/update-and-deploy.yml
```

GitHub lo intenta ejecutar cada 4 horas, al minuto 37:

```yaml
schedule:
  - cron: "37 */4 * * *"
```

La cadencia interna decide qué fuentes deben revisarse en esa ejecución. Por ejemplo, aunque el workflow corra, una fuente configurada cada 12 horas se omite hasta que corresponda.

También puedes ejecutarlo manualmente desde **Actions**.

## Estructura

```text
CaliArriendos/
├── .github/
│   └── workflows/
│       └── update-and-deploy.yml
├── assets/
│   ├── css/
│   │   ├── responsive.css
│   │   └── styles.css
│   └── js/
│       └── app.js
├── config/
│   ├── areas.json
│   └── sources.json
├── data/
│   └── listings.json
├── scripts/
│   ├── collect.py
│   ├── dedupe.py
│   └── scrape.py
├── index.html
├── requirements.txt
└── README.md
```

## Subir/reemplazar en GitHub

Si ya tienes el repositorio `Apartamentos`:

1. Descomprime el ZIP.
2. Entra en la carpeta `CaliArriendos`.
3. En GitHub abre **Code → Add file → Upload files**.
4. Arrastra **todo el contenido interno**, incluida la carpeta `.github` si el navegador la permite.
5. Los archivos con la misma ruta se reemplazan al confirmar el commit.
6. Confirma con un mensaje como `Actualizar Cali Arriendos V4`.

Si el navegador no permite arrastrar la carpeta oculta `.github`, conserva la que ya tienes en el repo y comprueba que contenga `workflows/update-and-deploy.yml`.

## Precio

El precio no se limita en `collect.py`.

En la interfaz el visitante puede:

- dejar **Sin límite**;
- mover la barra;
- escribir un valor manual como `15000000`;
- ampliar automáticamente el rango de la barra si escribe una cifra mayor.

## Zonas sin dirección exacta

El visitante puede buscar por:

- Toda Cali
- Sur
- Norte
- Este
- Oeste
- Centro

y luego afinar por barrio/sector cuando los avisos permiten detectarlo.

## Cómo se agrupan duplicados

V4 compara de forma conservadora:

- barrio/sector;
- precio;
- habitaciones;
- baños;
- área;
- similitud del título.

Solo agrupa cuando hay suficientes coincidencias. La tarjeta conserva enlaces a varias fuentes para poder comprobar el aviso original.

## Tolerancia a fallos

Los portales pueden cambiar HTML, cargar contenido con JavaScript o bloquear automatizaciones. Por eso el sistema:

- no borra inmediatamente resultados antiguos;
- marca como `por revisar` avisos que dejan de aparecer tras una revisión válida;
- conserva avisos cuando una fuente completa falla;
- siempre ofrece el enlace directo a cada portal.

## Agregar otra fuente

Edita `config/sources.json`. Ejemplo:

```json
{
  "name": "Nueva inmobiliaria",
  "tier": "local",
  "cadence_hours": 12,
  "automated": true,
  "max_items": 60,
  "allowed_domains": ["ejemplo.com"],
  "listing_regex": "/inmueble/",
  "urls": ["https://ejemplo.com/arriendos/cali"],
  "manual_urls": ["https://ejemplo.com/arriendos/cali"]
}
```

No conviene agregar decenas de páginas del mismo portal. Una página de resultados amplia por fuente suele ser mejor que muchas búsquedas pequeñas.

## Ejecutar localmente

```bash
pip install -r requirements.txt
python scripts/collect.py --no-network
python scripts/collect.py --all
```

`--all` fuerza todas las fuentes y está pensado para pruebas, no para usarlo continuamente.

## Seguridad al arrendar

Nunca transfieras dinero únicamente para “separar” un inmueble. Verifica el apartamento, la identidad del propietario o inmobiliaria y el contrato antes de pagar.

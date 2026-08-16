# Cali Arriendos

Dashboard estático para reunir apartamentos en arriendo en Cali sin pedir una dirección exacta y publicarlos con GitHub Pages.

## Configuración inicial

- Tope: **$2.000.000 COP**
- Búsqueda principal por **Zona Sur, Norte, Este, Oeste o Centro**, sin pedir dirección exacta
- Barrios prioritarios del sur: **Bochalema, Cachipay/Kachipay, Ciudad Meléndez y Valle del Lili**
- Actualización: **cada 6 horas**
- Frontend: **HTML + CSS + JavaScript vanilla**
- Automatización: **GitHub Actions**
- Hosting: **GitHub Pages**

## Estructura

```text
CaliArriendos/
├── .github/workflows/update-and-deploy.yml
├── assets/css/styles.css
├── assets/css/responsive.css
├── assets/js/app.js
├── config/areas.json
├── config/sources.json
├── data/listings.json
├── scripts/collect.py
├── index.html
├── requirements.txt
└── README.md
```

## Subirlo a GitHub

1. Crea un repo nuevo, por ejemplo `CaliArriendos`.
2. Sube **el contenido interno de esta carpeta** a la rama `main`.
3. Ve a `Settings → Pages`.
4. En `Build and deployment → Source`, selecciona **GitHub Actions**.
5. Abre `Actions`.
6. Ejecuta `Actualizar arriendos y publicar Pages` manualmente si el primer push no lo arrancó.
7. Al terminar, GitHub mostrará la URL pública.

El workflow también se ejecuta automáticamente cada 6 horas (minuto 17).

## Cómo trabaja el recolector

`scripts/collect.py` lee `config/sources.json` y `config/areas.json`, consulta solo páginas públicas configuradas y busca:

- JSON-LD público.
- Enlaces visibles a anuncios.
- Precio, zona, habitaciones, baños, área y parqueadero cuando aparecen en el HTML.

Después:

- descarta precios conocidos sobre $2.000.000 COP;
- fusiona nuevos avisos con resultados anteriores;
- conserva temporalmente resultados previos cuando una fuente falla;
- genera `data/listings.json`;
- el frontend lo filtra sin backend.

## Cambiar presupuesto

En `config/sources.json` cambia:

```json
"max_rent_cop": 2000000
```

## Agregar una zona

En `site.zones` agrega, por ejemplo:

```json
{
  "name": "Caney",
  "aliases": ["caney"]
}
```

Luego agrega una página pública de búsqueda de esa zona en alguna fuente.

## Facebook Marketplace

Está como acceso manual. El sistema no inicia sesión, no resuelve CAPTCHA y no intenta evadir protecciones anti-bot.

## Metrocuadrado

También está como acceso manual: su página de resultados carga los anuncios con JavaScript en el navegador, así que una petición HTTP simple no devuelve ningún anuncio en el HTML. Intentar automatizarlo solo generaría "0 encontrados" en cada corrida sin aportar nada.

## Limitaciones

Los portales pueden cambiar HTML o bloquear runners automatizados. Si pasa:

- el panel conserva resultados anteriores por un tiempo;
- los marca como `por revisar`;
- los enlaces directos de cada portal siguen disponibles.

Los workflows programados de GitHub pueden sufrir retrasos ocasionales; no deben tratarse como un reloj exacto.

## Seguridad

Antes de pagar o separar un apartamento, verifica inmueble, propietario o inmobiliaria y contrato.


## Búsqueda sin dirección exacta

El usuario puede elegir **Zona Sur, Norte, Este, Oeste, Centro o Toda Cali** sin escribir una dirección real. El barrio es opcional.

### Respaldo inteligente

Si una macrozona queda sin coincidencias bajo los filtros, el panel intenta mostrar hasta 6 alternativas disponibles de otras zonas de Cali y avisa claramente que no son coincidencias exactas. Si no hay avisos cacheados, quedan visibles los botones de búsqueda directa en los portales.

El sistema no inventa propiedades ni garantiza que exista un apartamento disponible en una zona determinada.

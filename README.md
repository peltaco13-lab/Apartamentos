# Cali Arriendos

Dashboard estático para reunir apartamentos en arriendo del sur de Cali y publicarlos con GitHub Pages.

## Configuración inicial

- Precio: **sin tope fijo en el recolector**
- Cada usuario puede indicar su presupuesto máximo o dejar **Sin límite**
- Búsqueda principal por **Zona Sur, Norte, Este, Oeste o Centro**, sin pedir dirección exacta
- Barrios prioritarios del sur: **Bochalema, Cachipay/Kachipay, Ciudad Meléndez y Valle del Lili**
- Actualización: **cada hora**
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

El workflow también se ejecuta automáticamente al minuto 17 de cada hora.

## Cómo trabaja el recolector

`scripts/collect.py` lee `config/sources.json`, consulta solo páginas públicas configuradas y busca:

- JSON-LD público.
- Enlaces visibles a anuncios.
- Precio, zona, habitaciones, baños, área y parqueadero cuando aparecen en el HTML.

Después:

- conserva los precios detectados sin aplicar un tope global;
- fusiona nuevos avisos con resultados anteriores;
- conserva temporalmente resultados previos cuando una fuente falla;
- genera `data/listings.json`;
- el frontend lo filtra sin backend.

## Presupuesto

Ya no existe un límite global de $2.000.000. El recolector intenta conservar todos los avisos de arriendo que detecte.

En la web, cada usuario puede:

- escribir un presupuesto máximo, por ejemplo `15000000`;
- mover la barra de presupuesto;
- marcar **Sin límite** para ver todos los precios disponibles.

El número escrito puede superar el máximo visible inicial de la barra: la barra se amplía automáticamente, así que no existe un tope de precio configurado para el usuario.

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

## Limitaciones

Los portales pueden cambiar HTML o bloquear runners automatizados. Si pasa:

- el panel conserva resultados anteriores por un tiempo;
- los marca como `por revisar`;
- los enlaces directos de cada portal siguen disponibles.

Los workflows programados de GitHub pueden sufrir retrasos ocasionales; no deben tratarse como un reloj exacto.

## Seguridad

Antes de pagar o separar un apartamento, verifica inmueble, propietario o inmobiliaria y contrato.


## Búsqueda sin dirección exacta

El usuario no necesita escribir una dirección real.

Puede elegir:

- Zona Sur
- Zona Norte
- Zona Este
- Zona Oeste
- Zona Centro
- Toda Cali

El sistema clasifica los avisos por macrozona cuando el barrio o el propio portal permiten identificarla.

### Respaldo inteligente

Si una macrozona seleccionada queda sin coincidencias bajo los filtros:

1. el panel intenta mostrar hasta 6 alternativas disponibles de otras zonas de Cali;
2. avisa claramente que son alternativas y no coincidencias exactas;
3. mantiene botones de búsqueda directa en los portales para la macrozona elegida.

Esto evita una pantalla muerta, pero no inventa propiedades ni garantiza que exista un apartamento disponible en una zona determinada.


## Cambio V3 — precio libre

Se eliminó el filtro fijo de $2.000.000 tanto del recolector como del JSON. El presupuesto ahora es únicamente un filtro personal en el navegador y no limita lo que GitHub Actions puede recopilar.

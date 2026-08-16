# Cali Arriendos V4

Agregador estático de apartamentos en arriendo en Cali. El sitio vive en GitHub Pages y GitHub Actions actualiza los datos de varias fuentes públicas de manera escalonada.

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
4. Metrocuadrado

### Secundarias · cada 8 h
5. Arriendo.com
6. Unisa Inmobiliaria
7. Bienco

### Locales · cada 12 h
8. A&C Inmobiliarios
9. Metro Red Inmobiliaria

### Manual
10. Facebook Marketplace

Facebook queda como acceso directo porque normalmente exige sesión y aplica protecciones que no corresponden a un scraper estático.

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

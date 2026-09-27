# Odossey Travel (Viajes) – Análisis y decisiones

## Qué se reutiliza de Odoo 19 Community (todo LGPL-3)
- `sale_management` + `sale_crm`: las reservas son órdenes de venta (`sale.order`) vinculadas a un viaje; la seña usa el asistente estándar de anticipos.
- `crm`: oportunidades por viaje (`crm.lead.trip_id`), ganadas/perdidas (`won_status`) y motivos de pérdida.
- `calendar`, `mail`: chatter, actividades.
- `account` + `l10n_ar`: Factura A/B/C, tipos de documento, IVA exento / no gravado / 10,5 / 21, fechas de servicio ARCA.
- Fuera: `l10n_ar_edi`, `l10n_ar_reports`, `account_invoice_extract` (Enterprise). CAE: módulos OCA `l10n_ar_afipws_fe` (en addons path, 19.0) a nivel instancia.

## Facturación ARCA (según la factura de ejemplo)
Factura B, concepto Servicios. Cada componente del viaje es un producto de servicio con su IVA:
pasaje aéreo internacional → exento; servicios terrestres en el exterior → no gravado;
servicios de comercialización (comisión) → IVA 21 %. Las fechas de servicio ARCA toman las fechas del viaje (configurable).
**A confirmar con el contador:** intermediación o cuenta propia, exento o no gravado para el terrestre exterior,
fechas de servicio, moneda (USD/ARS), percepción RG 5617 (30 % en turismo al exterior pagado en pesos), base y alícuota de IIBB
(la factura de ejemplo dice "IIBB: EXENTO"), la seña como factura de anticipo o como recibo, y el punto de venta para webservice (el PV 0004 es de Comprobantes en Línea).

## Lectura de documentos
- DNI tarjeta: el código es **PDF417**, no QR (campos separados por `@`, formato 2012+ y el de 2009-2012). El DNI electrónico 2026 trae QR con formato no oficial.
- Pasaporte: zona **MRZ** (TD3, 2 × 44), con los dígitos verificadores validados.
- Captura: lector 2D en modo teclado (lo más fiable; si el `@` llega como `"` se corrige solo), la cámara con el escáner del core de Odoo (PDF417 y QR, requiere HTTPS), o pegando la MRZ.
- Se registra el consentimiento (Ley 25.326) en el chatter del contacto.

## "Reporte 31"
No es concluyente, así que no se implementó. Opciones:
1. F.931 (cargas sociales, sale de sueldos);
2. reportes contables "al 31" (sumas y saldos, mayor: OCA `account_financial_report` 19.0 está disponible);
3. Libro IVA Digital / IVA Simple (el TXT oficial solo está en Enterprise o requiere un desarrollo);
4. percepciones SICORE.

Pregunta para el cliente: nombre exacto del formulario, un ejemplo de un mes anterior y el formato (PDF, Excel o TXT de ARCA).

## OCR de facturas
No está en Community (es Enterprise + créditos IAP). Alternativas:
- (a) importar comprobantes de proveedor leyendo el **QR ARCA** del PDF (JSON oficial: CUIT, tipo, PV, número, importe, CAE); esfuerzo S-M, sin costo por página;
- (b) OCA `account_invoice_import_simple_pdf` (no migrado a 19.0);
- (c) API de IA con visión (~0,002-0,02 USD por página).

Recomendado: (a), con (c) como respaldo.

## Cumpleaños
Odoo Community no trae fecha de nacimiento en contactos ni emails de cumpleaños. El módulo OCA `partner_contact_birthdate`
no está en el addons path. Se agregó `birthdate` y un cron diario con plantilla (ES/IT/EN según el idioma del contacto).

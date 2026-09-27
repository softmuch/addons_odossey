# Radio (odossey_radio): análisis y decisiones

Módulo Community (AGPL-3, porque extiende `subscription_oca`) para la gestión comercial y operativa
de una emisora / programa de radio en Argentina.

## Circuito
1. **Oportunidad** (CRM) → **Orden de publicidad** (`sale.order`) con productos del tarifario: formato,
   duración, franja o programa, días, salidas por día.
2. Al confirmar, `subscription_oca` crea el **contrato** (`sale.subscription`). El módulo copia la
   campaña, el N.º de OP, la agencia, la comisión y las fechas de emisión.
3. La **pauta diaria** (`radio.emission`) se planifica desde los contratos en curso, lo hace un cron
   para los próximos N días o se puede lanzar a mano. Respeta:
   - la capacidad (en segundos) de cada tanda;
   - el **límite legal de 14 minutos de publicidad por hora** (Ley 26.522, art. 82 a), configurable;
   - los días y las fechas de cada línea, y la posición en la tanda (primera o última);
   - la rotación de los materiales aprobados y vigentes.
   Lo que no entra queda "sin lugar" para reprogramar.
4. El operador confirma lo emitido. Por defecto, al final del día lo planificado se da por emitido y
   solo se registran las excepciones. Una salida no emitida se puede **reprogramar** en la próxima
   tanda con lugar.
5. **Facturación mensual** con el cron de `subscription_oca`:
   - *Abono fijo (por adelantado)*: se facturan las cantidades del contrato.
   - *Salidas emitidas (mes vencido)*: se factura lo emitido en el período, y se adjunta el
     **certificado de emisión**.
   - En los dos casos: fechas de servicio ARCA = período, referencia = OP / campaña, cliente =
     anunciante o agencia.
6. **Comisión de agencia**: puede ir como descuento en la factura, lo que baja la base del gravamen
   ENACOM (art. 94), o como factura de la agencia, con una liquidación mensual que crea las facturas
   de proveedor en borrador.
7. **Morosidad**: con facturas vencidas hace más de N días, la emisión se suspende sola y se reanuda
   cuando el cliente paga.
8. **Renovaciones**: 30 días antes del fin del contrato se crea una actividad.

## Normativa (verificada)
- **Ley 26.522, art. 82 a**: radio, hasta 14 minutos de publicidad por hora de emisión.
  https://leyes-ar.com/ley_de_servicios_de_comunicacion_audiovisual/82.htm
- **Art. 81**: restricciones de contenido (alcohol, tabaco, salud, juegos de azar, menores). Los
  materiales con restricción piden un número de autorización antes de aprobarse.
- **Gravamen ENACOM (arts. 94-96)**: se calcula sobre la facturación bruta, deduciendo solo las
  bonificaciones y los descuentos facturados. La alícuota sale de la tabla del art. 96 según la
  categoría (A-D) y la banda (AM, FM o baja potencia); se configura en Ajustes.
  https://leyes-ar.com/ley_de_servicios_de_comunicacion_audiovisual/96.htm
- **IVA 21 %** en la publicidad radial. No hay alícuota reducida vigente para radio: la del art. 28
  (Ley de IVA) es para medios gráficos. Queda configurable por producto.
- **Facturación electrónica obligatoria** para los medios (Decreto 1145/2009). El concepto ARCA es
  "Servicios", con fechas de inicio y fin.

## Para confirmar con el cliente / contador
- Si es la **emisora** o un **programa** que alquila espacio. En el segundo caso el gravamen y
  SADAIC no le corresponderían, y aparece un costo mensual de espacio.
- Categoría ENACOM, alícuota de IIBB y si las PNT computan dentro de los 14 minutos (la ley remite al
  Decreto 1225/2010).
- La factura electrónica con CAE no está en Community (`l10n_ar_edi` es Enterprise). En este entorno
  se puede usar `l10n_ar_afipws_fe` (ADHOC, AGPL), que está en `addons_oca_ar`.
- SADAIC / AADI-CAPIF: aranceles y liquidación (no implementado).

## Correcciones sobre `subscription_oca` (hechas dentro del módulo, sin tocar el original)
- Exige una lista de precios: el módulo crea una por empresa y activa la función.
- `_read_group_stage_ids` filtraba las etapas con el dominio de las suscripciones, lo que rompía el
  kanban de cualquier acción filtrada.
- Sin cuenta de ingreso en el producto o la categoría, la línea de factura fallaba: ahora se usa la
  del diario.
- Si todavía no hay facturas, no avanzaba la próxima fecha: en los períodos sin factura (canje,
  suspendido, sin emisiones) se avanza explícitamente.
- Al pasar a "En progreso" pisaba la fecha de inicio: las fechas de la campaña se escriben al final.

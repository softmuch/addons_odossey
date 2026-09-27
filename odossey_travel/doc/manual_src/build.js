const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow,
  TableCell, WidthType, ShadingType, BorderStyle, LevelFormat, Footer, Header, PageNumber,
  PageBreak, TabStopType,
} = require('docx');

const IMG = path.join(__dirname, 'jpg');
const ACCENT = '714B67';      // Odoo purple
const LIGHT = 'F3EEF2';
const NOTE = 'EAF4FB';
const WARN = 'FFF4E0';
const CONTENT_W = 9638;       // A4 with 2 cm margins (DXA)

// ---------- helpers ----------
function runs(text, base = {}) {
  // **bold** and _italic_ inline markup
  const out = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts });
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)], pageBreakBefore: true });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
const bullet = (text, level = 0) => new Paragraph({ numbering: { reference: 'bullets', level }, children: runs(text), spacing: { after: 60 } });
let listInstance = 0;
function steps(items) {
  listInstance += 1;
  return items.map((t) => new Paragraph({ numbering: { reference: 'steps', level: 0, instance: listInstance }, children: runs(t), spacing: { after: 60 } }));
}
function box(text, kind = 'note') {
  const fill = kind === 'warn' ? WARN : NOTE;
  const label = kind === 'warn' ? 'Importante: ' : 'Consejo: ';
  return new Paragraph({
    children: [new TextRun({ text: label, bold: true }), ...runs(text)],
    shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: kind === 'warn' ? 'E0A030' : '3C8DBC', space: 8 } },
    spacing: { before: 120, after: 160 }, indent: { left: 120, right: 120 },
  });
}
function img(name, caption, width = 620) {
  const file = path.join(IMG, name + '.jpg');
  const buf = fs.readFileSync(file);
  // read JPEG size from SOF marker
  let i = 2, w = 1600, h = 1000;
  while (i < buf.length) {
    if (buf[i] !== 0xFF) { i++; continue; }
    const marker = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xC0 && marker <= 0xC3) { h = buf.readUInt16BE(i + 5); w = buf.readUInt16BE(i + 7); break; }
    i += 2 + len;
  }
  let height = Math.round(width * h / w);
  const maxH = 820;
  if (height > maxH) { width = Math.round(width * maxH / height); height = maxH; }
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: 'jpg', data: buf, transformation: { width, height },
        altText: { title: caption, description: caption, name } })],
    }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: caption, italics: true, size: 18, color: '666666' })] }),
  ];
}
function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, isHead, w) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: isHead ? { type: ShadingType.CLEAR, fill: ACCENT, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: runs(text, isHead ? { bold: true, color: 'FFFFFF' } : {}), spacing: { after: 0 } })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((t, k) => cell(t, true, widths[k])) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, k) => cell(t, false, widths[k])) })),
    ],
  });
}
const spacer = () => new Paragraph({ children: [], spacing: { after: 120 } });

// ---------- content ----------
const C = [];
const add = (...xs) => xs.flat().forEach((x) => C.push(x));

// Cover
add(
  new Paragraph({ spacing: { before: 2600 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Manual de usuario', size: 56, bold: true, color: ACCENT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: 'Aplicación Viajes para Odoo 19', size: 36 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Gestión de la agencia · Reservas y pagos online', size: 26, color: '555555' })] }),
  new Paragraph({ spacing: { before: 1800 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Módulos incluidos', bold: true, size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Viajes (odossey_travel) · Viajes – Sitio web (odossey_travel_website)', size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Versión 19.0.1.1.0 · Septiembre 2026', size: 22, color: '555555' })] }),
);

// Contents (static)
add(
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun('Contenido')] }),
  ...[
    '1. Introducción', '2. Primeros pasos', '3. Configuración', '4. Viajes', '5. Calendario e itinerario',
    '6. Reservas', '7. Cancelaciones y reembolsos', '8. Grupos de viaje', '9. Pasajeros y documentación',
    '10. Facturación electrónica (ARCA) y costos', '11. Informes', '12. Oportunidades (CRM)',
    '13. Correos de cumpleaños', '14. Sitio web: reservas y pagos online', '15. Portal del cliente',
    '16. Preguntas frecuentes', '17. Glosario', 'Anexo: puesta en producción',
  ].map((t) => new Paragraph({ children: [new TextRun({ text: t, size: 24 })], spacing: { after: 80 } })),
);

// 1. Introducción
add(
  H1('1. Introducción'),
  P('La aplicación **Viajes** reúne en Odoo todo lo que necesita una agencia de viajes recreativos: los viajes que se ofrecen, los pasajeros, las reservas con seña, los pagos, las cancelaciones, la facturación electrónica y los informes de ganancia. Todo se hace desde un único menú, sin planillas aparte.'),
  P('Está formada por dos módulos que funcionan juntos:'),
  table(['Módulo', 'Para qué sirve'], [
    ['**Viajes**', 'Gestión interna de la agencia: viajes, servicios y precios, reservas, grupos, pasajeros y documentación, seña que congela el precio, cancelaciones con penalidad, facturación ARCA, costos de proveedores, informes de proyección y rentabilidad, calendario, oportunidades y correos de cumpleaños.'],
    ['**Viajes – Sitio web**', 'Venta online: catálogo público de viajes, página de cada viaje, formulario de reserva, pago online de la seña o del total, pago del saldo desde el portal, sección “Mis viajes” para el cliente y botón de arrepentimiento.'],
  ], [2600, 7038]),
  H2('1.1 Conceptos clave'),
  table(['Concepto', 'Qué significa'], [
    ['**Viaje**', 'Una salida concreta: destino, fechas, cupo, servicios incluidos y precio por persona. Ejemplo: “Cataratas del Iguazú – Fin de semana largo”, del 11 al 15 de noviembre.'],
    ['**Servicios**', 'Los componentes del precio (pasaje, alojamiento, traslados, asistencia, comisión de la agencia), cada uno con su costo, su precio de venta y su IVA.'],
    ['**Reserva**', 'La venta a un cliente. En Odoo es una orden de venta vinculada al viaje, con sus pasajeros.'],
    ['**Seña**', 'El pago inicial (un importe fijo o un porcentaje). Al pagarla el precio queda **congelado**: aunque el viaje aumente, ese cliente paga lo pactado.'],
    ['**Saldo**', 'Lo que falta pagar después de la seña. Tiene una fecha límite (días antes de la salida).'],
    ['**Grupo**', 'Varias personas que viajan juntas: una **familia** (paga uno solo) o **amigos** (cada uno paga lo suyo).'],
    ['**Política de cancelación**', 'Las reglas de penalidad según los días que faltan para la salida.'],
  ], [2400, 7238]),
  H2('1.2 El circuito de trabajo'),
  ...steps([
    '**Se arma el viaje**: destino, fechas, cupo, servicios con sus costos y precios, seña y política de cancelación.',
    '**Se abre a la venta** (estado “En venta”) y, si se desea, se **publica en el sitio web**.',
    '**Se cotiza y reserva**: desde la oficina o el cliente reserva solo en la web. Se cargan los pasajeros.',
    '**Se cobra la seña**: se emite la factura (A o B según el cliente) y el precio queda congelado.',
    '**Se cobra el saldo** antes de la fecha límite (en la oficina o online desde el portal).',
    '**Se controla la documentación** de los pasajeros (DNI, pasaporte vigente).',
    '**Se viaja**: el calendario muestra el itinerario; se cargan las facturas de los proveedores.',
    '**Se analiza la ganancia**: el informe de rentabilidad separa IVA, percepciones, Ingresos Brutos, comisiones y costos.',
  ]),
);

// 2. Primeros pasos
add(
  H1('2. Primeros pasos'),
  H2('2.1 Ingresar a la aplicación'),
  P('Desde la pantalla principal de Odoo, hacer clic en el ícono **Viajes**. La aplicación abre en el tablero de viajes, agrupados por estado.'),
  ...img('b02_trips_kanban', 'Tablero de viajes agrupados por estado (Planificación, En venta, Confirmado, Finalizado, Cancelado).'),
  H2('2.2 Los menús'),
  table(['Menú', 'Opciones', 'Uso'], [
    ['**Calendario**', '—', 'Vista mensual de viajes y actividades del itinerario.'],
    ['**Viajes**', 'Viajes · Itinerario', 'Alta y seguimiento de los viajes y de sus actividades.'],
    ['**Ventas**', 'Oportunidades · Reservas · Grupos de viaje', 'Consultas de clientes, reservas y grupos.'],
    ['**Viajeros**', 'Contactos · Pasajeros · Escanear DNI / Pasaporte · Cumpleaños', 'Datos personales y documentación de los viajeros.'],
    ['**Facturación**', 'Facturas de cliente · Costos de proveedores', 'Facturas emitidas y facturas de proveedores de cada viaje.'],
    ['**Informes**', 'Proyección de ingresos · Rentabilidad neta · Ocupación · Oportunidades ganadas / perdidas', 'Análisis del negocio.'],
    ['**Configuración**', 'Ajustes · Servicios · Políticas de cancelación · Correo de cumpleaños · Motivos de pérdida', 'Parámetros de la aplicación.'],
  ], [1900, 3700, 4038]),
  H2('2.3 Perfiles de usuario'),
  P('En **Ajustes > Usuarios**, cada persona recibe un perfil para la aplicación Viajes:'),
  table(['Perfil', 'Puede', 'No puede'], [
    ['**Usuario** (vendedor)', 'Ver viajes, crear y confirmar reservas, facturar la seña, cancelar reservas, cargar pasajeros y escanear documentos, usar el calendario, ver Ocupación y Oportunidades ganadas/perdidas.', 'Modificar precios o costos de los viajes, borrar viajes, ver la Proyección de ingresos y la Rentabilidad neta, entrar en Configuración.'],
    ['**Administrador**', 'Todo lo anterior, más: crear y modificar viajes y precios, ver los informes financieros y cambiar la configuración.', '—'],
  ], [2000, 4400, 3238]),
  H2('2.4 Datos de demostración'),
  P('Para conocer la aplicación sin cargar nada a mano se pueden crear datos de ejemplo de una agencia de Córdoba: 9 viajes (en todos los estados), unas 40 reservas, familias y grupos de amigos, facturas A y B, una nota de crédito, cancelaciones, facturas de proveedores, oportunidades y reservas hechas en el sitio web.'),
  ...steps([
    'Ir a **Configuración > Ajustes**, sección **Viajes**, bloque **Demo**.',
    'Hacer clic en **Cargar datos de demostración**.',
    'Confirmar el aviso. En unos segundos se abre el tablero con los viajes de ejemplo.',
  ]),
  box('Los datos de demostración crean clientes, facturas y pagos reales dentro de la empresa. Usarlos solo en una base de pruebas o de demostración, nunca en la base de producción. No se pueden cargar dos veces.', 'warn'),
  ...img('b24b_settings_demo', 'Botón para cargar los datos de demostración en los Ajustes.'),
);

// 3. Configuración
add(
  H1('3. Configuración'),
  P('Todos los parámetros están en **Configuración > Ajustes**, sección **Viajes**. Solo el administrador puede modificarlos.'),
  ...img('b24_settings', 'Ajustes de la aplicación Viajes.'),
  H2('3.1 Proyección de ingresos'),
  P('Permite estimar cuánto se va a ganar teniendo en cuenta que algunos clientes cancelan. Se define la probabilidad de cancelación según el estado de la reserva:'),
  table(['Parámetro', 'Valor inicial', 'Significado'], [
    ['Tasa de cancelación – Seña pendiente', '25 %', 'Reserva confirmada que todavía no pagó la seña.'],
    ['Tasa de cancelación – Seña pagada', '12 %', 'Reserva con precio congelado.'],
    ['Tasa de cancelación – Pagado', '3 %', 'Reserva totalmente pagada.'],
    ['Incluir cotizaciones en la proyección', 'Sí', 'Suma también las cotizaciones abiertas…'],
    ['Tasa de conversión de cotizaciones', '30 %', '…multiplicadas por la probabilidad de que se concreten.'],
  ], [3600, 1500, 4538]),
  P('El botón **Usar tasa histórica** reemplaza las tres tasas por el porcentaje real de reservas canceladas de la agencia, calculado sobre el historial.'),
  H2('3.2 Rentabilidad neta'),
  table(['Parámetro', 'Uso'], [
    ['Alícuota IIBB (%)', 'Ingresos Brutos que paga la agencia. No figura en las facturas; se estima en el informe de rentabilidad.'],
    ['Base imponible IIBB', '**Ingreso neto** o **Margen** (ingresos menos costos de proveedores), según la actividad declarada por la agencia. Consultar con el contador.'],
    ['Comisiones de cobro (%)', 'Costo estimado de tarjetas, bancos o pasarelas de pago sobre lo facturado.'],
  ], [3000, 6638]),
  H2('3.3 Operaciones'),
  table(['Parámetro', 'Uso'], [
    ['Vigencia del pasaporte después del regreso (meses)', 'Por defecto 6. Si el pasaporte de un pasajero de un viaje internacional vence antes, la aplicación lo avisa.'],
    ['Fechas de servicio ARCA', '**Fechas del viaje** (el período del servicio que se informa en la factura es el del viaje) o **Mes de la factura**.'],
    ['Legajo de la agencia de viajes', 'Número de legajo (Ley 18.829). Se imprime en las cotizaciones.'],
    ['Políticas de cancelación', 'Acceso a las políticas (ver 3.5).'],
  ], [3600, 6038]),
  H2('3.4 Servicios'),
  P('En **Configuración > Servicios** están los productos que componen los viajes. Cada servicio tiene un **Tipo de servicio de viaje** y su **IVA**, que determinan cómo se factura y cómo se clasifica en los informes:'),
  table(['Tipo de servicio', 'IVA habitual (consultar con el contador)'], [
    ['Vuelo internacional', 'Exento'],
    ['Vuelo de cabotaje, transporte de pasajeros en bus', '10,5 %'],
    ['Servicios terrestres en el exterior', 'No gravado'],
    ['Alojamiento, excursiones y servicios en Argentina', '21 %'],
    ['Servicios de la agencia / comisión', '21 %'],
    ['Comisiones de pago / bancarias', 'Solo compras: se usa en las facturas de pasarelas y bancos y se informa como “Comisiones”.'],
  ], [4800, 4838]),
  H2('3.5 Políticas de cancelación'),
  P('En **Configuración > Políticas de cancelación** se definen las penalidades. La aplicación incluye la política **Viaje grupal estándar**:'),
  table(['Días antes de la salida', 'Penalidad'], [
    ['Más de 60 días', 'Se retiene la seña'],
    ['Entre 60 y 31 días', '60 % del total'],
    ['Entre 30 y 8 días', '80 % del total'],
    ['7 días o menos (y no presentación)', '100 % del total'],
  ], [4800, 4838]),
  P('La opción **Seña reembolsable** indica si la seña se devuelve cuando no corresponde penalidad. Se pueden crear otras políticas (por ejemplo, una “flexible”) y asignar a cada viaje la que corresponda.'),
  ...img('b25_policy', 'Política de cancelación con sus reglas.'),
);

// 4. Viajes
add(
  H1('4. Viajes'),
  P('Cada viaje es una salida con fecha. Se crea desde **Viajes > Viajes > Nuevo**.'),
  ...img('b03_trip_form', 'Ficha de un viaje: datos generales, cupo, ocupación y botones de acceso rápido.'),
  H2('4.1 Datos generales'),
  table(['Campo', 'Descripción'], [
    ['Nombre, Destino, País', 'El país determina si el viaje es **Nacional** o **Internacional** (se puede cambiar).'],
    ['Fechas', 'Salida y regreso. Las noches se calculan solas.'],
    ['Moneda', 'ARS o USD. Los viajes al exterior suelen cotizarse en dólares.'],
    ['Lista de precios', 'Opcional: tarifa específica del viaje. Si queda vacía se usa la de la moneda del viaje.'],
    ['Cupo y mínimo de pasajeros', 'El cupo impide vender más lugares. El mínimo indica si el viaje “sale”.'],
    ['Responsable y Coordinador', 'Vendedor a cargo y coordinador del grupo.'],
    ['Lugares reservados / cotizados / disponibles, Ocupación', 'Se calculan solos con las reservas.'],
  ], [3300, 6338]),
  H2('4.2 Pestaña Servicios y precios'),
  P('Se agrega una línea por cada servicio: pasaje, alojamiento, traslados, excursiones, asistencia, comisión de la agencia. Para cada una se indica **Proveedor**, **Costo** y **Precio de venta** por pasajero. Si un servicio se cobra una sola vez por reserva (no por persona), se desmarca **Por pasajero**.'),
  P('Abajo se ven el **precio por persona**, el **costo**, el **margen** y los **costos fijos** del viaje (por ejemplo, el coordinador).'),
  H2('4.3 Pestaña Pagos y cancelación'),
  table(['Campo', 'Descripción'], [
    ['Tipo de seña', '**Importe fijo por pasajero** (ej. USD 930) o **Porcentaje** del total (ej. 30 %).'],
    ['Vencimiento del saldo (días antes)', 'Hasta cuándo se puede pagar el saldo. La fecha límite se calcula sola.'],
    ['Validez de la cotización (horas)', 'Por defecto 48 h. Las cotizaciones web retienen los lugares durante ese tiempo.'],
    ['Política de cancelación', 'Reglas de penalidad del viaje.'],
  ], [3300, 6338]),
  ...img('b04_trip_tab_payments', 'Pestaña Pagos y cancelación.'),
  H2('4.4 Pestañas Itinerario, Pasajeros, Resumen financiero y Cotización'),
  bullet('**Itinerario**: vuelos (aerolínea, número, ruta, escalas, equipaje), alojamientos (estrellas, régimen), traslados y excursiones. Todo aparece en el calendario.'),
  bullet('**Pasajeros**: todos los pasajeros del viaje con su reserva, grupo, pagador, habitación, estado de documentación y estado de pago.'),
  bullet('**Resumen financiero**: reservado, cobrado y saldo pendiente; ingreso y margen esperados; y la rentabilidad neta de lo ya facturado.'),
  bullet('**Cotización**: qué incluye y qué no, la descripción y las condiciones que se imprimen en la cotización.'),
  ...img('b04_trip_tab_passengers', 'Pestaña Pasajeros: documentación y estado de pago de cada uno.'),
  ...img('b04_trip_tab_summary', 'Pestaña Resumen financiero.'),
  H2('4.5 Estados del viaje'),
  table(['Estado', 'Botón para llegar', 'Qué implica'], [
    ['**Planificación**', '(al crearlo)', 'Se arma el viaje. Todavía no se promociona.'],
    ['**En venta**', 'Ventas abiertas', 'Se pueden hacer reservas y publicarlo en la web. Se crea su cuenta analítica.'],
    ['**Confirmado**', 'Confirmar salida', 'Se alcanzó el mínimo y el viaje sale. Se sigue pudiendo vender.'],
    ['**Finalizado**', 'Finalizar', 'El viaje terminó. Ya no admite reservas.'],
    ['**Cancelado**', 'Cancelar viaje', 'No sale. No admite reservas. Con **Volver a planificación** se reactiva.'],
  ], [2000, 2400, 5238]),
  H2('4.6 Botones útiles'),
  bullet('**Nueva reserva**: abre una reserva ya vinculada al viaje.'),
  bullet('**Actualizar precios de las cotizaciones**: si cambió un precio, lo aplica a las cotizaciones abiertas. Las reservas confirmadas **no cambian**: su precio está congelado.'),
  bullet('**Imprimir cotización**: PDF apaisado con itinerario, servicios, precios, seña y condiciones, para enviar al cliente.'),
  bullet('Botones superiores: Calendario, Reservas, Pasajeros, Grupos, Oportunidades, Facturas, Margen neto e **Ir al sitio web**.'),
  box('Si el aviso amarillo “pasajero(s) con documentación faltante o por vencer” aparece en el viaje, hacer clic en **Ver pasajeros** para ver quiénes son.'),
);

// 5. Calendario
add(
  H1('5. Calendario e itinerario'),
  P('El **Calendario** es la vista principal para ver qué pasa cada día: cada viaje aparece como una barra de salida a regreso, y dentro de él sus vuelos, alojamientos, traslados y excursiones, con un color por viaje.'),
  ...img('b05_calendar', 'Calendario de un viaje: la barra del viaje y sus actividades.'),
  bullet('La entrada del viaje en el calendario se actualiza sola al cambiar las fechas del viaje; no se edita a mano.'),
  bullet('Para agregar una actividad: hacer clic en un día del calendario, o **Viajes > Itinerario > Nuevo** (al elegir el viaje se propone el día de salida a las 9:00).'),
  bullet('Desde una actividad, el botón **Viaje** abre la ficha del viaje.'),
  ...img('b05b_calendar_general', 'Calendario general: se ven todos los viajes del mes (aquí, uno en curso).'),
);

// 6. Reservas
add(
  H1('6. Reservas'),
  P('Las reservas están en **Ventas > Reservas**, agrupadas por viaje, con el total, lo pagado, el saldo y el estado de cada una.'),
  ...img('b06b_bookings_open', 'Reservas de un viaje con su estado de pago.'),
  H2('6.1 Estados de una reserva'),
  table(['Estado', 'Cuándo'], [
    ['**Cotización**', 'Todavía no se confirmó. El precio puede cambiar.'],
    ['**Seña pendiente**', 'Confirmada, pero la seña no está paga.'],
    ['**Precio congelado**', 'La seña está paga: el cliente conserva el precio aunque el viaje aumente.'],
    ['**Pagado**', 'Se cobró el total.'],
    ['**Cancelado**', 'Se canceló (ver capítulo 7).'],
  ], [2600, 7038]),
  H2('6.2 Crear una reserva'),
  ...steps([
    'Abrir el viaje y hacer clic en **Nueva reserva** (o **Ventas > Reservas > Nuevo** y elegir el viaje).',
    'Elegir el **Cliente**. Si es una persona, se agrega automáticamente como pasajero.',
    'En la pestaña **Viaje**, agregar los demás **pasajeros**, con tipo (Adulto, Menor, Bebé), **habitación** (Single, Doble, Twin, Triple, Cuádruple) y grupo de habitación.',
    'Hacer clic en **Cargar servicios del viaje**: se completan las líneas con los servicios y precios del viaje para la cantidad de pasajeros.',
    'Enviar la cotización con **Enviar** (sale por correo con el PDF) o imprimirla.',
    'Cuando el cliente acepta, hacer clic en **Confirmar**. La reserva pasa a **Seña pendiente**.',
  ]),
  ...img('b08_new_booking', 'Reserva nueva con los servicios del viaje cargados.'),
  box('Si el cliente no está cargado, se puede usar **Escanear DNI / Pasaporte** (capítulo 9) para crearlo en segundos con los datos del documento.'),
  H2('6.3 Cobrar la seña y congelar el precio'),
  ...steps([
    'En la reserva confirmada, hacer clic en **Facturar seña**. El importe ya viene calculado según el viaje (fijo por pasajero o porcentaje del total con IVA).',
    'Hacer clic en **Crear borrador** y luego **Confirmar** la factura (se emite la factura A o B según la condición frente al IVA del cliente).',
    'Registrar el cobro con **Pagar**.',
    'La reserva pasa a **Precio congelado**: queda registrada la fecha y el importe de la seña.',
  ]),
  ...img('b09_deposit_wizard', 'Facturación de la seña con el importe calculado.'),
  H2('6.4 Cobrar el saldo'),
  P('Antes de la fecha límite, desde la reserva: **Crear factura** (factura final, que descuenta la seña ya facturada), confirmarla y registrar el pago. La reserva pasa a **Pagado**.'),
  H2('6.5 Pestaña Viaje de la reserva'),
  P('Muestra la salida y el regreso, la fecha límite del saldo, la seña requerida, lo pagado, el saldo, si el precio está congelado y la lista de pasajeros con su documentación.'),
  ...img('b07b_booking_travel_tab', 'Pestaña Viaje: pagos, precio congelado y pasajeros.'),
  H2('6.6 Controles automáticos'),
  bullet('No se puede confirmar una reserva si **no hay lugares** suficientes en el viaje.'),
  bullet('No se puede reservar un viaje **Finalizado** o **Cancelado**.'),
  bullet('Una misma persona **no puede estar dos veces** en el mismo viaje.'),
  bullet('Una reserva confirmada **no recalcula su precio**, aunque cambien los precios del viaje.'),
);

// 7. Cancelaciones
add(
  H1('7. Cancelaciones y reembolsos'),
  H2('7.1 Cancelar una reserva'),
  ...steps([
    'En la reserva, hacer clic en **Cancelar reserva**.',
    'Indicar la **fecha de cancelación** y el **motivo**.',
    'El asistente muestra los días que faltan, la política, el porcentaje y el importe de la **penalidad**, lo pagado, el **importe a reembolsar** y, si corresponde, lo que el cliente **todavía adeuda**. La penalidad se puede ajustar a mano.',
    'Confirmar. La reserva queda **Cancelada** con el detalle en el historial y los lugares se liberan.',
  ]),
  ...img('b10_cancel_wizard', 'Asistente de cancelación con el cálculo de la penalidad.'),
  H3('Ejemplo con la política estándar'),
  table(['Situación', 'Resultado'], [
    ['Cancela a 240 días, pagó solo la seña', 'Se retiene la seña. No hay reembolso.'],
    ['Cancela a 45 días, pagó el 30 %', 'Penalidad 60 % del total: se retiene lo pagado y el cliente adeuda la diferencia.'],
    ['Cancela a 20 días, pagó el total', 'Penalidad 80 %: se reembolsa el 20 %.'],
  ], [4200, 5438]),
  H2('7.2 Reembolsar'),
  P('Cuando hay importe a reembolsar, la aplicación crea una **actividad** para el responsable. Para hacerlo: abrir la factura, **Nota de crédito**, confirmarla y registrar el pago de devolución. En los informes la nota de crédito descuenta el ingreso.'),
  H2('7.3 Cancelación del viaje completo por la agencia'),
  P('Si el viaje no llega al mínimo: cancelar cada reserva con penalidad **0 %** (se devuelve todo), emitir las notas de crédito y luego **Cancelar viaje**. En los datos de demostración, “El Calafate y Ushuaia” muestra este caso.'),
  ...img('b11_booking_cancelled', 'Reserva cancelada: penalidad retenida y reembolso en el aviso superior.'),
);

// 8. Grupos
add(
  H1('8. Grupos de viaje'),
  P('En **Ventas > Grupos de viaje** se registran las personas que viajan juntas. Hay dos tipos:'),
  table(['Tipo', 'Reservas', 'Facturación'], [
    ['**Familia (un solo pagador)**', 'Una sola reserva a nombre del responsable, con todos los integrantes como pasajeros.', 'Una sola factura al responsable.'],
    ['**Amigos (cada uno paga)**', 'Una reserva por integrante.', 'Una factura por integrante, todas vinculadas al grupo.'],
  ], [2800, 3800, 3038]),
  ...steps([
    'Crear el grupo: nombre, viaje, tipo y responsable/pagador.',
    'Agregar los **integrantes** en la pestaña correspondiente.',
    'Hacer clic en **Crear reservas**. Si más tarde se suma alguien, al volver a hacer clic se crea solo la reserva que falta.',
    'Confirmar las reservas y usar **Crear facturas** para facturarlas según el tipo de grupo.',
  ]),
  P('El grupo muestra el total, lo pagado y el saldo de todas sus reservas.'),
  ...img('b12_group_friends', 'Grupo de amigos: cada integrante con su reserva.'),
);

// 9. Pasajeros
add(
  H1('9. Pasajeros y documentación'),
  H2('9.1 Lista de pasajeros'),
  P('**Viajeros > Pasajeros** reúne a todos los pasajeros de las reservas activas, con su documentación y estado de pago. Se puede filtrar y agrupar por viaje.'),
  table(['Documentación', 'Significado'], [
    ['**OK**', 'Documentación correcta.'],
    ['**Falta el pasaporte**', 'Viaje internacional sin pasaporte cargado.'],
    ['**Pasaporte por vencer**', 'El pasaporte vence antes de los meses de vigencia exigidos después del regreso (6 por defecto).'],
    ['**Falta el DNI**', 'Viaje nacional sin número de documento.'],
  ], [3000, 6638]),
  ...img('b13_passengers', 'Pasajeros de un viaje con avisos de documentación.'),
  H2('9.2 Escanear DNI o pasaporte'),
  P('Para cargar clientes sin tipear y sin errores: **Viajeros > Escanear DNI / Pasaporte** (también desde la ficha del contacto y desde la reserva).'),
  bullet('**DNI argentino**: se lee el código de barras del frente con un lector 2D (tipo pistola) o con la **cámara** del celular o notebook.'),
  bullet('**Pasaporte o documento extranjero**: se pegan o escanean las dos o tres líneas de la parte inferior (zona MRZ).'),
  P('La aplicación muestra los datos leídos (nombre, apellido, sexo, fecha de nacimiento, nacionalidad, número y vencimiento) y los compara con los contactos existentes: crea un contacto nuevo o actualiza el existente. Si se abrió desde una reserva, agrega a la persona como pasajero.'),
  box('Hay que marcar **El pasajero consiente el tratamiento de sus datos personales (Ley 25.326)**; sin el consentimiento no se guarda nada. Si el lector escribe caracteres extraños, verificar que su distribución de teclado sea la misma que la del sistema operativo.', 'warn'),
  ...img('b14_scan_dni', 'Lectura del código de barras de un DNI.'),
  H2('9.3 Ficha del contacto'),
  P('La pestaña **Viajero** de cada contacto tiene los datos personales (nacimiento, edad, sexo, nacionalidad, trámite y ejemplar del DNI) y del pasaporte (número, país emisor, fechas de emisión y vencimiento). El botón **Viajes** muestra en qué viajes participó.'),
  ...img('b15_contact_traveller', 'Pestaña Viajero de un contacto.'),
);

// 10. Facturación
add(
  H1('10. Facturación electrónica (ARCA) y costos'),
  H2('10.1 Facturas de cliente'),
  P('Las facturas se generan desde las reservas y usan la localización argentina de Odoo:'),
  bullet('El tipo de comprobante se elige solo según la condición del cliente: **Factura B** a consumidor final, **Factura A** a Responsables Inscriptos y monotributistas.'),
  bullet('Cada servicio lleva su IVA (exento, no gravado, 10,5 % o 21 %), como en las facturas de las agencias.'),
  bullet('Si la agencia es agente de percepción, las **percepciones** (IIBB, IVA, Ganancias) se agregan en las líneas de la factura y el informe de rentabilidad las muestra por separado.'),
  bullet('El período del servicio informado a ARCA puede ser el de las fechas del viaje (ver Ajustes).'),
  bullet('**Facturación > Facturas de cliente** muestra las facturas agrupadas por viaje.'),
  ...img('b19_invoice_A', 'Factura A de seña a una empresa, con IVA y percepción IIBB Córdoba.'),
  H2('10.2 Costos de proveedores'),
  P('En **Facturación > Costos de proveedores** se cargan las facturas de mayoristas, transportes, hoteles, etc., indicando el **Viaje** al que corresponden. Así el informe de rentabilidad descuenta los costos reales. Las facturas de pasarelas de pago y bancos (servicio de tipo “Comisiones de pago / bancarias”) se informan como **Comisiones**.'),
  ...img('b20_bills', 'Costos de proveedores agrupados por viaje.'),
);

// 11. Informes
add(
  H1('11. Informes'),
  P('Todos los informes se pueden ver como tabla dinámica, gráfico o lista, filtrar, agrupar y exportar a Excel.'),
  H2('11.1 Proyección de ingresos'),
  P('Estima cuánto va a ingresar, considerando que algunas reservas se cancelan. Para cada reserva:'),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: 'Ingreso esperado = Total × (1 − p) + seña retenida × p', bold: true })] }),
  P('donde _p_ es la tasa de cancelación según el estado (Ajustes 3.1). Las reservas canceladas aportan la penalidad efectivamente retenida y las cotizaciones se ponderan por la tasa de conversión. También se estima el costo esperado.'),
  ...img('b21_forecast', 'Proyección de ingresos por mes de salida.'),
  H2('11.2 Rentabilidad neta'),
  P('Parte de lo realmente facturado y separa lo que no es ganancia de la agencia:'),
  table(['Columna', 'Qué incluye'], [
    ['Facturado bruto', 'Total de las facturas del viaje.'],
    ['IVA', 'IVA de las facturas (se paga a ARCA).'],
    ['Percepciones', 'Percepciones cobradas (se ingresan al fisco).'],
    ['Ingreso neto', 'Facturado sin IVA ni percepciones.'],
    ['Costos de proveedores', 'Facturas de proveedores del viaje.'],
    ['Comisiones', 'Comisiones de cobro estimadas y facturas de pasarelas/bancos.'],
    ['Ingresos Brutos (IIBB)', 'Estimado con la alícuota y la base de los Ajustes.'],
    ['**Ganancia neta**', 'Ingreso neto − costos − comisiones − IIBB.'],
  ], [3200, 6438]),
  ...img('b22_profitability', 'Rentabilidad neta por viaje.'),
  P('Desde el viaje se puede imprimir el **PDF de rentabilidad** con el mismo detalle.'),
  H2('11.3 Ocupación'),
  P('Lugares reservados y porcentaje de ocupación de cada viaje, para decidir si un viaje sale o si conviene reforzar la venta.'),
  ...img('b23_occupancy', 'Ocupación de los viajes.'),
  H2('11.4 Oportunidades ganadas / perdidas'),
  P('Cuántas consultas se convirtieron en venta y cuántas se perdieron, por viaje y por motivo.'),
);

// 12 CRM + 13 birthdays
add(
  H1('12. Oportunidades (CRM)'),
  P('**Ventas > Oportunidades** usa el CRM de Odoo con datos de viaje: **Viaje**, **Pasajeros esperados** y **Destino deseado** (cuando todavía no hay un viaje armado). Las etapas son Nuevo, Calificado, Propuesta y Ganado.'),
  P('Desde una oportunidad, el botón **Nueva cotización** crea la reserva ya vinculada al viaje y al cliente.'),
  ...img('b17_crm', 'Oportunidades por etapa.'),
  H1('13. Correos de cumpleaños'),
  P('Todos los días la aplicación envía un saludo por correo a los contactos que cumplen años (en su idioma: español, italiano o inglés). Nunca envía dos saludos el mismo día.'),
  bullet('Se activa o desactiva en **Ajustes > Correos de cumpleaños**; allí también se elige y edita la plantilla del correo.'),
  bullet('**Viajeros > Cumpleaños** lista los cumpleaños del mes, con la edad que cumplen.'),
  bullet('La fecha de nacimiento se carga en la pestaña **Viajero** del contacto o con el escáner de DNI.'),
  ...img('b16_birthdays', 'Cumpleaños del mes.'),
);

// 14 Website
add(
  H1('14. Sitio web: reservas y pagos online'),
  P('El módulo **Viajes – Sitio web** permite que los clientes vean los viajes, reserven y paguen desde el sitio de la agencia, sin intervención del personal. Las reservas online aparecen en **Ventas > Reservas** como cualquier otra.'),
  H2('14.1 Publicar un viaje'),
  P('En la ficha del viaje, pestaña **Sitio web**:'),
  table(['Campo', 'Uso'], [
    ['**Publicado en el sitio web**', 'Muestra el viaje en el catálogo. Solo se pueden reservar online los viajes En venta o Confirmados, con fecha futura y lugares libres.'],
    ['Reservable online / Lugares disponibles online', 'Indicadores: lugares libres menos los retenidos por cotizaciones web vigentes.'],
    ['Máx. pasajeros por reserva online', 'Cuántas personas puede reservar un cliente en una sola compra (por defecto 8).'],
    ['**Seña online**', 'Si está marcada, el cliente puede pagar solo la seña (congela el precio) y el saldo después. Si no, debe pagar el total.'],
    ['**Moneda de pago online**', '**Moneda de la empresa** (pesos, convertidos a la cotización del día; necesario para Mercado Pago) o **Moneda del viaje** (por ejemplo, dólares por tarjeta o transferencia).'],
    ['Descripción web', 'Texto de la página del viaje. Si está vacío se usa la descripción del viaje.'],
  ], [3400, 6238]),
  ...img('b04_trip_tab_website', 'Pestaña Sitio web del viaje.'),
  H2('14.2 El catálogo'),
  P('La página **/viajes** muestra los viajes publicados con foto, destino, fechas, noches, precio por persona y el importe de la seña. Se puede buscar por destino, mes de salida y tipo (nacional/internacional). Los viajes con pocos lugares muestran un aviso y los completos, **Agotado**. Si el precio no es en pesos se indica la moneda (por ejemplo, USD).'),
  ...img('w01_catalogue', 'Catálogo de viajes en el sitio web.', 560),
  H2('14.3 La página del viaje'),
  P('Incluye qué contiene el viaje, la descripción, el itinerario día por día, las condiciones y la política de cancelación, el precio por persona (con la conversión si corresponde), la seña que congela el precio, la fecha límite del saldo y el selector de pasajeros.'),
  ...img('w02_trip_page', 'Página de un viaje.', 520),
  ...img('w03_sold_out', 'Viaje agotado: no se ofrece la reserva.'),
  H2('14.4 Cómo reserva el cliente'),
  ...steps([
    'Elige la cantidad de pasajeros y hace clic en **Reservar ahora**.',
    'Completa los datos del **titular** (nombre, correo, teléfono, DNI/CUIT, condición frente al IVA) y de los **pasajeros** (nombre, DNI, fecha de nacimiento), la habitación y comentarios. Si el titular viaja, es el pasajero 1.',
    'Acepta las condiciones de reserva y la política de cancelación.',
    'Hace clic en **Continuar al pago**.',
  ]),
  ...img('w04_booking_form', 'Formulario de reserva.', 560),
  P('El sistema valida que haya lugares, que no se repita una persona y que el correo sea válido. Si ya existe un cliente con el mismo DNI y correo, se usa su ficha; si el cliente reserva estando conectado a su cuenta, se usan sus datos.'),
  H2('14.5 El pago'),
  P('Se abre la ventana de pago de Odoo con dos opciones: **Anticipo** (la seña) o **Importe completo**, y los medios de pago configurados (Mercado Pago, tarjeta, transferencia bancaria…).'),
  ...img('w05_payment_modal', 'Ventana de pago: seña o importe completo.'),
  P('Cuando el pago se aprueba, automáticamente:'),
  bullet('la reserva se **confirma**;'),
  bullet('se emite y publica la **factura** (de seña o final);'),
  bullet('el precio queda **congelado** y el cliente recibe la confirmación por correo.'),
  P('Si paga por **transferencia**, la reserva queda pendiente hasta que la agencia confirme la recepción del dinero.'),
  ...img('w06_order_deposit_paid', 'La reserva después de pagar la seña: precio congelado, saldo y botón para pagarlo.', 560),
  H2('14.6 Lugares retenidos y sobreventa'),
  bullet('Mientras una cotización web está vigente (según la validez del viaje, 48 h por defecto) sus lugares quedan **retenidos**. Si vence sin pago, se liberan.'),
  bullet('Antes de cobrar se vuelve a controlar el cupo: si mientras tanto el viaje se completó, el pago **no se procesa** y el cliente ve el aviso.'),
  bullet('Si igualmente entra un pago cuando ya no hay lugar, el dinero no se pierde: la reserva queda sin confirmar y se crea una actividad para que la agencia resuelva (reubicación o reembolso).'),
  H2('14.7 Botón de arrepentimiento'),
  P('Exigido en Argentina para las ventas online (Resolución 424/2020). Aparece en el pie de todas las páginas y lleva a **/viajes/arrepentimiento**: el cliente ingresa el número de reserva y su correo dentro de los 10 días corridos de la compra. La solicitud queda registrada en la reserva con una actividad para la agencia, que gestiona la devolución.'),
  ...img('w07_withdrawal', 'Botón de arrepentimiento.'),
  H2('14.8 Las reservas online en la oficina'),
  P('Las reservas hechas en la web se ven en **Ventas > Reservas** (origen “Sitio web”) y en la pestaña Sitio web del viaje. Se trabajan igual que las demás: cancelación, facturación del saldo, documentación.'),
  ...img('b27_online_bookings', 'Reservas de un viaje, incluidas las hechas online.'),
);

// 15 Portal
add(
  H1('15. Portal del cliente'),
  P('Cada cliente puede tener acceso a **Mi cuenta** en el sitio web para ver sus viajes, pagar el saldo y descargar sus facturas.'),
  H2('15.1 Dar acceso a un cliente'),
  ...steps([
    'Abrir el contacto del cliente.',
    'Menú **Acción** (engranaje) > **Conceder acceso al portal**.',
    'Hacer clic en **Otorgar acceso**. El cliente recibe un correo para crear su contraseña.',
  ]),
  ...img('b26_portal_wizard', 'Conceder acceso al portal.'),
  H2('15.2 Lo que ve el cliente'),
  bullet('**Mis viajes**: sus reservas con viaje, salida, pasajeros, total, saldo, estado y el botón **Pagar** o **Pagar saldo**.'),
  bullet('El detalle de cada reserva, con pasajeros, pagos y la fecha límite del saldo.'),
  bullet('**Sus facturas**, para descargar en PDF.'),
  bullet('Si reserva un viaje estando conectado, sus datos ya aparecen completos.'),
  P('Cada cliente ve solamente sus propias reservas.'),
  ...img('w08_portal_home', 'Mi cuenta: acceso a “Mis viajes”.'),
  ...img('w09_my_trips', 'Mis viajes: reservas del cliente y pago del saldo.'),
);

// 16 FAQ
add(
  H1('16. Preguntas frecuentes'),
  H3('¿Por qué la seña no coincide con el 30 % del precio de lista?'),
  P('Porque el porcentaje se calcula sobre el **total con IVA** de la reserva, que es lo que paga el cliente.'),
  H3('Cambié el precio de un viaje, ¿se actualizan las reservas?'),
  P('Las **cotizaciones** se actualizan con **Actualizar precios de las cotizaciones**. Las reservas **confirmadas no**: su precio quedó pactado.'),
  H3('¿Por qué no puedo confirmar una reserva?'),
  P('Porque no hay lugares suficientes, el viaje está Finalizado o Cancelado, faltan pasajeros o alguno ya está en otra reserva del mismo viaje. El mensaje indica la causa.'),
  H3('El viaje no aparece en el sitio web'),
  P('Verificar que esté **Publicado**, en estado **En venta** o **Confirmado**, con fecha de salida futura y con servicios cargados. Si está completo se muestra como Agotado.'),
  H3('Un pasajero figura con “Pasaporte por vencer”'),
  P('Su pasaporte vence antes de los meses exigidos después del regreso. Se corrige cargando el pasaporte nuevo (a mano o escaneándolo).'),
  H3('¿Cómo devuelvo dinero de una cancelación?'),
  P('Con la **Nota de crédito** de la factura y el pago de devolución (capítulo 7). La actividad creada al cancelar recuerda el importe.'),
  H3('¿El IVA y las percepciones cuentan como ganancia?'),
  P('No. El informe de rentabilidad los separa porque se ingresan al fisco.'),
  H3('¿Puedo vender un viaje en dólares y cobrarlo en pesos online?'),
  P('Sí: en la pestaña Sitio web elegir **Moneda de la empresa**. El precio se convierte a la cotización del día y queda congelado con la seña.'),
);

// 17 Glosario
add(
  H1('17. Glosario'),
  table(['Término', 'Definición'], [
    ['ARCA', 'Agencia de Recaudación y Control Aduanero (ex AFIP).'],
    ['Base doble', 'Precio por persona compartiendo habitación doble.'],
    ['CUIT / CUIL', 'Identificación tributaria / laboral.'],
    ['IIBB', 'Ingresos Brutos, impuesto provincial.'],
    ['MRZ', 'Zona de lectura mecánica: las líneas inferiores del pasaporte.'],
    ['PDF417', 'Código de barras del frente del DNI argentino.'],
    ['Percepción', 'Anticipo de impuesto que el agente cobra en la factura y deposita al fisco.'],
    ['Precio congelado', 'Precio pactado al pagar la seña; no cambia aunque aumente el viaje.'],
    ['Cotización', 'Reserva todavía no confirmada.'],
    ['Portal', 'Sección “Mi cuenta” del sitio web para los clientes.'],
  ], [2600, 7038]),
);

// Annex
add(
  H1('Anexo: puesta en producción'),
  P('Antes de usar la aplicación con clientes reales conviene completar:'),
  ...steps([
    '**Datos de la empresa**: razón social, CUIT, condición IVA, Ingresos Brutos, inicio de actividades, logo (Ajustes > Empresas).',
    '**Facturación electrónica**: certificado y puntos de venta de ARCA.',
    '**Medios de pago online**: credenciales de Mercado Pago (o el proveedor elegido) y datos bancarios para transferencias (Facturación / Sitio web > Proveedores de pago).',
    '**Sitio web**: logo, textos institucionales, datos de contacto, imágenes de cada viaje y textos legales de condiciones y cancelación.',
    '**Ajustes de Viajes**: tasas de cancelación, alícuota y base de IIBB, comisiones, legajo de la agencia.',
    '**Servicios y políticas**: revisar los tipos de servicio e IVA con el contador y las políticas de cancelación con el área legal.',
    '**Usuarios**: asignar los perfiles Usuario o Administrador.',
  ]),
  box('Los datos de demostración sirven para capacitar al equipo en una base de pruebas. En la base de producción empezar sin ellos.', 'warn'),
);

// ---------- document ----------
const doc = new Document({
  creator: 'Odossey', title: 'Manual de usuario – Viajes', description: 'Manual de los módulos Viajes y Viajes – Sitio web',
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, color: ACCENT, font: 'Calibri' },
        paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, color: '333333', font: 'Calibri' },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, color: ACCENT, font: 'Calibri' },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } },
      ] },
      { reference: 'steps', levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } },
      ] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: 'Manual de usuario – Aplicación Viajes', size: 16, color: '888888' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: 'Página ', size: 16, color: '888888' }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '888888' }), new TextRun({ text: ' de ', size: 16, color: '888888' }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: '888888' })] })] }) },
    children: C,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = process.argv[2] || path.join(__dirname, 'Manual_Viajes.docx');
  fs.writeFileSync(out, buf);
  console.log('written', out, buf.length);
});

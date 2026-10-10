# odossey_veterinary — análisis y decisiones

*Octubre 2026. Módulo veterinario para Odoo 19 **Community** (ninguna dependencia Enterprise).*

## Origen

- **Referencia funcional:** `veterinary_clinic` de Odoo S.A. Es un módulo "industry" con licencia **OEEL-1**, hecho con datos de Studio y con dependencias Enterprise (Studio, Planning, Appointment, Documents/Sign, Knowledge, CRM Enterprise, FSM). **No se copió código ni datos**: solo sirvió para entender el flujo esperado.
- **Investigación de mercado y normativa:**
  - Análisis de la referencia: `tools_claude/veterinary/analisis_veterinary_clinic.md`.
  - Benchmark de ezyVet, Provet, IDEXX Neo, Covetrus, Vetspire, Digitail, Shepherd, QVET, GVet, Aturna, VetApp y otros, más normativa argentina e italiana: `tools_claude/veterinary/investigacion_mercado.md`.
  - Datos maestros: `tools_claude/veterinary/datos_maestros_ar.json`.

## Qué reemplaza a cada pieza Enterprise de la referencia

| Referencia (Enterprise) | Este módulo (Community) |
|---|---|
| Studio (`x_pets`, `x_species`…) | Modelos Python reales (`vet.pet`, `vet.species`…) |
| Appointment | `calendar.event` + tipos de turno, consultorios y estado de la visita |
| Sign | Firma propia (widget en pantalla o `portal.signature_form`) con huella SHA-256 |
| Documents | Adjuntos (`ir.attachment`) en la consulta |
| Knowledge | Ayudas en cada campo, textos de ejemplo en Ajustes y manual de usuario |
| Planning / FSM | Agenda por veterinario y consultorio, y turno "a domicilio" |

## Alcance v1

- **Paciente:** especie, raza (filtrada por especie), sexo, castración, nacimiento (o estimado), edad, pelaje, microchip ISO de 15 dígitos, curva de peso con condición corporal, temperamento, alertas por gravedad, alergias, enfermedades crónicas y fallecimiento.
- **Consulta (SOAP):**
  - Signos vitales con rangos de referencia para perro y gato, y aviso si salen de rango.
  - Anamnesis, examen físico, diagnósticos codificados y plan.
  - Aviso automático si el diagnóstico es una zoonosis o una enfermedad de denuncia obligatoria.
  - Plantillas por motivo de consulta.
  - Cargos que pasan a una orden de venta al cerrar la consulta (configurable), con el lote del medicamento usado.
  - Al cerrar, la historia clínica queda bloqueada.
- **Vacunación y desparasitación:**
  - El producto define el plan: dosis iniciales, intervalo, refuerzo o repetición.
  - El sistema calcula la próxima dosis y reemplaza la anterior del mismo grupo.
  - Estados: al día, por vencer y vencida.
  - Recordatorio diario por email, agrupado por tutor, y botón de WhatsApp (`wa.me`, número argentino con el 9).
  - Carnet de vacunación y certificado antirrábico (Ley 22.953).
- **Recetas:**
  - Simple o **archivada**: obligatoria si el medicamento es controlado; se imprimen original para la farmacia y duplicado para el tutor.
  - Numeración propia para cada tipo, con matrícula y colegio del profesional y firma escaneada.
  - Vigencia, código **CUVE** de la RVE (Res. SENASA 654/2026) y huella de integridad.
  - Una vez emitida, la receta es inmodificable.
- **Libro de controlados:** cada uso de ketamina, diazepam, opioides, etc. queda registrado con paciente, lote y profesional.
- **Internación:**
  - Hoja de tratamiento por horario, con asistente "cada N horas durante X días".
  - Tablero de tareas pendientes y atrasadas.
  - Cargo por día iniciado, epicrisis y PDF de alta.
- **Consentimientos:** plantillas de cirugía y anestesia, eutanasia e internación con placeholders. Se firman en pantalla o desde el portal y quedan bloqueados con su huella.
- **Laboratorio:** 14 paneles con analitos, rangos orientativos para perro y gato, marcado de valores fuera de rango y PDF.
- **Certificados:** salud, viaje (validez de 10 días para el CVI de SENASA), desparasitación, castración y defunción.
- **Portal del tutor:** sus mascotas, el carnet de vacunas, los próximos turnos, recetas, certificados y la firma de consentimientos.
- **Datos maestros argentinos**, traducidos al inglés, español e italiano:

| Dato | Cantidad |
|---|---|
| Especies | 20 |
| Razas | 45 |
| Enfermedades | 38 |
| Alertas, alergias y comportamientos | 33 |
| Vacunas | 19 |
| Medicamentos (los controlados marcados) | 71 |
| Insumos y productos de venta | 36 |
| Servicios | 55 |
| Paneles de laboratorio | 14 |
| Plantillas de consentimiento | 3 |

- **Precios de referencia:** los aranceles en ARS de 2026 de los servicios solo se aplican si la empresa factura en pesos.

## Decisiones

- **Tutor = contacto (`res.partner`):** se reutiliza toda la facturación y la localización argentina (ARCA) sin código extra.
- **Medicamentos y vacunas = productos:** se usan el stock, los lotes y los vencimientos (`product_expiry`) y las compras estándar.
- **Impuestos:** el módulo no fija alícuotas de IVA, porque dependen del producto y del contador.
- **Dosis de referencia:** quedan en inglés con abreviaturas veterinarias universales (q12h, PO, SC, mg/kg). Son orientativas y el profesional siempre las confirma.

## Para confirmar con el cliente

1. **IVA:** alícuota de medicamentos y alimentos (¿10,5 % o 21 %?). Los servicios van al 21 %.
2. **Laboratorios:** quién comercializa en Argentina Algen, Acedan, Contal, Quantum, Total Full y Basken. Están marcados para verificar en el JSON.
3. **Libro recetario:** si la provincia exige un libro recetario o un registro de psicotrópicos con un formato específico.
4. **RVE de SENASA:** qué productos alcanza y cuál es el cronograma. Hoy el CUVE se carga a mano; la integración queda para cuando haya un servicio web público.
5. **Rangos de laboratorio:** ajustarlos al analizador o laboratorio que use la clínica.
6. **Reserva online de turnos** desde el sitio web: no está en la v1 y se puede reutilizar la de dentOS.
7. **Peluquería con ficha propia, guardería/hotel y planes de salud por cuota** (`subscription_oca`): previstos para la v2.

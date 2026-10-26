# Odossey Ophthalmology — análisis funcional y decisiones

Módulo para clínicas oftalmológicas de Argentina. Solo usa módulos Community (LGPL-3):
- `mail`, `contacts`, `portal`, `calendar`;
- `sale_management`, `sale_stock`, `product_expiry`;
- `purchase`, `account`.

Está traducido a español (es_AR), italiano e inglés.

Fuentes del relevamiento:
- `tools_claude/ophthalmology/investigacion_mercado.md` (softwares de oftalmología, Omnia Salud, normativa);
- `tools_claude/ophthalmology/datos_maestros_ar.json` (datos maestros).

## Flujo cubierto

| Paso | Dónde |
|---|---|
| Turno (por profesional, tipo, sala, obra social, autorización/token) | Recepción › Agenda |
| Llegada, pre-consulta, dilatación, estudios, consulta, atendido, se retiró, ausente, a reprogramar | Recepción › Sala de espera (kanban con tiempo de espera) |
| Pre-consulta del técnico: AV, lensometría, autorrefracción, queratometría, PIO, paquimetría | Consulta › pestaña Pre-consulta |
| Consulta del médico, por ojo: refracción, biomicroscopía (LOCS), gonioscopía, fondo de ojo (copa/disco) | Consulta |
| Diagnósticos CIE-10, plan e indicaciones; próximo control sugerido según el diagnóstico | Consulta › Diagnóstico y plan |
| Estudios complementarios: OCT, campo visual, biometría, topografía, endotelio… | Clínica › Estudios |
| Receta de anteojos y de lentes de contacto, generada desde la refracción | Clínica › Anteojos y lentes de contacto |
| Receta de medicamentos con diagnóstico; código CUIR de la plataforma habilitada | Clínica › Recetas |
| Cirugía en quirófano: autorización, consentimiento, checklist OMS, LIO con número de serie, protocolo, tarjeta de implante, controles post-op | Cirugía |
| Facturación al paciente (presupuesto / factura) y a la obra social (prestaciones y liquidación mensual) | Facturación |
| Portal del paciente: turnos, recetas, informes, certificados, firma del consentimiento | /my/ophthalmology |

## Funcionalidades tomadas de Omnia Salud

**Incluidas:**
- **Agenda:** estados de turno (Pendiente, Confirmado, Recepcionado, Atendiendo, Atendido, Retirado, Cancelado, A reprogramar) y autorizaciones por turno.
- **Historia clínica:** consentimientos y certificados; recordatorios por email y WhatsApp.
- **Obras sociales:** obra social, plan y arancel convenido; aumento masivo de aranceles; prefacturación por obra social (liquidación) con débitos y refacturación.
- **Estudios:** pedido y resultado.
- **Stock:** consumo de insumos con lote.
- **Portal del paciente.**

**Pendientes (requieren integración o definición):**
- Receta electrónica emitida desde una plataforma registrada en ReNaPDiS. Por ahora el módulo guarda el CUIR que devuelve la plataforma externa.
- Validación online de afiliados (Traditum, Activia, token de cada prepaga) y órdenes electrónicas de PAMI.
- Factura electrónica ARCA: en Community requiere los módulos de localización argentina de la comunidad.
- Liquidación de honorarios a médicos; teleconsulta; integración con equipos (DICOM / HL7); dictado por voz.

## Diferencial frente a Omnia

Omnia no tiene examen oftalmológico estructurado; este módulo sí:
- examen por ojo;
- gráfico de evolución de la PIO;
- cálculo y registro de LIO con trazabilidad;
- checklist quirúrgico;
- tarjeta de implante.

## Normativa considerada (a validar por el asesor legal de la clínica)

- **Ley 26.529 / 26.742:**
  - la consulta cerrada no se modifica, las correcciones se cargan como adendas, y no se borra historia clínica cerrada;
  - consentimiento informado con firma, hash e IP, revocable;
  - certificados y copia para el paciente.
- **Ley 25.326:** registro de accesos a la historia clínica, permisos por rol (recepción no ve el contenido clínico detallado) y portal con reglas por paciente.
- **Ley 27.553 y sus decretos:** desde 2025 la receta válida es la electrónica de una plataforma registrada. El módulo imprime una constancia y guarda el CUIR.
- **IVA:** las prestaciones facturadas a obras sociales se generan sin IVA. La condición impositiva del paciente particular depende de la clínica: confirmar con el contador.

## Preguntas para la clínica

1. ¿Qué obras sociales y prepagas atienden? ¿Con qué aranceles y códigos de nomenclador, y cuál es el coseguro de cada plan?
2. ¿Quién valida afiliados y cómo (web de cada obra social, Traditum, token)?
3. ¿Qué plataforma de receta electrónica usan los médicos?
4. ¿Qué equipos tienen (OCT, campímetro, biómetro, topógrafo)? ¿Exportan PDF o DICOM?
5. Paquetes quirúrgicos particulares: ¿incluyen la LIO y los insumos? ¿Cuántos controles post-operatorios incluyen?
6. ¿Liquidan honorarios a los médicos por porcentaje o por prestación?
7. Textos de los consentimientos: validar con el área médica y legal (los incluidos son borradores).

## Datos maestros incluidos

- 88 diagnósticos CIE-10 (H00–H59 y otros relevantes), con intervalo de control para los crónicos;
- 50 servicios de consulta y estudio con código de Nomenclador Nacional / CAO;
- 36 procedimientos quirúrgicos con duración, anestesia, controles post-op y consentimiento;
- 54 medicamentos oftálmicos disponibles en Argentina;
- 10 tipos de LIO con número de serie y vencimiento, y 24 insumos quirúrgicos con lote;
- 6 plantillas de consentimiento;
- 21 obras sociales y prepagas;
- 14 tipos de turno.

Los precios particulares son orientativos (ARS, octubre de 2026) y solo se aplican si la empresa factura en pesos.

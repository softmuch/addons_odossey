# Manual de usuario – fuentes

Regenerar el manual (`../Manual_Viajes_Odoo19.docx` / `.pdf`) después de cambios en la interfaz:

1. Base de demostración limpia con los datos demo cargados (Ajustes > Viajes > Cargar datos de
   demostración), servidor en `http://localhost:8072` (ver `BASE` en `t_common.py`).
2. Capturas: `python3 manual_shots.py` y `python3 manual_shots2.py` (Playwright). Ajustar `SP` en
   `t_common.py`: las imágenes se guardan en `$SP/manual/`.
3. Convertir las PNG a JPEG en `manual/jpg/` (ancho máx. 1600 px).
4. `npm install docx@9` y `node build.js Manual_Viajes_Odoo19.docx` (lee las imágenes de `jpg/`
   junto al script).
5. PDF: `soffice --headless --convert-to pdf Manual_Viajes_Odoo19.docx`.

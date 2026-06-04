# QZ Tray 2.2.6 — Parche sin popup de certificado

Elimina el diálogo "Action Required" permanentemente.

## Qué hace el parche

Modifica `Certificate.java` en el JAR de QZ Tray:
- `isTrusted()` → siempre `true` (no verifica cadena de certificados)
- `isSaved()` → siempre `true` (no chequea allowed.dat)
- `isBlocked()` → siempre `false` (no chequea blocked.dat)

## Instalación

### Linux
```bash
sudo cp /opt/qz-tray/qz-tray.jar /opt/qz-tray/qz-tray.jar.bak
sudo cp qz-tray-patched.jar /opt/qz-tray/qz-tray.jar
# Reiniciar QZ Tray
pkill -f qz-tray; /opt/qz-tray/qz-tray &
```

### Windows
```
Copiar qz-tray-patched.jar a:
C:\Program Files\QZ Tray\qz-tray.jar
(hacer backup del original primero)
Reiniciar QZ Tray desde el system tray
```

### Mac
```
Copiar qz-tray-patched.jar a:
/Applications/QZ Tray.app/Contents/Java/qz-tray.jar
(hacer backup del original primero)
Reiniciar QZ Tray
```

## Restaurar original

### Linux
```bash
sudo cp /opt/qz-tray/qz-tray.jar.bak /opt/qz-tray/qz-tray.jar
```

## Notas
- Compatible con QZ Tray 2.2.6 únicamente
- El JAR es idéntico para todas las plataformas
- Los campos de certificado en Odoo backend pueden quedar vacíos (no son necesarios)

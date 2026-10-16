# Odossey || Payment Provider: PowerTranz

Proveedor de pago PowerTranz (BAC Credomatic / First Atlantic Commerce) para el eCommerce de Odoo 18.

- El cliente paga en la **página alojada de PowerTranz (HPP)**: los datos de la tarjeta nunca pasan por Odoo (PCI SAQ A).
- 3-D Secure lo maneja PowerTranz.
- El resultado se confirma siempre servidor a servidor (`spi/payment`). Se verifican el GUID, el pedido, la moneda y el importe.
- Reembolsos totales y parciales desde Contabilidad, con el botón **Reembolsar** del pago.

## Flujo

1. Al pagar, Odoo llama a `POST /api/spi/sale`. Se envía el `ExtendedData.HostedPage` y se recibe `RedirectData`, un HTML que se envía solo, más un `SpiToken`.
2. El navegador va a `/payment/powertranz/redirect`. Esa ruta sirve el HTML de PowerTranz como página completa y el cliente queda en la página de PowerTranz.
3. PowerTranz hace un POST a `/payment/powertranz/return?reference=…&access_token=…` con `Response` (JSON), `TransactionIdentifier` y `SpiToken`. Ese POST no está firmado, así que solo sirve para decidir qué hacer según el resultado del 3DS:
   - `HP0`, o `3D0` con estado Y/A: se completa el pago.
   - `3D0` con estado N/R: error.
   - `3D0` con estado U, o `3D1`/`SP1`: depende de la configuración.
4. Odoo llama a `POST /api/spi/payment` con el token guardado en el servidor. Ese es el momento en que se cobra. Si el token ya se usó o expiró (5 minutos), consulta `GET /api/transactions/{guid}` antes de marcar error.
5. Al reembolsar, Odoo llama a `POST /api/refund` con `Refund: true` y el GUID original. Luego se crea el pago saliente.

## Configuración

1. En el portal de PowerTranz (admin.ptranz.com), crear y publicar una **Hosted Payment Page**. Para 3DS, la plantilla debe pedir el nombre del titular y el email y/o el teléfono.
2. En Odoo, ir a Contabilidad / Sitio web → Configuración → Proveedores de pago → **PowerTranz** y completar:
   - **PowerTranz ID** y **Contraseña**: los entrega BAC/PowerTranz. Staging y producción tienen credenciales distintas.
   - **Page Set** / **Page Name**: los de la página creada. El prefijo `PTZ/` se agrega solo.
   - **Gateway Key**: solo si PowerTranz la entrega.
   - **URL de producción**: dejarla vacía para usar `https://gateway.ptranz.com/api/`.
3. Estado:
   - **Modo de prueba** usa `https://staging.ptranz.com/api/`. En este modo el proveedor no se publica solo: hay que publicarlo a mano para verlo en la tienda.
   - **Habilitado** usa producción.
4. La moneda de la tienda debe estar entre las soportadas. Para Panamá es USD.

Tarjetas de prueba (staging):
- `4012000000020071`: aprobada, sin desafío.
- `4012000000020006`: desafío 3DS, clave `3ds2`.
- `4012000000020121`: 3DS falla.
- `4666666666662222`: rechazada con código 05.

## Pendiente de confirmar con BAC/PowerTranz

- La URL de producción asignada al comercio.
- Si los **reembolsos parciales** están habilitados para el adquirente. Si no lo están, PowerTranz rechaza el reembolso y la transacción queda en error con el mensaje del banco.
- Si se acepta mostrar la HPP a página completa. La documentación recomienda un iframe.
- Qué envía la HPP cuando el cliente cancela. Hoy, cualquier código desconocido deja la transacción en error.

## Tests

```bash
python3 -m odoo -c setup/odoo.conf -d <db> --addons-path="odoo/addons,setup_docs/addons_odossey" \
    -u odossey_payment_powertranz --test-tags /odossey_payment_powertranz --stop-after-init
```

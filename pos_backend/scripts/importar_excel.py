r"""
Script de importacion de datos desde el Excel maestro (VB) hacia PostgreSQL (Neon).
Ejecutar desde pos_backend/ con:
  $env:PYTHONPATH = '.'; .\venv\Scripts\python scripts\importar_excel.py

El archivo de origen se puede indicar con la variable de entorno `EXCEL_ORIGEN`;
si no, se usa el Excel maestro por defecto.

La importacion es **atomica**: todo se inserta en una sola transaccion y se hace
un único `commit` al final. Si algo falla, no queda nada a medias. Pensado para
correr sobre una base **vacía** (tras `TRUNCATE ... RESTART IDENTITY` o recrear
el esquema con Alembic).
"""
import os
import sys
import openpyxl
import bcrypt
from datetime import datetime
from app.core.timezone import BOGOTA_TZ

from app.db.session import SessionLocal
from app.db.models import (
    Cliente, Producto, Factura, DetalleFactura, Pago, RegistroCaja, TurnoCaja,
    Kardex, Usuario,
    EstadoFactura, FormaPago, TipoMovimientoCaja, TipoMovimientoInventario,
    RolUsuario,
)

ARCHIVO = os.getenv(
    "EXCEL_ORIGEN",
    "data/Sistema_Ventas_CasaCultural_ModoUsuario.xlsx",
)


def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def safe_str(val, default=""):
    return str(val).strip() if val is not None else default


def parse_datetime(fecha, hora=None):
    if fecha is None:
        return None
    if isinstance(fecha, datetime):
        dt = fecha
    else:
        dt = datetime(fecha.year, fecha.month, fecha.day)
    if hora is not None:
        try:
            dt = dt.replace(hour=hora.hour, minute=hora.minute, second=hora.second)
        except Exception:
            pass
    return dt.replace(tzinfo=BOGOTA_TZ)


FORMA_PAGO_MAP = {
    "efectivo": FormaPago.EFECTIVO,
    "transferencia": FormaPago.TRANSFERENCIA,
    "tarjeta": FormaPago.TARJETA,
    "credito": FormaPago.OTRO,
    "crédito": FormaPago.OTRO,
    "banco": FormaPago.OTRO,
    "otro": FormaPago.OTRO,
}

ESTADO_FACTURA_MAP = {
    "pagada": EstadoFactura.PAGADA,
    "pendiente": EstadoFactura.PENDIENTE,
    "pagado parcial": EstadoFactura.PAGADO_PARCIAL,
    "anulada": EstadoFactura.ANULADA,
}


def map_forma_pago(val):
    if val is None:
        return None
    return FORMA_PAGO_MAP.get(str(val).strip().lower(), FormaPago.OTRO)


def map_estado_factura(val):
    if val is None:
        return EstadoFactura.PENDIENTE
    return ESTADO_FACTURA_MAP.get(str(val).strip().lower(), EstadoFactura.PENDIENTE)


def main():
    print(f"Abriendo {ARCHIVO}...")
    wb = openpyxl.load_workbook(ARCHIVO, read_only=True, data_only=True)
    db = SessionLocal()

    try:
        # ============================================================
        # 0. Crear un usuario sistema para las FK obligatorias
        # ============================================================
        usuario_sistema = Usuario(
            username="sistema",
            nombre="Usuario Sistema (importacion)",
            hashed_password=bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8"),
            rol=RolUsuario.ADMIN,
            activo=True,
        )
        db.add(usuario_sistema)
        db.flush()
        usuario_id = usuario_sistema.id
        print(f"  Usuario sistema creado (id={usuario_id})")

        # ============================================================
        # 1. CLIENTES
        # ============================================================
        print("Importando Clientes...")
        ws = wb["Clientes"]
        cliente_nombre_a_id = {}
        count = 0
        seen_docs = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            id_excel = row[0]
            if id_excel is None:
                continue
            nombre = safe_str(row[1], "Cliente Desconocido")
            doc_raw = safe_str(row[6])
            if not doc_raw:
                doc_raw = f"SIN-DOC-{id_excel}"
            doc_final = doc_raw
            suffix = 2
            while doc_final in seen_docs:
                doc_final = f"{doc_raw}-{suffix}"
                suffix += 1
            seen_docs.add(doc_final)

            c = Cliente(nombre=nombre, documento=doc_final)
            db.add(c)
            db.flush()
            cliente_nombre_a_id[nombre.lower()] = c.id
            count += 1
        for r in wb["Facturas"].iter_rows(min_row=2, values_only=True):
            if r[0] is not None:
                n = safe_str(r[3], "Consumidor Final")
                if n.lower() not in cliente_nombre_a_id:
                    doc = "SIN-DOC-CLI-" + str(len(cliente_nombre_a_id) + 1)
                    cli = Cliente(nombre=n, documento=doc)
                    db.add(cli)
                    db.flush()
                    cliente_nombre_a_id[n.lower()] = cli.id
                    count += 1
        db.flush()
        print(f"  {count} clientes importados (incluyendo no registrados en hoja Clientes).")

        # ============================================================
        # 2. PRODUCTOS (saltar duplicados por codigo)
        # ============================================================
        print("Importando Productos...")
        ws = wb["Productos"]
        producto_codigo_a_id = {}
        producto_clave_a_id = {}
        codigos_usados = set()
        count = 0
        skipped = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            codigo = row[0]
            if not codigo:
                continue
            codigo = safe_str(codigo).upper()
            nombre = safe_str(row[1])
            clave = (codigo, nombre.lower())
            if clave in producto_clave_a_id:
                skipped += 1
                continue
            codigo_final = codigo
            sufijo = 2
            while codigo_final in codigos_usados:
                codigo_final = f"{codigo}-{sufijo}"
                sufijo += 1
            codigos_usados.add(codigo_final)
            precio = safe_float(row[3])
            stock = safe_int(row[6])

            p = Producto(codigo=codigo_final, nombre=nombre, precio=precio, stock=stock)
            db.add(p)
            db.flush()
            producto_clave_a_id[clave] = p.id
            producto_clave_a_id[(codigo_final, nombre.lower())] = p.id
            producto_codigo_a_id.setdefault(codigo, p.id)
            count += 1
        db.flush()
        print(f"  {count} productos importados ({skipped} duplicados omitidos).")

        def resolver_producto(cod, nom):
            codigo_buscar = safe_str(cod).upper()
            clave_buscar = (codigo_buscar, safe_str(nom).lower())
            return producto_clave_a_id.get(clave_buscar) or producto_codigo_a_id.get(codigo_buscar)

        # ============================================================
        # 3. FACTURAS
        # ============================================================
        print("Importando Facturas...")
        ws = wb["Facturas"]
        factura_num_a_id = {}
        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            num_factura = row[0]
            if num_factura is None:
                continue
            fecha = parse_datetime(row[1], row[2])
            cliente_nombre = safe_str(row[3]).lower()
            total = safe_float(row[4])
            estado = map_estado_factura(row[6])
            saldo = safe_float(row[7])

            cliente_id = cliente_nombre_a_id.get(cliente_nombre)

            f = Factura(
                cliente_id=cliente_id,
                vendedor_id=usuario_id,
                fecha=fecha,
                total=total,
                saldo=saldo,
                estado=estado,
            )
            db.add(f)
            db.flush()
            factura_num_a_id[num_factura] = f.id
            count += 1
        db.flush()
        print(f"  {count} facturas importadas.")

        # ============================================================
        # 4. DETALLE FACTURA
        # ============================================================
        print("Importando Detalles de Factura...")
        ws = wb["DetalleFactura"]
        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            num_factura = row[0]
            if num_factura is None:
                continue
            factura_id = factura_num_a_id.get(num_factura)
            if factura_id is None:
                continue
            producto_id = resolver_producto(row[2], row[3])
            cantidad = safe_int(row[4], 1)
            precio_unitario = safe_float(row[5])
            subtotal = safe_float(row[6])

            d = DetalleFactura(
                factura_id=factura_id,
                producto_id=producto_id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                subtotal=subtotal,
            )
            db.add(d)
            count += 1
        db.flush()
        print(f"  {count} detalles de factura importados.")

        # ============================================================
        # 5. PAGOS
        # ============================================================
        print("Importando Pagos...")
        ws = wb["Pagos"]
        count = 0
        sin_pago = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None or row[2] is None:
                continue
            factura_id = factura_num_a_id.get(row[2])
            if factura_id is None:
                continue
            fecha = parse_datetime(row[0], row[1])
            valor = safe_float(row[5])
            if valor == 0:
                sin_pago += 1
            forma_pago = map_forma_pago(row[4])
            pago = Pago(factura_id=factura_id, cajero_id=usuario_id, fecha=fecha, valor=valor, forma_pago=forma_pago)
            db.add(pago)
            count += 1
        db.flush()
        print(f"  {count} pagos importados ({sin_pago} con valor 0).")

        # ============================================================
        # 6. MOVIMIENTOS DE INVENTARIO (Kardex)
        # ============================================================
        print("Importando Movimientos de Inventario...")
        ws = wb["MovimientosInventario"]
        TIPO_MOV_INV_MAP = {
            "compra": TipoMovimientoInventario.ENTRADA_COMPRA,
            "entrada por compra": TipoMovimientoInventario.ENTRADA_COMPRA,
            "inventario inicial": TipoMovimientoInventario.ENTRADA_COMPRA,
            "venta": TipoMovimientoInventario.SALIDA_VENTA,
            "salida por venta": TipoMovimientoInventario.SALIDA_VENTA,
            "devolucion": TipoMovimientoInventario.DEVOLUCION,
            "ajuste": TipoMovimientoInventario.AJUSTE,
            "ajuste positivo": TipoMovimientoInventario.AJUSTE,
            "ajuste negativo": TipoMovimientoInventario.AJUSTE,
        }
        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            fecha = parse_datetime(row[0], row[1])
            tipo_raw = safe_str(row[2]).lower()
            tipo = TIPO_MOV_INV_MAP.get(tipo_raw, TipoMovimientoInventario.AJUSTE)
            producto_id = resolver_producto(row[3], row[4])
            cantidad = safe_int(row[5])
            saldo_stock = safe_int(row[7])
            observacion = safe_str(row[10])

            k = Kardex(
                producto_id=producto_id,
                usuario_id=usuario_id,
                fecha=fecha,
                tipo_movimiento=tipo,
                cantidad=cantidad,
                saldo_stock=saldo_stock,
                referencia=observacion if observacion else None,
            )
            db.add(k)
            count += 1
        db.flush()
        print(f"  {count} movimientos de inventario importados.")

        # ============================================================
        # 7. MOVIMIENTOS DE CAJA (RegistroCaja)
        # ============================================================
        print("Importando Movimientos de Caja...")
        turno = TurnoCaja(
            usuario_apertura_id=usuario_id,
            saldo_inicial=0,
            abierta=False,
        )
        db.add(turno)
        db.flush()
        turno_id = turno.id

        ws = wb["Caja"]
        TIPO_MOV_CAJA_MAP = {
            "apertura": TipoMovimientoCaja.APERTURA,
            "cierre": TipoMovimientoCaja.CIERRE,
            "entrada": TipoMovimientoCaja.ENTRADA,
            "salida": TipoMovimientoCaja.SALIDA,
        }
        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            fecha = parse_datetime(row[0], row[1])
            tipo_raw = safe_str(row[2]).lower()
            tipo = TIPO_MOV_CAJA_MAP.get(tipo_raw, TipoMovimientoCaja.ENTRADA)
            referencia = safe_str(row[3])
            forma_pago = map_forma_pago(row[4])
            entrada = safe_float(row[5])
            salida = safe_float(row[6])
            monto = entrada - salida
            observacion = safe_str(row[7])

            rc = RegistroCaja(
                turno_caja_id=turno_id,
                usuario_id=usuario_id,
                fecha=fecha,
                tipo=tipo,
                referencia=referencia if referencia else "Importado desde Excel",
                forma_pago=forma_pago,
                monto=monto,
                observacion=observacion if observacion else None,
            )
            db.add(rc)
            count += 1
        db.commit()
        print(f"  {count} movimientos de caja importados.")

        print("\n=== IMPORTACION COMPLETADA EXITOSAMENTE ===")

    except Exception as e:
        db.rollback()
        print(f"\nERROR durante la importacion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

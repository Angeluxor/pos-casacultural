"""Pruebas del feedback del equipo y su bandeja de gestión."""
from .conftest import auth

_CAPTURA_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2nGQAAAAASUVORK5CYII="
)


def _crear(client, token, **cambios):
    datos = {
        "tipo": "Idea",
        "comentario": "Sería útil ver el total del día en la caja.",
        "contexto": {"ruta": "/caja", "version": "1.0.0"},
    }
    datos.update(cambios)
    return client.post("/api/feedback/", headers=auth(token), json=datos)


def test_cajero_y_mesero_pueden_enviar_feedback(client, token_cajero, token_mesero):
    creado = _crear(client, token_cajero)
    assert creado.status_code == 200, creado.text
    item = creado.json()
    assert item["estado"] == "Nuevo"
    assert item["prioridad"] == "Media"
    assert item["usuario_nombre"] == "Cajero"
    assert item["contexto"]["ruta"] == "/caja"
    assert item["tiene_captura"] is False

    assert _crear(client, token_mesero, tipo="Bug").status_code == 200

    # Solo quien gestiona puede ver la bandeja.
    assert client.get("/api/feedback/", headers=auth(token_cajero)).status_code == 403
    assert client.get("/api/feedback/", headers=auth(token_mesero)).status_code == 403


def test_admin_lista_filtra_y_busca(client, token_admin, token_cajero):
    assert _crear(
        client, token_cajero, tipo="Bug", comentario="Error al cerrar caja"
    ).status_code == 200
    assert _crear(
        client,
        token_cajero,
        tipo="Idea",
        comentario="Agregar un atajo para abrir caja",
    ).status_code == 200

    listado = client.get("/api/feedback/", headers=auth(token_admin))
    assert listado.status_code == 200, listado.text
    assert listado.json()["total"] == 2

    por_tipo = client.get(
        "/api/feedback/", headers=auth(token_admin), params={"tipo": "Idea"}
    ).json()
    assert por_tipo["total"] == 1
    assert "atajo" in por_tipo["items"][0]["comentario"]

    por_busqueda = client.get(
        "/api/feedback/", headers=auth(token_admin), params={"buscar": "cerrar caja"}
    ).json()
    assert por_busqueda["total"] == 1

    por_estado = client.get(
        "/api/feedback/", headers=auth(token_admin), params={"estado": "Nuevo"}
    ).json()
    assert por_estado["total"] == 2


def test_captura_se_valida_y_solo_la_ve_admin(client, token_admin, token_cajero):
    creado = _crear(
        client,
        token_cajero,
        captura_base64=_CAPTURA_PNG,
        captura_mime="image/png",
        captura_nombre="pantalla.png",
    )
    assert creado.status_code == 200, creado.text
    item = creado.json()
    assert item["tiene_captura"] is True
    assert item["captura_mime"] == "image/png"
    assert item["captura_nombre"] == "pantalla.png"

    listado = client.get("/api/feedback/", headers=auth(token_admin)).json()
    assert listado["items"][0]["tiene_captura"] is True

    captura = client.get(
        f"/api/feedback/{item['id']}/captura", headers=auth(token_admin)
    )
    assert captura.status_code == 200, captura.text
    assert captura.headers["content-type"].startswith("image/png")
    assert captura.content.startswith(b"\x89PNG\r\n\x1a\n")

    assert (
        client.get(
            f"/api/feedback/{item['id']}/captura", headers=auth(token_cajero)
        ).status_code
        == 403
    )


def test_capturas_invalidas_se_rechazan(client, token_cajero):
    base = {
        "tipo": "Bug",
        "comentario": "No puedo guardar",
        "contexto": {},
    }

    no_es_base64 = client.post(
        "/api/feedback/",
        headers=auth(token_cajero),
        json={**base, "captura_base64": "esto no es una imagen", "captura_mime": "image/png"},
    )
    assert no_es_base64.status_code == 400

    firma_incorrecta = client.post(
        "/api/feedback/",
        headers=auth(token_cajero),
        json={**base, "captura_base64": _CAPTURA_PNG, "captura_mime": "image/jpeg"},
    )
    assert firma_incorrecta.status_code == 400

    sin_mime = client.post(
        "/api/feedback/",
        headers=auth(token_cajero),
        json={**base, "captura_base64": _CAPTURA_PNG},
    )
    assert sin_mime.status_code == 422


def test_admin_gestiona_estado_prioridad_etiquetas_y_responsable(
    client, token_admin, token_cajero, admin_id
):
    item = _crear(client, token_cajero).json()

    cambio = client.patch(
        f"/api/feedback/{item['id']}",
        headers=auth(token_admin),
        json={
            "estado": "Resuelto",
            "prioridad": "Alta",
            "etiquetas": ["UI", "bug", " ui "],
            "notas_internas": "Se corrigió en el próximo despliegue.",
            "responsable_id": admin_id,
        },
    )
    assert cambio.status_code == 200, cambio.text
    actualizado = cambio.json()
    assert actualizado["estado"] == "Resuelto"
    assert actualizado["prioridad"] == "Alta"
    assert actualizado["etiquetas"] == ["UI", "bug"]
    assert actualizado["notas_internas"].startswith("Se corrigió")
    assert actualizado["responsable_id"] == admin_id
    assert actualizado["responsable_nombre"] == "Admin"
    assert actualizado["resuelto_en"] is not None

    reabierto = client.patch(
        f"/api/feedback/{item['id']}",
        headers=auth(token_admin),
        json={"estado": "Nuevo", "responsable_id": None, "etiquetas": []},
    )
    assert reabierto.status_code == 200, reabierto.text
    assert reabierto.json()["resuelto_en"] is None
    assert reabierto.json()["responsable_id"] is None
    assert reabierto.json()["etiquetas"] == []

    invalido = client.patch(
        f"/api/feedback/{item['id']}",
        headers=auth(token_admin),
        json={"responsable_id": 999999},
    )
    assert invalido.status_code == 400

    estado_nulo = client.patch(
        f"/api/feedback/{item['id']}",
        headers=auth(token_admin),
        json={"estado": None},
    )
    assert estado_nulo.status_code == 400


def test_limite_de_envios_por_minuto(client, token_cajero):
    for i in range(5):
        assert _crear(client, token_cajero, comentario=f"Comentario {i}").status_code == 200
    excedido = _crear(client, token_cajero, comentario="Comentario 6")
    assert excedido.status_code == 429

"""Pruebas de la sonda de salud y de las cabeceras de seguridad."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_raiz(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Casi Obsceno" in resp.json()["message"]


def test_cabeceras_de_seguridad(client):
    resp = client.get("/api/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers

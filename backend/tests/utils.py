"""Ayudas para las pruebas de la API de datos."""
from __future__ import annotations

CLAVE = "Tr3s-Tristes-Tigres"
API = "/api/v1"

GASTO = {"merchant": "Líder", "amount": 3190, "category": "Alimentación", "date": "2026-09-29"}
INGRESO = {"source": "Empresa SpA", "amount": 850000, "date": "2026-09-01", "type": "sueldo"}
CATEGORIA = {"name": "Mascotas", "color": "#3b82f6"}
META = {"title": "Notebook", "target_amount": 600000}


class Usuario:
    """Un usuario registrado, con sus cabeceras de autenticación."""

    def __init__(self, cliente, email: str) -> None:
        r = cliente.post(f"{API}/auth/register", json={"email": email, "password": CLAVE})
        assert r.status_code == 201, r.text
        cuerpo = r.json()
        self.email = email
        self.id = cuerpo["user"]["id"]
        self.headers = {"Authorization": f"Bearer {cuerpo['access_token']}"}
        self.cliente = cliente

    def get(self, ruta, **kw):
        return self.cliente.get(f"{API}{ruta}", headers=self.headers, **kw)

    def post(self, ruta, json=None, **kw):
        return self.cliente.post(f"{API}{ruta}", json=json, headers=self.headers, **kw)

    def patch(self, ruta, json=None, **kw):
        return self.cliente.patch(f"{API}{ruta}", json=json, headers=self.headers, **kw)

    def delete(self, ruta, **kw):
        return self.cliente.delete(f"{API}{ruta}", headers=self.headers, **kw)

    # atajos que exigen éxito
    def crear(self, ruta, datos) -> dict:
        r = self.post(ruta, datos)
        assert r.status_code == 201, r.text
        return r.json()

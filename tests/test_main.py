"""
Pruebas unitarias automatizadas para el pipeline de CI/CD.

Cubre los 4 casos marcados como "Automatizable (CI/CD)" en la matriz
de pruebas (matriz_pruebas_solicitudes.xlsx):

    TC-01  Login con correo válido y activo      -> redirige a /auth/mfa
    TC-02  Login con correo inexistente          -> mensaje de error
    TC-07  OTP incorrecto o expirado             -> mensaje de error
    TC-20  USER intentando entrar a /admin       -> redirige a /dashboard

No requieren una Postgres real: TC-01 y TC-02 sustituyen get_db por
una sesión falsa (app.dependency_overrides); TC-07 y TC-20 nunca
llegan a tocar la base de datos.

Desde que se agregó protección CSRF a main.py, todo POST exige un
campo csrfToken que coincida con la cookie csrf_token puesta por el
middleware. _obtener_csrf_token() simula lo que hace el navegador:
un GET normal, y de ahí se lee la cookie para reusarla en el POST.
"""

import sys
import os
import uuid
from types import SimpleNamespace

# main.py, db.py y modelos.py viven en codigos/, un nivel arriba de tests/
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "codigos"),
)

import pytest
from fastapi.testclient import TestClient

import main
from main import app, get_db

client = TestClient(app)


# ==========================================
# Helpers
# ==========================================

def _obtener_csrf_token():
    """Simula lo que hace un navegador: un GET normal deja la cookie
    csrf_token puesta por el middleware; la leemos para reusarla."""
    resp = client.get("/")
    token = resp.cookies.get("csrf_token") or client.cookies.get("csrf_token")
    assert token, "El middleware no puso la cookie csrf_token"
    return token


class FakeQuery:
    """Sustituye a Session.query(Usuario).filter(...).first()."""

    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._resultado


class FakeSession:
    def __init__(self, usuario=None):
        self._usuario = usuario

    def query(self, modelo):
        return FakeQuery(self._usuario)

    def commit(self):
        pass

    def rollback(self):
        pass


def _fake_get_db(usuario=None):
    """Genera un override de get_db que entrega una FakeSession."""

    def _override():
        yield FakeSession(usuario=usuario)

    return _override


@pytest.fixture(autouse=True)
def limpiar_overrides():
    """Evita que un override de un test contamine a los demás."""
    yield
    app.dependency_overrides.clear()


# ==========================================
# TC-01 — Login con correo válido y activo
# ==========================================

def test_tc01_login_correo_valido_redirige_a_mfa():
    usuario_fake = SimpleNamespace(
        email="usuario@gmail.com",
        rol="ADMIN",
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    )
    app.dependency_overrides[get_db] = _fake_get_db(usuario=usuario_fake)

    csrf_token = _obtener_csrf_token()

    response = client.post(
        "/auth/google",
        data={"email": "usuario@gmail.com", "csrfToken": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/mfa"
    assert response.cookies.get("temp_email") == "usuario@gmail.com"
    assert response.cookies.get("temp_role") == "ADMIN"
    assert response.cookies.get("temp_user_id") == "11111111-1111-1111-1111-111111111111"


# ==========================================
# TC-02 — Login con correo inexistente
# ==========================================

def test_tc02_login_correo_inexistente_muestra_error():
    app.dependency_overrides[get_db] = _fake_get_db(usuario=None)

    csrf_token = _obtener_csrf_token()

    response = client.post(
        "/auth/google",
        data={"email": "falso@gmail.com", "csrfToken": csrf_token},
    )

    assert response.status_code == 200
    assert "No existe una cuenta activa con ese correo." in response.text


# ==========================================
# TC-07 — Código OTP incorrecto o expirado
# ==========================================

def test_tc07_otp_incorrecto_muestra_error():
    csrf_token = _obtener_csrf_token()

    response = client.post(
        "/auth/mfa/verify",
        data={"codigo_otp": "000000", "csrfToken": csrf_token},
    )

    assert response.status_code == 200
    assert "Código incorrecto o expirado." in response.text


# ==========================================
# TC-20 — USER intentando entrar al panel de administración
# ==========================================

def test_tc20_user_no_puede_entrar_al_panel_admin():
    response = client.get(
        "/admin",
        cookies={
            "user_email": "usuario@gmail.com",
            "user_role": "USER",
            "user_id": "11111111-1111-1111-1111-111111111111",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
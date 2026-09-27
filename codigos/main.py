import io
import os
import uuid
import base64
from datetime import datetime

import pyotp
import qrcode

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from db import get_db
from modelos import Usuario, Solicitud, HistorialSolicitud


app = FastAPI(title="Solicitudes APP")


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ==========================================
# CONFIGURACIÓN
# ==========================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ==========================================
# GOOGLE AUTHENTICATOR
# ==========================================

MFA_SECRET = pyotp.random_base32()


# ==========================================
# HELPER - USUARIO ACTUAL
# ==========================================

def get_current_user(request: Request):
    user_email = request.cookies.get("user_email")
    user_role = request.cookies.get("user_role")
    user_id = request.cookies.get("user_id")

    if not user_email or not user_id:
        return None

    return {
        "email": user_email,
        "role": user_role,
        "id": user_id
    }


# ==========================================
# PANTALLAS DE AUTENTICACIÓN
# ==========================================

@app.get("/", response_class=HTMLResponse)
def pantalla_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


# ==========================================
# LOGIN
# ==========================================

@app.post("/auth/google")
def login_google(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.email == email,
                Usuario.esta_activo.is_(True)
            )
            .first()
        )
    except SQLAlchemyError:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "No se pudo conectar con la base de datos. Revisa tus variables de entorno."
            }
        )

    if usuario is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "No existe una cuenta activa con ese correo."
            }
        )

    redirect = RedirectResponse(
        url="/auth/mfa",
        status_code=303
    )

    redirect.set_cookie(key="temp_email", value=usuario.email)
    redirect.set_cookie(key="temp_role", value=usuario.rol)
    redirect.set_cookie(key="temp_user_id", value=str(usuario.id))

    return redirect


# ==========================================
# CONFIGURACIÓN DE GOOGLE AUTHENTICATOR
# ==========================================

@app.get("/auth/mfa/setup", response_class=HTMLResponse)
def configurar_mfa(request: Request):
    email_actual = request.cookies.get(
        "temp_email",
        request.cookies.get("user_email", "usuario@gmail.com")
    )

    totp = pyotp.TOTP(MFA_SECRET)
    uri = totp.provisioning_uri(
        name=email_actual,
        issuer_name="Solicitudes APP"
    )

    qr = qrcode.make(uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Configurar Google Authenticator</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
            img {{ width: 250px; height: 250px; margin: 20px; }}
            .secret {{ font-family: monospace; background: #eee; padding: 10px; display: inline-block; }}
        </style>
    </head>
    <body>
        <h1>Configurar Google Authenticator</h1>
        <p>Escanea este código QR con Google Authenticator.</p>
        <img src="data:image/png;base64,{qr_base64}" alt="QR Google Authenticator">
        <p>Si no puedes escanear el QR, utiliza esta clave:</p>
        <p class="secret">{MFA_SECRET}</p>
        <p>Después de configurarlo, regresa al login.</p>
        <a href="/">Volver al login</a>
    </body>
    </html>
    """


# ==========================================
# PANTALLA MFA
# ==========================================

@app.get("/auth/mfa", response_class=HTMLResponse)
def pantalla_mfa(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="mfa.html"
    )


# ==========================================
# VERIFICACIÓN MFA
# ==========================================

@app.post("/auth/mfa/verify")
def verificar_mfa(
    request: Request,
    codigo_otp: str = Form(...),
    db: Session = Depends(get_db)
):
    totp = pyotp.TOTP(MFA_SECRET)

    if not totp.verify(codigo_otp):
        return templates.TemplateResponse(
            request=request,
            name="mfa.html",
            context={
                "error": "Código incorrecto o expirado."
            }
        )

    email = request.cookies.get("temp_email", "usuario@gmail.com")
    role = request.cookies.get("temp_role", "USER")
    user_id = request.cookies.get("temp_user_id")

    if user_id:
        try:
            usuario_db = (
                db.query(Usuario)
                .filter(Usuario.id == uuid.UUID(user_id))
                .first()
            )

            if usuario_db:
                usuario_db.ultlogin = datetime.utcnow()
                db.commit()

        except (SQLAlchemyError, ValueError):
            db.rollback()

    redirect = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    redirect.set_cookie(key="user_email", value=email)
    redirect.set_cookie(key="user_role", value=role)

    if user_id:
        redirect.set_cookie(key="user_id", value=user_id)

    redirect.delete_cookie("temp_email")
    redirect.delete_cookie("temp_role")
    redirect.delete_cookie("temp_user_id")

    return redirect


# ==========================================
# LOGOUT
# ==========================================

@app.get("/logout")
def logout():
    redirect = RedirectResponse(
        url="/",
        status_code=303
    )

    redirect.delete_cookie("user_email")
    redirect.delete_cookie("user_role")
    redirect.delete_cookie("user_id")

    return redirect


# ==========================================
# PANTALLAS USUARIO FINAL
# ==========================================

@app.get("/dashboard", response_class=HTMLResponse)
def pantalla_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    # Filtrar únicamente registros activos (no borrados)
    query = db.query(Solicitud).filter(Solicitud.borrado.is_(False))

    if user["role"] == "ADMIN":
        # El Administrador ve absolutamente todas las solicitudes activas
        solicitudes_visibles = query.all()
    else:
        user_uuid = uuid.UUID(user["id"])
        # El usuario común ve:
        # 1. Sus propias solicitudes (independientemente del estatus: Pendiente, Aceptado, Rechazado)
        # 2. Las solicitudes de otros usuarios SI Y SOLO SI su estatus es 'Aceptado'
        solicitudes_visibles = query.filter(
            (Solicitud.user_id == user_uuid) | (Solicitud.estatus == "Aceptado")
        ).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "solicitudes": solicitudes_visibles,
            "user": user
        }
    )


# ==========================================
# CREAR SOLICITUD
# ==========================================

@app.get("/requests/new", response_class=HTMLResponse)
def pantalla_crear_solicitud(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="create_request.html",
        context={
            "user": user
        }
    )


@app.post("/requests/new")
def crear_solicitud(
    request: Request,
    organizacion: str = Form(...),
    contacto: str = Form(...),
    descripcion: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    nueva_solicitud = Solicitud(
        organizacion=organizacion,
        correo_contacto=contacto,
        descripcion=descripcion,
        estatus="Pendiente",
        borrado=False,
        user_id=uuid.UUID(user["id"])
    )

    db.add(nueva_solicitud)
    db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# ELIMINAR SOLICITUD (SOFT DELETE)
# ==========================================

@app.post("/requests/delete/{req_id}")
def borrar_solicitud(
    request: Request,
    req_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    solicitud = db.query(Solicitud).filter(Solicitud.id == req_id).first()

    if solicitud:
        user_uuid = uuid.UUID(user["id"])

        # ADMIN o el creador de la solicitud
        if user["role"] == "ADMIN" or solicitud.user_id == user_uuid:
            solicitud.borrado = True
            solicitud.fecborrado = datetime.utcnow()
            solicitud.fecact = datetime.utcnow()
            db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# ADMIN
# ==========================================

@app.get("/admin", response_class=HTMLResponse)
def pantalla_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)

    if not user or user["role"] != "ADMIN":
        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    solicitudes_eliminadas = (
        db.query(Solicitud)
        .filter(Solicitud.borrado.is_(True))
        .all()
    )

    solicitudes_todas = (
        db.query(Solicitud)
        .filter(Solicitud.borrado.is_(False))
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "eliminadas": solicitudes_eliminadas,
            "todas": solicitudes_todas,
            "user": user
        }
    )


# ==========================================
# CAMBIAR STATUS + AUDITORÍA (HISTORIAL)
# ==========================================

@app.post("/admin/status/{req_id}")
def cambiar_status(
    request: Request,
    req_id: int,
    status: str = Form(...),  # Espera 'Pendiente', 'Aceptado' o 'Rechazado'
    db: Session = Depends(get_db)
):
    user = get_current_user(request)

    if not user or user["role"] != "ADMIN":
        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    solicitud = db.query(Solicitud).filter(Solicitud.id == req_id).first()

    if solicitud and solicitud.estatus != status:
        estatus_anterior = solicitud.estatus

        # Actualizar la solicitud
        solicitud.estatus = status
        solicitud.fecact = datetime.utcnow()

        # Insertar registro en el historial de cambios
        historial = HistorialSolicitud(
            sol_id=solicitud.id,
            estatus_antiguo=estatus_anterior,
            estatus_actual=status,
            modificado_por=uuid.UUID(user["id"])
        )

        db.add(historial)
        db.commit()

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


# ==========================================
# EJECUCIÓN
# ==========================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
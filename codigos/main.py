import io
import base64

import pyotp
import qrcode

from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="Solicitudes APP")


# ==========================================
# CONFIGURACIÓN
# ==========================================

templates = Jinja2Templates(directory="templates")


# ==========================================
# GOOGLE AUTHENTICATOR
# ==========================================

# IMPORTANTE:
# Por ahora usamos una clave global únicamente para probar
# el funcionamiento del autenticador.
#
# Más adelante esta clave debe guardarse en la base de datos
# y cada usuario tendrá su propio secreto.

MFA_SECRET = pyotp.random_base32()


# ==========================================
# BASE DE DATOS SIMULADA
# ==========================================

MOCK_REQUESTS = [

    {
        "id": 1,
        "organizacion": "Tech Corp",
        "contacto": "juan@tech.com",
        "descripcion": "Soporte para servidores",
        "status": "ACCEPTED",
        "deleted": False,
        "user_email": "usuario@gmail.com"
    },

    {
        "id": 2,
        "organizacion": "Dev Inc",
        "contacto": "ana@dev.com",
        "descripcion": "Licencia de software",
        "status": "PENDING",
        "deleted": False,
        "user_email": "otro@gmail.com"
    }
]


# ==========================================
# HELPER - USUARIO ACTUAL
# ==========================================

def get_current_user(request: Request):

    user_email = request.cookies.get("user_email")
    user_role = request.cookies.get("user_role")

    if not user_email:
        return None

    return {
        "email": user_email,
        "role": user_role
    }


# ==========================================
# PANTALLAS DE AUTENTICACIÓN
# ==========================================

@app.get("/", response_class=HTMLResponse)
def pantalla_login(request: Request):

    """
    Pantalla 1: Login con selección de rol.

    NOTA:
    Actualmente sigue siendo una simulación.
    Posteriormente cambiaremos esto por autenticación real.
    """

    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


# ==========================================
# LOGIN
# ==========================================

@app.post("/auth/google")
def login_google(
    response: Response,
    role: str = Form(...),
    email: str = Form(...)
):

    """
    Actualmente solamente guarda temporalmente
    el email y rol seleccionado.

    El nombre /auth/google es provisional.
    Todavía NO estamos utilizando OAuth de Google.
    """

    redirect = RedirectResponse(
        url="/auth/mfa",
        status_code=303
    )

    redirect.set_cookie(
        key="temp_email",
        value=email
    )

    redirect.set_cookie(
        key="temp_role",
        value=role
    )

    return redirect


# ==========================================
# CONFIGURACIÓN DE GOOGLE AUTHENTICATOR
# ==========================================

@app.get("/auth/mfa/setup", response_class=HTMLResponse)
def configurar_mfa(request: Request):

    """
    Genera la información necesaria para vincular
    Google Authenticator.

    Esta ruta es provisional para configurar el MFA.
    """

    totp = pyotp.TOTP(MFA_SECRET)

    uri = totp.provisioning_uri(
        name="usuario@gmail.com",
        issuer_name="Solicitudes APP"
    )

    # Generar QR en memoria
    qr = qrcode.make(uri)

    buffer = io.BytesIO()

    qr.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return f"""
    <!DOCTYPE html>

    <html lang="es">

    <head>

        <meta charset="UTF-8">

        <title>Configurar Google Authenticator</title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                text-align: center;
                margin-top: 50px;
            }}

            img {{
                width: 250px;
                height: 250px;
                margin: 20px;
            }}

            .secret {{
                font-family: monospace;
                background: #eee;
                padding: 10px;
                display: inline-block;
            }}

        </style>

    </head>

    <body>

        <h1>Configurar Google Authenticator</h1>

        <p>
            Escanea este código QR con Google Authenticator.
        </p>

        <img
            src="data:image/png;base64,{qr_base64}"
            alt="QR Google Authenticator"
        >

        <p>
            Si no puedes escanear el QR, utiliza esta clave:
        </p>

        <p class="secret">
            {MFA_SECRET}
        </p>

        <p>
            Después de configurarlo, regresa al login.
        </p>

        <a href="/">
            Volver al login
        </a>

    </body>

    </html>
    """


# ==========================================
# PANTALLA MFA
# ==========================================

@app.get("/auth/mfa", response_class=HTMLResponse)
def pantalla_mfa(request: Request):

    """
    Pantalla 2:
    Validación del código generado por Google Authenticator.
    """

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
    codigo_otp: str = Form(...)
):

    """
    Verifica el código de 6 dígitos generado
    por Google Authenticator.
    """

    # Crear objeto TOTP utilizando nuestro secreto
    totp = pyotp.TOTP(MFA_SECRET)

    # Verificar código
    codigo_valido = totp.verify(codigo_otp)

    if not codigo_valido:

        return templates.TemplateResponse(
            request=request,
            name="mfa.html",
            context={
                "error": "Código incorrecto o expirado."
            }
        )

    # Recuperar datos temporales
    email = request.cookies.get(
        "temp_email",
        "usuario@gmail.com"
    )

    role = request.cookies.get(
        "temp_role",
        "USER"
    )

    # Crear sesión
    redirect = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    redirect.set_cookie(
        key="user_email",
        value=email
    )

    redirect.set_cookie(
        key="user_role",
        value=role
    )

    # Eliminar cookies temporales
    redirect.delete_cookie("temp_email")
    redirect.delete_cookie("temp_role")

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

    return redirect


# ==========================================
# PANTALLAS USUARIO FINAL
# ==========================================

@app.get("/dashboard", response_class=HTMLResponse)
def pantalla_dashboard(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    # ADMIN puede ver todas las solicitudes
    if user["role"] == "ADMIN":

        solicitudes_visibles = [
            r
            for r in MOCK_REQUESTS
            if not r["deleted"]
        ]

    else:

        # Usuario normal:
        # solicitudes aceptadas + sus propias solicitudes
        solicitudes_visibles = [

            r
            for r in MOCK_REQUESTS

            if not r["deleted"]
            and (
                r["status"] == "ACCEPTED"
                or r["user_email"] == user["email"]
            )

        ]

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

    descripcion: str = Form(...)

):

    user = get_current_user(request)

    if not user:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    nueva_solicitud = {

        "id": len(MOCK_REQUESTS) + 1,

        "organizacion": organizacion,

        "contacto": contacto,

        "descripcion": descripcion,

        "status": "PENDING",

        "deleted": False,

        "user_email": user["email"]

    }

    MOCK_REQUESTS.append(
        nueva_solicitud
    )

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# ELIMINAR SOLICITUD
# ==========================================

@app.post("/requests/delete/{req_id}")
def borrar_solicitud(
    request: Request,
    req_id: int
):

    user = get_current_user(request)

    if not user:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    for r in MOCK_REQUESTS:

        if r["id"] == req_id:

            # ADMIN o creador
            if (
                user["role"] == "ADMIN"
                or r["user_email"] == user["email"]
            ):

                r["deleted"] = True

            break

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# ADMIN
# ==========================================

@app.get("/admin", response_class=HTMLResponse)
def pantalla_admin(request: Request):

    user = get_current_user(request)

    # Solo ADMIN
    if not user or user["role"] != "ADMIN":

        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    solicitudes_eliminadas = [
        r
        for r in MOCK_REQUESTS
        if r["deleted"]
    ]

    solicitudes_todas = [
        r
        for r in MOCK_REQUESTS
        if not r["deleted"]
    ]

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
# CAMBIAR STATUS
# ==========================================

@app.post("/admin/status/{req_id}")
def cambiar_status(

    request: Request,

    req_id: int,

    status: str = Form(...)

):

    user = get_current_user(request)

    if not user or user["role"] != "ADMIN":

        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    for r in MOCK_REQUESTS:

        if r["id"] == req_id:

            r["status"] = status

            break

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
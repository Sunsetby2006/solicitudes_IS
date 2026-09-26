from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Sistema de Solicitudes")

templates = Jinja2Templates(directory="templates")

# ==========================================
# BASE DE DATOS SIMULADA (MOCK EN MEMORIA)
# ==========================================
MOCK_REQUESTS = [
    {
        "id": 1,
        "organizacion": "Tech Corp",
        "contacto": "juan@tech.com",
        "descripcion": "Soporte para servidores de producción y mantenimiento preventivo.",
        "status": "ACCEPTED",  # Visible para usuarios normales
        "deleted": False,
        "user_email": "usuario@gmail.com"
    },
    {
        "id": 2,
        "organizacion": "Dev Inc",
        "contacto": "ana@dev.com",
        "descripcion": "Renovación de licencias de software de desarrollo.",
        "status": "PENDING",   # Solo visible para ADMIN o el creador de la solicitud
        "deleted": False,
        "user_email": "otro@gmail.com"
    }
]

# Helper para obtener el usuario actual desde las Cookies
def get_current_user(request: Request):
    user_email = request.cookies.get("user_email")
    user_role = request.cookies.get("user_role")
    if not user_email:
        return None
    return {"email": user_email, "role": user_role}

# ==========================================
# PANTALLAS DE AUTENTICACIÓN
# ==========================================

@app.get("/", response_class=HTMLResponse)
def pantalla_login(request: Request):
    """Pantalla 1: Login con Selección de Rol (Simulado)"""
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/auth/google")
def login_google(role: str = Form(...), email: str = Form(...)):
    """Guarda temporalmente el email y rol seleccionado en cookies"""
    redirect = RedirectResponse(url="/auth/mfa", status_code=303)
    redirect.set_cookie(key="temp_email", value=email)
    redirect.set_cookie(key="temp_role", value=role)
    return redirect

@app.get("/auth/mfa", response_class=HTMLResponse)
def pantalla_mfa(request: Request):
    """Pantalla 2: Validación Authenticator (OTP)"""
    return templates.TemplateResponse(request=request, name="mfa.html")

@app.post("/auth/mfa/verify")
def verificar_mfa(request: Request, codigo_otp: str = Form(...)):
    """Simulación de código OTP que confirma e inicia la sesión"""
    email = request.cookies.get("temp_email", "usuario@gmail.com")
    role = request.cookies.get("temp_role", "USER")

    redirect = RedirectResponse(url="/dashboard", status_code=303)
    redirect.set_cookie(key="user_email", value=email)
    redirect.set_cookie(key="user_role", value=role)
    return redirect

@app.get("/logout")
def logout():
    """Cierra la sesión actual eliminando las cookies"""
    redirect = RedirectResponse(url="/", status_code=303)
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
        return RedirectResponse(url="/", status_code=303)

    # Filtrado por ROL:
    # - ADMIN ve todas las solicitudes no eliminadas.
    # - USER solo ve las que están en estado ACCEPTED o las que él mismo creó (aunque estén PENDING).
    if user["role"] == "ADMIN":
        solicitudes_visibles = [r for r in MOCK_REQUESTS if not r["deleted"]]
    else:
        solicitudes_visibles = [
            r for r in MOCK_REQUESTS 
            if not r["deleted"] and (r["status"] == "ACCEPTED" or r["user_email"] == user["email"])
        ]

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "solicitudes": solicitudes_visibles,
            "user": user
        }
    )

@app.get("/requests/new", response_class=HTMLResponse)
def pantalla_crear_solicitud(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="create_request.html", context={"user": user})

@app.post("/requests/new")
def crear_solicitud(
    request: Request,
    organizacion: str = Form(...),
    contacto: str = Form(...),
    descripcion: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    nueva_solicitud = {
        "id": len(MOCK_REQUESTS) + 1,
        "organizacion": organizacion,
        "contacto": contacto,
        "descripcion": descripcion,
        "status": "PENDING",
        "deleted": False,
        "user_email": user["email"]
    }
    MOCK_REQUESTS.append(nueva_solicitud)
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/requests/delete/{req_id}")
def borrar_solicitud(request: Request, req_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    for r in MOCK_REQUESTS:
        if r["id"] == req_id:
            # Solo se permite borrar si es ADMIN o si es el usuario dueño del registro
            if user["role"] == "ADMIN" or r["user_email"] == user["email"]:
                r["deleted"] = True
            break
    return RedirectResponse(url="/dashboard", status_code=303)

# ==========================================
# PANTALLAS ADMINISTRADOR
# ==========================================

@app.get("/admin", response_class=HTMLResponse)
def pantalla_admin(request: Request):
    user = get_current_user(request)
    # Bloqueo estricto si no es ADMIN
    if not user or user["role"] != "ADMIN":
        return RedirectResponse(url="/dashboard", status_code=303)

    solicitudes_eliminadas = [r for r in MOCK_REQUESTS if r["deleted"]]
    solicitudes_activas = [r for r in MOCK_REQUESTS if not r["deleted"]]

    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={
            "eliminadas": solicitudes_eliminadas,
            "todas": solicitudes_activas,
            "user": user
        }
    )

@app.post("/admin/status/{req_id}")
def cambiar_status(request: Request, req_id: int, status: str = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "ADMIN":
        return RedirectResponse(url="/dashboard", status_code=303)

    for r in MOCK_REQUESTS:
        if r["id"] == req_id:
            r["status"] = status
            break
    return RedirectResponse(url="/admin", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
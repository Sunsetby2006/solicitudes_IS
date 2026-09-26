import os
import shutil
from fastapi import FastAPI, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Solicitudes APP")

# Crear carpeta para subir imágenes custom
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory="templates")

# ==========================================
# BASE DE DATOS SIMULADA (MOCK EN MEMORIA)
# ==========================================
MOCK_REQUESTS = [
    {
        "id": 1,
        "organizacion": "Tech Corp",
        "contacto": "juan@tech.com",
        "descripcion": "Soporte para servidores",
        "status": "ACCEPTED", # Solo aceptadas se ven para usuarios normales
        "deleted": False,
        "imagen_url": "https://picsum.photos/400/225?random=1",
        "user_email": "usuario@gmail.com"
    },
    {
        "id": 2,
        "organizacion": "Dev Inc",
        "contacto": "ana@dev.com",
        "descripcion": "Licencia de software",
        "status": "PENDING", # No visible para usuarios normales
        "deleted": False,
        "imagen_url": "https://picsum.photos/400/225?random=2",
        "user_email": "otro@gmail.com"
    }
]

# Helper para obtener usuario actual desde Cookies
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
def login_google(response: Response, role: str = Form(...), email: str = Form(...)):
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
def verificar_mfa(request: Request, response: Response, codigo_otp: str = Form(...)):
    """Simulación de código de 6 dígitos que activa la sesión"""
    email = request.cookies.get("temp_email", "usuario@gmail.com")
    role = request.cookies.get("temp_role", "USER")

    redirect = RedirectResponse(url="/dashboard", status_code=303)
    redirect.set_cookie(key="user_email", value=email)
    redirect.set_cookie(key="user_role", value=role)
    return redirect

@app.get("/logout")
def logout():
    """Cerrar Sesión"""
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

    # REQUERIMIENTO 2: Usuarios normales SOLO ven las solicitudes 'ACCEPTED'
    if user["role"] == "ADMIN":
        solicitudes_visibles = [r for r in MOCK_REQUESTS if not r["deleted"]]
    else:
        # Si es usuario normal, también puede ver las suyas aunque estén PENDING
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

# REQUERIMIENTO 1: Crear solicitud con contacto (Gmail) y Subida de Foto Custom
@app.post("/requests/new")
async def crear_solicitud(
    request: Request,
    organizacion: str = Form(...),
    contacto: str = Form(...),
    descripcion: str = Form(...),
    imagen: UploadFile = File(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    # Guardar imagen en la carpeta uploads
    imagen_path = f"{UPLOAD_DIR}/{imagen.filename}"
    with open(imagen_path, "wb") as buffer:
        shutil.copyfileobj(imagen.file, buffer)

    nueva_solicitud = {
        "id": len(MOCK_REQUESTS) + 1,
        "organizacion": organizacion,
        "contacto": contacto, # Gmail / Contacto custom
        "descripcion": descripcion,
        "status": "PENDING", # Inicia como pendiente
        "deleted": False,
        "imagen_url": f"/{imagen_path}", # Ruta local de la imagen custom
        "user_email": user["email"]
    }
    MOCK_REQUESTS.append(nueva_solicitud)
    return RedirectResponse(url="/dashboard", status_code=303)

# REQUERIMIENTO 4: Usuario solo borra sus propias solicitudes
@app.post("/requests/delete/{req_id}")
def borrar_solicitud(request: Request, req_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    for r in MOCK_REQUESTS:
        if r["id"] == req_id:
            # Si es admin o si es el creador de la solicitud
            if user["role"] == "ADMIN" or r["user_email"] == user["email"]:
                r["deleted"] = True
            break
    return RedirectResponse(url="/dashboard", status_code=303)

# ==========================================
# PANTALLAS ADMINISTRADOR
# ==========================================

# REQUERIMIENTO 4: Bloquear pantalla Admin a Usuarios Normales
@app.get("/admin", response_class=HTMLResponse)
def pantalla_admin(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "ADMIN":
        return RedirectResponse(url="/dashboard", status_code=303) # Denegar acceso

    solicitudes_eliminadas = [r for r in MOCK_REQUESTS if r["deleted"]]
    solicitudes_todas = [r for r in MOCK_REQUESTS if not r["deleted"]]

    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={
            "eliminadas": solicitudes_eliminadas,
            "todas": solicitudes_todas,
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
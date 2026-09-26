from datetime import datetime

from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse
)

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from db import get_db
from modelos import Usuario, Solicitud, HistorialSolicitud


app = FastAPI(title="Sistema de Solicitudes")

templates = Jinja2Templates(directory="templates")


# ==========================================
# USUARIO ACTUAL
# ==========================================

def get_current_user(
    request: Request,
    db: Session
):
    user_email = request.cookies.get("user_email")

    if not user_email:
        return None

    user = (
        db.query(Usuario)
        .filter(
            Usuario.email == user_email,
            Usuario.esta_activo == True
        )
        .first()
    )

    return user


# ==========================================
# PANTALLA DE LOGIN
# ==========================================

@app.get("/", response_class=HTMLResponse)
def pantalla_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


# ==========================================
# LOGIN SIMULADO
# ==========================================

@app.post("/auth/google")
def login_google(
    role: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Login simulado.

    Busca al usuario en PostgreSQL.
    Si no existe, lo crea.
    """

    usuario = (
        db.query(Usuario)
        .filter(Usuario.email == email)
        .first()
    )

    if not usuario:

        usuario = Usuario(
            google_id=f"mock-{email}",
            email=email,
            nombre=email.split("@")[0],
            rol=role
        )

        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    else:

        usuario.rol = role
        usuario.ultlogin = datetime.now()

        db.commit()

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
# MFA
# ==========================================

@app.get("/auth/mfa", response_class=HTMLResponse)
def pantalla_mfa(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="mfa.html"
    )


@app.post("/auth/mfa/verify")
def verificar_mfa(
    request: Request,
    codigo_otp: str = Form(...)
):

    email = request.cookies.get("temp_email")

    role = request.cookies.get(
        "temp_role",
        "USER"
    )

    if not email:
        return RedirectResponse(
            url="/",
            status_code=303
        )

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
# DASHBOARD
# ==========================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
def pantalla_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

    if not user:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    if user.rol == "ADMIN":

        solicitudes_visibles = (
            db.query(Solicitud)
            .filter(
                Solicitud.borrado == False
            )
            .order_by(
                Solicitud.fecalta_sol.desc()
            )
            .all()
        )

    else:

        solicitudes_visibles = (
            db.query(Solicitud)
            .filter(
                Solicitud.borrado == False,
                (
                    (Solicitud.estatus == "Aceptado") |
                    (Solicitud.user_id == user.id)
                )
            )
            .order_by(
                Solicitud.fecalta_sol.desc()
            )
            .all()
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "solicitudes": solicitudes_visibles,
            "user": user
        }
    )


# ==========================================
# CREAR SOLICITUD - FORMULARIO
# ==========================================

@app.get(
    "/requests/new",
    response_class=HTMLResponse
)
def pantalla_crear_solicitud(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

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


# ==========================================
# CREAR SOLICITUD
# ==========================================

@app.post("/requests/new")
def crear_solicitud(
    request: Request,
    organizacion: str = Form(...),
    contacto: str = Form(...),
    descripcion: str = Form(...),
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

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
        user_id=user.id
    )

    db.add(nueva_solicitud)

    db.commit()

    db.refresh(nueva_solicitud)

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# BORRAR SOLICITUD
# ==========================================

@app.post("/requests/delete/{req_id}")
def borrar_solicitud(
    request: Request,
    req_id: int,
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

    if not user:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    solicitud = (
        db.query(Solicitud)
        .filter(
            Solicitud.id == req_id
        )
        .first()
    )

    if solicitud:

        es_admin = user.rol == "ADMIN"

        es_propietario = (
            solicitud.user_id == user.id
        )

        if es_admin or es_propietario:

            solicitud.borrado = True
            solicitud.fecborrado = datetime.now()

            db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ==========================================
# ADMIN
# ==========================================

@app.get(
    "/admin",
    response_class=HTMLResponse
)
def pantalla_admin(
    request: Request,
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

    if not user or user.rol != "ADMIN":

        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    solicitudes_eliminadas = (
        db.query(Solicitud)
        .filter(
            Solicitud.borrado == True
        )
        .order_by(
            Solicitud.fecborrado.desc()
        )
        .all()
    )

    solicitudes_activas = (
        db.query(Solicitud)
        .filter(
            Solicitud.borrado == False
        )
        .order_by(
            Solicitud.fecalta_sol.desc()
        )
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "eliminadas": solicitudes_eliminadas,
            "todas": solicitudes_activas,
            "user": user
        }
    )


# ==========================================
# CAMBIAR ESTATUS
# ==========================================

@app.post("/admin/status/{req_id}")
def cambiar_status(
    request: Request,
    req_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):

    user = get_current_user(request, db)

    if not user or user.rol != "ADMIN":

        return RedirectResponse(
            url="/dashboard",
            status_code=303
        )

    solicitud = (
        db.query(Solicitud)
        .filter(
            Solicitud.id == req_id
        )
        .first()
    )

    if solicitud:

        estatus_anterior = solicitud.estatus

        solicitud.estatus = status
        solicitud.fecact = datetime.now()

        historial = HistorialSolicitud(
            sol_id=solicitud.id,
            estatus_antiguo=estatus_anterior,
            estatus_actual=status,
            modificado_por=user.id
        )

        db.add(historial)

        db.commit()

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


# ==========================================
# EJECUCIÓN LOCAL
# ==========================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
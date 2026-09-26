from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text
)

from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()
request_status_enum = ENUM(
    "Pendiente",
    "Aceptado",
    "Rechazado",
    name="request_status",
    create_type=False
)

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    nombre = Column(String(255), nullable=False)
    perfil = Column(Text)
    rol = Column(String(20), nullable=False, default="USER")
    esta_activo = Column(Boolean, default=True)
    fecalta = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    ultlogin = Column(DateTime)
    solicitudes = relationship(
        "Solicitud",
        back_populates="usuario"
    )

class Solicitud(Base):
    __tablename__ = "solicitudes"
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    organizacion = Column(String(255), nullable=False)
    correo_contacto = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=False)
    estatus = Column(
        request_status_enum,
        nullable=False,
        default="Pendiente"
    )
    borrado = Column(Boolean, default=False)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
        nullable=False
    )
    fecalta_sol = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )
    fecact = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )
    fecborrado = Column(DateTime)
    usuario = relationship(
        "Usuario",
        back_populates="solicitudes"
    )
    historial = relationship(
        "HistorialSolicitud",
        back_populates="solicitud"
    )

class HistorialSolicitud(Base):
    __tablename__ = "historial_solicitudes"
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    sol_id = Column(
        Integer,
        ForeignKey("solicitudes.id"),
        nullable=False
    )
    estatus_antiguo = Column(
        request_status_enum
    )
    estatus_actual = Column(
        request_status_enum,
        nullable=False
    )
    modificado_por = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
        nullable=False
    )
    feccambio = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )
    solicitud = relationship(
        "Solicitud",
        back_populates="historial"
    )
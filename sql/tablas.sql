--modelo de estatus
CREATE TYPE request_status AS ENUM (
'Pendiente',
'Aceptado',
'Rechazado'
);

--usuarios
CREATE TABLE usuarios (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
google_id VARCHAR(255) UNIQUE NOT NULL,
email VARCHAR(255) UNIQUE NOT NULL,
nombre VARCHAR(255) NOT NULL,
perfil TEXT,
rol VARCHAR(20) NOT NULL DEFAULT 'USER',
esta_activo BOOLEAN DEFAULT TRUE,
fecalta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ultlogin TIMESTAMP
);

CREATE TABLE solicitudes (
id SERIAL PRIMARY KEY,
organizacion VARCHAR(255) NOT NULL,
correo_contacto VARCHAR(255) NOT NULL,
descripcion TEXT NOT NULL,
estatus request_status NOT NULL DEFAULT 'Pendiente',
borrado BOOLEAN DEFAULT FALSE,
user_id UUID NOT NULL,
fecalta_sol TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
fecact TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
fecborrado TIMESTAMP NULL,
CONSTRAINT fk_solicitud_usuario
FOREIGN KEY (user_id)
REFERENCES usuarios(id)
);

CREATE TABLE historial_solicitudes (
id SERIAL PRIMARY KEY,
sol_id INT NOT NULL,
estatus_antiguo request_status,
estatus_actual request_status NOT NULL,
modificado_por UUID NOT NULL,
feccambio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (sol_id)
REFERENCES solicitudes(id),
FOREIGN KEY (modificado_por)
REFERENCES usuarios(id)
);
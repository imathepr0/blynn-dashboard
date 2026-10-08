"""
Configuración central del backend de Blynn.

Todos los parámetros ajustables se definen aquí; se leen de variables de
entorno o del archivo `.env` (ver `.env.example`). Los secretos (clave
JWT, cadena de conexión) NUNCA se escriben en el código.
"""
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración del backend de Blynn."""

    # --- Información del servicio ---
    APP_NAME: str = "Blynn API"
    APP_VERSION: str = "0.1.0"

    # --- Entorno de ejecución ---
    # "development" (por defecto) o "production". En producción el
    # arranque exige más cosas (ver `validar_configuracion` más abajo).
    ENVIRONMENT: str = "development"

    # --- Base de datos (Etapa 1: Postgres, compatible con Supabase) ---
    # Se puede pegar tal cual la cadena de conexión que entrega Supabase
    # ("postgresql://..." o "postgres://..."): `app/db/session.py` la
    # convierte al formato que necesita SQLAlchemy con psycopg 3. Debe
    # venir SIEMPRE de una variable de entorno / archivo `.env`, nunca
    # escrita en el código. `None` = la base de datos no está configurada.
    DATABASE_URL: SecretStr | None = None
    # Pool de conexiones DENTRO de esta aplicación. Los valores bajos son
    # a propósito: el plan gratuito de Supabase limita las conexiones
    # simultáneas y el "pooler" de Supabase ya reparte las suyas.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT_SECONDS: float = 10.0
    # Recicla conexiones inactivas antes de que el pooler las corte.
    DB_POOL_RECYCLE_SECONDS: int = 300
    # True = sin pool propio (una conexión por operación). Útil si el
    # hosting escala a cero instancias; el pooler de Supabase hace el pool.
    DB_USE_NULL_POOL: bool = False

    # --- Autenticación propia (Etapa 2) ---
    # Clave que firma los tokens de acceso. Obligatoria, al menos 32
    # caracteres, sin valor por defecto a propósito (un valor por defecto
    # conocido permitiría a cualquiera fabricar tokens). Generar con:
    #   python -c "import secrets; print(secrets.token_urlsafe(64))"
    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ISSUER: str = "blynn-api"
    # Token de acceso: vida corta, porque no se puede revocar antes de
    # que venza (es "sin estado"). El refresh token (que sí se puede
    # revocar) es el que dura más.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Costo de bcrypt (2^N vueltas). 12 es un equilibrio razonable hoy;
    # las pruebas lo bajan a 4 solo para que la suite sea rápida.
    BCRYPT_ROUNDS: int = 12
    PASSWORD_MIN_LENGTH: int = 8

    # --- Límite de intentos (protección contra fuerza bruta) ---
    # Se guarda en memoria del proceso: sirve contra ataques simples pero
    # cada instancia del servidor cuenta por separado (ver README).
    AUTH_RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 900  # 15 minutos
    AUTH_MAX_FALLOS_POR_CUENTA: int = 5  # correo + IP
    AUTH_MAX_FALLOS_POR_IP: int = 30
    AUTH_MAX_REGISTROS_POR_IP: int = 10  # por ventana
    # Nombre de una cabecera que el hosting sobrescribe con la IP REAL del cliente (si no, detrás de
    # un proxy todos los usuarios comparten la IP del proxy y el límite por IP los bloquea a todos
    # juntos). Déjala vacía si no estás seguro de que el hosting la sobrescriba.
    TRUSTED_CLIENT_IP_HEADER: str | None = None

    # --- Límites de la API ---
    # Tamaño máximo del cuerpo de una petición (1 MiB). Suficiente para
    # cualquier JSON de la app. Las imágenes del escaneo tienen su propio
    # límite, solo para su ruta (ver OCR_MAX_IMAGE_BYTES).
    MAX_REQUEST_BODY_BYTES: int = 1_048_576

    # --- Escaneo de boletas (Etapa 4) ---
    # Dirección BASE del servicio de escaneo (boletas-backend), sin ruta:
    # "https://escaner-de-boletas-cl.onrender.com". `None` = el escaneo
    # está desactivado y el endpoint responde 503.
    OCR_SERVICE_URL: str | None = None
    # Clave compartida que este backend envía al servicio de escaneo en la
    # cabecera X-Service-Key. Opcional mientras el escáner siga público;
    # cuando el escáner la exija, es lo que impide que lo use cualquiera.
    OCR_SERVICE_KEY: SecretStr | None = None
    # Tiempo máximo TOTAL de un escaneo: despertar el servicio si estaba
    # dormido (el plan gratuito de Render lo apaga por inactividad) + el
    # procesamiento de la foto. Debe ser MAYOR que el límite del propio
    # escáner (su MAX_PROCESSING_TIME_SECONDS + TIMEOUT_MARGEN_SEGUNDOS; por
    # defecto 330 s) o este backend se rinde mientras el escáner sigue
    # gastando CPU. Con 90 s configurados en el escáner (corte duro a los
    # 120 s) quedan 60 s para despertarlo.
    OCR_SERVICE_TIMEOUT_SECONDS: float = 180.0
    # Tamaño máximo de la imagen (el mismo que acepta el escáner: 10 MiB).
    OCR_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    # Cada foto cuesta hasta 30 s de CPU del escáner: se limita por usuario.
    OCR_MAX_ESCANEOS_POR_USUARIO: int = 10
    OCR_RATE_LIMIT_WINDOW_SECONDS: int = 600  # 10 minutos

    # --- CORS: orígenes permitidos para el consumo desde el frontend ---
    # Formato en .env (JSON): CORS_ORIGINS=["https://blynn.cl"]
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://blynn-dashboard.vercel.app",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de Settings (patrón singleton simple)."""
    return Settings()


class ConfiguracionInvalidaError(RuntimeError):
    """La configuración no es segura o está incompleta para arrancar."""


def validar_configuracion(settings: Settings) -> None:
    """Falla al ARRANCAR (no en la primera petición) si la configuración
    de autenticación es insegura o falta algo esencial.

    Es preferible que el servidor no levante a que levante con una clave
    débil o con CORS abierto sin que nadie se dé cuenta.
    """
    problemas: list[str] = []

    clave = settings.JWT_SECRET_KEY.get_secret_value() if settings.JWT_SECRET_KEY else ""
    if len(clave) < 32:
        problemas.append(
            "JWT_SECRET_KEY falta o tiene menos de 32 caracteres. Genera una con: "
            'python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    if settings.ENVIRONMENT == "production":
        if not settings.DATABASE_URL:
            problemas.append("DATABASE_URL es obligatoria en producción.")
        if "*" in settings.CORS_ORIGINS:
            problemas.append(
                'CORS_ORIGINS no puede contener "*" en producción (se usan credenciales).'
            )

    url_escaner = (settings.OCR_SERVICE_URL or "").strip()
    if url_escaner and not url_escaner.lower().startswith(("http://", "https://")):
        problemas.append("OCR_SERVICE_URL debe empezar con https:// (o http:// solo en desarrollo).")
    if settings.ENVIRONMENT == "production":
        if url_escaner and not url_escaner.lower().startswith("https://"):
            problemas.append(
                "OCR_SERVICE_URL debe empezar con https:// en producción "
                "(la imagen de la boleta y la clave de servicio viajarían sin cifrar)."
            )
        clave_escaner = settings.OCR_SERVICE_KEY.get_secret_value().strip() if settings.OCR_SERVICE_KEY else ""
        if clave_escaner and len(clave_escaner) < 24:
            problemas.append("OCR_SERVICE_KEY es demasiado corta (mínimo 24 caracteres).")

    if problemas:
        detalle = "\n  - ".join(problemas)
        raise ConfiguracionInvalidaError(f"Configuración inválida:\n  - {detalle}")

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import BASE_DIR, settings
from app import preconciliation_audit
from app.database import SessionLocal, get_db
from app.schema_validation import validar_esquema_mysql
from app.local_count_store import inicializar_conteo_local
from app.preconciliation_store import notas_inventario
from app.local_reconciliation_store import inicializar_conciliaciones_local
from app.local_recount_store import inicializar_reconteos_local
from app.local_closing_store import (
    inicializar_cierres_local,
    sincronizar_cierres_local,
)
from app.models import CausaDiferencia, Inventario
from app.serializers import inventario_dict
from app.routers.api import router as api_router
from app.services.print_sheet import (
    filas_ciclico_impresion,
    filas_detalle_impresion,
    filas_materia_prima_impresion,
    filas_planilla_impresion,
)
from app.services.indicator_settings import (
    asegurar_configuracion,
    cargar_configuracion,
)
from app.services.catalogs import asegurar_catalogos
from app.services.print_formats import (
    asegurar_formatos_impresion,
    resolver_version_para_inventario,
    version_dict,
    versiones_para_formato,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    validar_esquema_mysql()
    inicializar_conteo_local()
    inicializar_conciliaciones_local()
    inicializar_reconteos_local()
    inicializar_cierres_local()
    with SessionLocal() as db:
        asegurar_configuracion(db)
        asegurar_formatos_impresion(db)
        asegurar_catalogos(db)
        sincronizar_cierres_local(db)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.93.10",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "app" / "static"),
    name="static",
)

templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
app.include_router(api_router)

FORMATOS_IMPRESION = {
    "CICLICO",
    "FLUJO_HORIZONTAL",
    "RESUMEN_VERTICAL",
    "DETALLE_ETAPAS",
    "LISTADO_SIMPLE",
    "MATERIA_PRIMA",
    "MEDIOS",
}


def resolver_formato_impresion(
    formato: str | None,
    categoria: str,
) -> str:
    if not formato:
        if categoria == "MATERIA_PRIMA":
            return "MATERIA_PRIMA"
        if categoria == "CICLICO":
            return "CICLICO"
        return "FLUJO_HORIZONTAL"
    formato = formato.strip().upper()
    if formato not in FORMATOS_IMPRESION:
        raise HTTPException(
            status_code=400,
            detail="Formato de impresión no válido",
        )
    if categoria == "MATERIA_PRIMA" and formato not in {
        "MATERIA_PRIMA",
        "LISTADO_SIMPLE",
    }:
        raise HTTPException(
            status_code=400,
            detail="Ese formato no corresponde a un inventario de materia prima",
        )
    if categoria != "MATERIA_PRIMA" and formato == "MATERIA_PRIMA":
        raise HTTPException(
            status_code=400,
            detail="Ese formato sólo corresponde a materia prima",
        )
    if formato == "MEDIOS" and categoria != "PIEZAS":
        raise HTTPException(
            status_code=400,
            detail="El formato de medios sólo corresponde a piezas.",
        )
    if categoria == "CICLICO" and formato not in {
        "CICLICO",
        "RESUMEN_VERTICAL",
        "DETALLE_ETAPAS",
        "LISTADO_SIMPLE",
    }:
        raise HTTPException(
            status_code=400,
            detail="Ese formato no corresponde a un inventario cíclico",
        )
    if categoria != "CICLICO" and formato == "CICLICO":
        raise HTTPException(
            status_code=400,
            detail="Ese formato sólo corresponde a un inventario cíclico",
        )
    return formato


@app.middleware("http")
async def evitar_cache_local(request: Request, call_next):
    response = await call_next(request)
    if (
        request.url.path in {
            "/",
            "/inventarios",
            "/programados",
            "/plantillas",
            "/conciliaciones",
            "/analisis-stock",
            "/reportes",
            "/configuracion",
            "/configuracion/causas",
            "/configuracion/indicadores",
            "/configuracion/planillas",
            "/configuracion/catalogos",
        }
        or request.url.path.startswith("/static/js/")
        or request.url.path.startswith("/static/css/")
        or request.url.path.endswith("/preconciliacion")
        or request.url.path.endswith("/movil")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/", include_in_schema=False)
def pagina_principal():
    return RedirectResponse("/inventarios")


@app.get("/mobile-sw.js", include_in_schema=False)
def mobile_service_worker():
    return FileResponse(
        BASE_DIR / "app" / "static" / "js" / "mobile-sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/",
        },
    )


def pagina_operativa(request: Request, vista: str):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "vista_inicial": vista,
        },
    )


@app.get("/inventarios", response_class=HTMLResponse, include_in_schema=False)
def pagina_inventarios(request: Request):
    return pagina_operativa(request, "inventarios")


@app.get("/movil", response_class=HTMLResponse, include_in_schema=False)
def pagina_portal_movil(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="mobile_home.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/inventarios/{inventario_id}/movil",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_conteo_movil(inventario_id: int, request: Request):
    return templates.TemplateResponse(
        request=request,
        name="mobile_count.html",
        context={
            "app_name": settings.APP_NAME,
            "inventario_id": inventario_id,
        },
    )


@app.get(
    "/inventarios/{inventario_id}/preconciliacion",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_preconciliacion(
    inventario_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    inventario = db.get(Inventario, inventario_id)
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    return templates.TemplateResponse(
        request=request,
        name="preconciliation.html",
        context={
            "app_name": settings.APP_NAME,
            "inventario_id": inventario_id,
            "inventario_codigo": inventario.codigo,
        },
    )


@app.get(
    "/analisis-stock",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_analisis_stock(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="preconciliation.html",
        context={
            "app_name": settings.APP_NAME,
            "inventario_id": "",
            "inventario_codigo": "",
        },
    )


@app.get(
    "/inventarios/{inventario_id}/difusion",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_difusion_inventario(
    inventario_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    inventario = db.scalar(
        select(Inventario)
        .options(selectinload(Inventario.items))
        .where(Inventario.id == inventario_id)
    )
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    causas = db.scalars(
        select(CausaDiferencia)
        .where(CausaDiferencia.activa.is_(True))
        .order_by(CausaDiferencia.orden, CausaDiferencia.nombre)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="inventory_diffusion.html",
        context={
            "app_name": settings.APP_NAME,
            "inventario": inventario_dict(inventario),
            "causas": {
                causa.codigo: causa.nombre
                for causa in causas
            },
            "configuracion": cargar_configuracion(db),
        },
    )


@app.get(
    "/inventarios/{inventario_id}/preconciliacion/difusion",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_difusion_preconciliacion(
    inventario_id: int,
    analisis: str,
    request: Request,
    inicial: int | None = None,
    db: Session = Depends(get_db),
):
    inventario = db.scalar(
        select(Inventario).where(Inventario.id == inventario_id)
    )
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    guardado = preconciliation_audit.get_analysis(analisis)
    if guardado is None:
        raise HTTPException(status_code=404, detail="Análisis guardado no encontrado")
    if int(guardado["final_id"]) != inventario_id:
        raise HTTPException(
            status_code=422,
            detail="El análisis no corresponde al inventario indicado",
        )
    escenarios = guardado.get("calculo", {}).get("escenarios", [])
    escenario = next(
        (
            item for item in escenarios
            if inicial is None or int(item.get("inicial", {}).get("id", 0)) == inicial
        ),
        None,
    )
    if escenario is None:
        raise HTTPException(
            status_code=404,
            detail="El escenario inicial no pertenece al análisis guardado",
        )
    causas = db.scalars(
        select(CausaDiferencia).order_by(
            CausaDiferencia.orden,
            CausaDiferencia.nombre,
        )
    ).all()
    calculo = guardado["calculo"]
    return templates.TemplateResponse(
        request=request,
        name="preconciliation_diffusion.html",
        context={
            "app_name": settings.APP_NAME,
            "inventario": {
                "id": inventario.id,
                "codigo": inventario.codigo,
                "cliente": inventario.cliente,
                "fecha": inventario.fecha.isoformat(),
                "responsable": inventario.responsable,
                "estado": inventario.estado,
            },
            "analisis": {
                "id": guardado["id"],
                "nombre": guardado["nombre"],
                "actualizado_en": guardado["actualizado_en"],
            },
            "escenario": escenario,
            "notas": notas_inventario(inventario_id),
            "movimientos": calculo.get("movimientos", []),
            "causas": {causa.codigo: causa.nombre for causa in causas},
            "configuracion": cargar_configuracion(db),
        },
    )


@app.get("/programados", response_class=HTMLResponse, include_in_schema=False)
def pagina_programados(request: Request):
    return pagina_operativa(request, "programados")


@app.get("/plantillas", response_class=HTMLResponse, include_in_schema=False)
def pagina_plantillas(request: Request):
    return pagina_operativa(request, "plantillas")


@app.get(
    "/conciliaciones",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_conciliaciones(request: Request):
    return pagina_operativa(request, "conciliaciones")


@app.get("/reportes", response_class=HTMLResponse, include_in_schema=False)
def pagina_reportes(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/configuracion",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def configurar_sistema(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings_home.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/configuracion/causas",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def configurar_causas(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cause_settings.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/configuracion/indicadores",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def configurar_indicadores(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="indicator_settings.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/configuracion/planillas",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def configurar_planillas(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="print_format_editor.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get(
    "/configuracion/catalogos",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def configurar_catalogos(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="catalog_settings.html",
        context={"app_name": settings.APP_NAME},
    )


@app.get("/plantillas/nueva", response_class=HTMLResponse, include_in_schema=False)
def nueva_plantilla(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="template_editor.html",
        context={
            "app_name": settings.APP_NAME,
            "plantilla_id": "",
            "modo": "nueva",
        },
    )


@app.get(
    "/plantillas/{plantilla_id}/editar",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def editar_plantilla(plantilla_id: int, request: Request):
    return templates.TemplateResponse(
        request=request,
        name="template_editor.html",
        context={
            "app_name": settings.APP_NAME,
            "plantilla_id": plantilla_id,
            "modo": "editar",
        },
    )


@app.get(
    "/inventarios/{inventario_id}/imprimir",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def imprimir_inventario(
    inventario_id: int,
    request: Request,
    formato: str | None = None,
    version_id: int | None = None,
    db: Session = Depends(get_db),
):
    inventario = db.scalar(
        select(Inventario)
        .where(Inventario.id == inventario_id)
        .options(selectinload(Inventario.items))
    )
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")

    formato_resuelto = resolver_formato_impresion(
        formato or inventario.formato_impresion,
        inventario.categoria,
    )
    version = resolver_version_para_inventario(
        db,
        inventario,
        formato_resuelto,
        version_id,
    )
    if version_id is not None and version is None:
        raise HTTPException(
            status_code=404,
            detail="La versión elegida no corresponde a este formato",
        )
    versiones = versiones_para_formato(db, formato_resuelto)
    return templates.TemplateResponse(
        request=request,
        name="print_inventory.html",
        context={
            "inventario": inventario,
            "piezas": filas_planilla_impresion(inventario),
            "detalle": filas_detalle_impresion(inventario),
            "materiales": filas_materia_prima_impresion(inventario),
            "ciclico": filas_ciclico_impresion(inventario),
            "formato_impresion": formato_resuelto,
            "diseno_impresion": version_dict(version) if version else None,
            "versiones_impresion": [
                version_dict(item) for item in versiones
            ],
        },
    )


@app.get(
    "/inventarios/codigo/{codigo}/imprimir",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def imprimir_inventario_por_codigo(
    codigo: str,
    request: Request,
    formato: str | None = None,
    version_id: int | None = None,
    db: Session = Depends(get_db),
):
    inventario = db.scalar(
        select(Inventario)
        .where(Inventario.codigo == codigo)
        .options(selectinload(Inventario.items))
    )
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")

    formato_resuelto = resolver_formato_impresion(
        formato or inventario.formato_impresion,
        inventario.categoria,
    )
    version = resolver_version_para_inventario(
        db,
        inventario,
        formato_resuelto,
        version_id,
    )
    if version_id is not None and version is None:
        raise HTTPException(
            status_code=404,
            detail="La versión elegida no corresponde a este formato",
        )
    versiones = versiones_para_formato(db, formato_resuelto)
    return templates.TemplateResponse(
        request=request,
        name="print_inventory.html",
        context={
            "inventario": inventario,
            "piezas": filas_planilla_impresion(inventario),
            "detalle": filas_detalle_impresion(inventario),
            "materiales": filas_materia_prima_impresion(inventario),
            "ciclico": filas_ciclico_impresion(inventario),
            "formato_impresion": formato_resuelto,
            "diseno_impresion": version_dict(version) if version else None,
            "versiones_impresion": [
                version_dict(item) for item in versiones
            ],
        },
    )


@app.get("/salud", tags=["Sistema"])
def salud():
    return {"estado": "ok", "aplicacion": settings.APP_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )

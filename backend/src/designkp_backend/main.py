from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from designkp_backend.api.routers.admin_storage import router as admin_storage_router
from designkp_backend.api.routers.base_formulas import router as base_formulas_router
from designkp_backend.api.routers.categories import router as categories_router
from designkp_backend.api.routers.internal_part_groups import router as internal_part_groups_router
from designkp_backend.api.routers.orders import router as orders_router
from designkp_backend.api.routers.order_designs import router as order_designs_router
from designkp_backend.api.routers.part_formulas import router as part_formulas_router
from designkp_backend.api.routers.params import router as params_router
from designkp_backend.api.routers.param_groups import router as param_groups_router
from designkp_backend.api.routers.part_kinds import router as part_kinds_router
from designkp_backend.api.routers.sub_categories import router as sub_categories_router
from designkp_backend.api.routers.sub_category_designs import router as sub_category_designs_router
from designkp_backend.api.routers.templates import router as templates_router
from designkp_backend.db.models import import_model_modules


app = FastAPI(title="DesignKP Backend", version="0.1.0")

import_model_modules()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(admin_storage_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(order_designs_router, prefix="/api")
app.include_router(part_kinds_router, prefix="/api")
app.include_router(param_groups_router, prefix="/api")
app.include_router(params_router, prefix="/api")
app.include_router(base_formulas_router, prefix="/api")
app.include_router(part_formulas_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(sub_categories_router, prefix="/api")
app.include_router(sub_category_designs_router, prefix="/api")
app.include_router(internal_part_groups_router, prefix="/api")

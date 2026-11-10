"""GET /api/tabs: the five tabs with the SPEC label of each screen and the P10 status line (spec.tabs)."""

from fastapi import APIRouter

from argus_workbench.spec import tabs

router = APIRouter()


@router.get("/api/tabs")
def get_tabs() -> dict:
    return {"tabs": tabs()}

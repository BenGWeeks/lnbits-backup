from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from lnbits.core.models import User
from lnbits.decorators import check_admin, check_user_exists
from lnbits.helpers import template_renderer
from starlette.responses import HTMLResponse, FileResponse

backup_generic_router = APIRouter()


def backup_renderer():
    return template_renderer(["backup/templates"])


@backup_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_admin)):
    """Main backup management page (admin only)"""
    return backup_renderer().TemplateResponse(
        "backup/index.html", {"request": request, "user": user.json()}
    )


@backup_generic_router.get("/description.md")
async def description():
    """Serve the extension description markdown file"""
    description_file = Path(__file__).parent / "description.md"
    return FileResponse(
        description_file,
        media_type="text/markdown",
        headers={"Content-Disposition": "inline"}
    )

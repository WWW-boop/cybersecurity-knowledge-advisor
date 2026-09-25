"""FastAPI dependencies shared by API routers."""

from typing import Annotated

from fastapi import Depends

from cybersecurity_advisor.config.settings import Settings, get_settings

SettingsDependency = Annotated[Settings, Depends(get_settings)]

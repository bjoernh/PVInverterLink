from typing import Optional
from pydantic.dataclasses import dataclass
from fastapi_users import schemas
from solar_backend.db import User



class UserRead(schemas.BaseUser[int]):
    first_name: str
    last_name: str


class UserCreate(schemas.BaseUserCreate):
    first_name: str
    last_name: str


class UserUpdate(schemas.BaseUserUpdate):
    first_name: str
    last_name: str


@dataclass
class InverterAdd:
        name: str
        serial: str


@dataclass
class InverterAddMetadata:
        rated_power: int
        number_of_mppts: int

@dataclass
class Inverter:
    id: int
    name: str
    serial_logger: str
    sw_version: str
    user: schemas.BaseUser[int]
    current_power: Optional[int] = None
    last_update: Optional[str] = None
    rated_power: Optional[int] = None
    number_of_mppts: Optional[int] = None


@dataclass
class InverterMetadataResponse:
    id: int
    serial_logger: str
    name: str
    rated_power: Optional[int]
    number_of_mppts: Optional[int]
    sw_version: str

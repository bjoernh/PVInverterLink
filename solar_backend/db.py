from typing import AsyncGenerator, List, Optional
import contextlib

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from sqlalchemy import ForeignKey, Integer, String, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import settings


class Base(DeclarativeBase):
    pass

class Inverter(Base):
    __tablename__ = "inverter"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(ForeignKey("user.id"))
    users = relationship("User", back_populates="inverters")
    name: Mapped[str] = mapped_column(String)
    serial_logger: Mapped[str] = mapped_column(String)
    influx_bucked_id: Mapped[Optional[str]]
    sw_version: Mapped[Optional[str]] = mapped_column(String)
    
    def __repr__(self):
        return f"{self.id} - {self.name}"
    
    class Config:
        orm_mode = True

class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inverters = relationship("Inverter", back_populates="users")
    first_name: Mapped[str]  = mapped_column(String(32))
    last_name: Mapped[str] = mapped_column(String(32))
    influx_url: Mapped[str] = mapped_column(String(64), default=settings.INFLUX_URL)
    influx_org_id: Mapped[Optional[str]]
    influx_token: Mapped[Optional[str]]
    
    def __repr__(self):
        return f"{self.id} - {self.first_name} {self.last_name}"


engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
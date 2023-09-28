from typing import AsyncGenerator, List, Optional, AsyncIterator
import contextlib
from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from solar_backend.config import settings, DEBUG


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
    tmp_pass: Mapped[Optional[str]]
    
    def __repr__(self):
        return f"{self.id} - {self.first_name} {self.last_name}"

class DatabaseSessionManager:
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None

    def init(self, host: str):
        self._engine = create_async_engine(host, echo=DEBUG)
        self._sessionmaker = async_sessionmaker(autocommit=False, bind=self._engine)

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # Used for testing
    async def create_all(self, connection: AsyncConnection):
        await connection.run_sync(Base.metadata.create_all)

    async def drop_all(self, connection: AsyncConnection):
        await connection.run_sync(Base.metadata.drop_all)

sessionmanager = DatabaseSessionManager()


engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmanager.session() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
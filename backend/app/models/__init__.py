from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VehicleInfo(Base):
    __tablename__ = "vehicle_info"

    vehicle_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    capacity: Mapped[float] = mapped_column(Float, default=100.0)
    soc: Mapped[float] = mapped_column(Float, default=1.0)
    soh: Mapped[float] = mapped_column(Float, default=1.0)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TaskInfo(Base):
    __tablename__ = "task_info"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    location: Mapped[str] = mapped_column(String(128))
    demand: Mapped[float] = mapped_column(Float, default=0.0)
    service_time: Mapped[float] = mapped_column(Float, default=0.0)
    time_window_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_window_end: Mapped[float | None] = mapped_column(Float, nullable=True)


class ChargeStation(Base):
    __tablename__ = "charge_station"

    station_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=1.0)
    queue: Mapped[int] = mapped_column(Integer, default=0)


class ScheduleResult(Base):
    __tablename__ = "schedule_result"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    runtime: Mapped[float] = mapped_column(Float, default=0.0)
    route_data: Mapped[str | None] = mapped_column(String, nullable=True)

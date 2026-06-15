from pydantic import BaseModel, Field


class VehicleBase(BaseModel):
    vehicle_id: str
    capacity: float = 100.0
    soc: float = Field(default=1.0, ge=0.0, le=1.0)
    soh: float = Field(default=1.0, ge=0.0, le=1.0)
    location: str | None = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    capacity: float | None = None
    soc: float | None = Field(default=None, ge=0.0, le=1.0)
    soh: float | None = Field(default=None, ge=0.0, le=1.0)
    location: str | None = None


class VehicleResponse(VehicleBase):
    class Config:
        from_attributes = True

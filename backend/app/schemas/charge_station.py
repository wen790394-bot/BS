from pydantic import BaseModel


class ChargeStationBase(BaseModel):
    station_id: str
    location: str | None = None
    price: float = 1.0
    queue: int = 0


class ChargeStationCreate(ChargeStationBase):
    pass


class ChargeStationResponse(ChargeStationBase):
    class Config:
        from_attributes = True

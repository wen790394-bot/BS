from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChargeStation
from app.schemas.charge_station import ChargeStationCreate, ChargeStationResponse

router = APIRouter()


@router.get("/", response_model=list[ChargeStationResponse])
def list_stations(db: Session = Depends(get_db)):
    return db.query(ChargeStation).all()


@router.post("/", response_model=ChargeStationResponse)
def create_station(payload: ChargeStationCreate, db: Session = Depends(get_db)):
    if db.get(ChargeStation, payload.station_id):
        raise HTTPException(status_code=400, detail="充电站已存在")
    station = ChargeStation(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TaskInfo
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter()


@router.get("/", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(TaskInfo).all()


@router.post("/", response_model=TaskResponse)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    if db.get(TaskInfo, payload.task_id):
        raise HTTPException(status_code=400, detail="订单已存在")
    task = TaskInfo(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(TaskInfo, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="订单不存在")
    return task


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(TaskInfo, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="订单不存在")
    db.delete(task)
    db.commit()
    return {"message": "删除成功"}

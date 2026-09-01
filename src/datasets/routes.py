from fastapi import APIRouter, status, Depends, Query, BackgroundTasks, UploadFile, File
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional
from fastapi.exceptions import HTTPException
from .schemas import (
    PaginationEquipmentResponse,
    DatasetUploadResponse,
    DatasetUpdate,
    DatasetDetailResponse,
    DatasetStatistics,
    ParameterStatistics,
)
from src.db.main import get_session
from .service import DatasetService
import uuid
from src.error import DatasetNotFound
from src.auth.authorization import require_dataset_owner
from src.db.models import Dataset, User
from src.auth.authorization import (
    get_current_user,
    require_dataset_owner,
    require_admin,
    require_verified_user,
    require_dataset_delete_permission,
)

dataset_service = DatasetService()

dataset_router = APIRouter()


@dataset_router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_session),
):
    return await dataset_service.upload_dataset(
        file=file,
        current_user=current_user,
        session=session,
        background_tasks=background_tasks,
    )

@dataset_router.get("/",response_model= PaginationEquipmentResponse)
async def get_all_datasets(current_user: User = Depends(get_current_user),session:AsyncSession = Depends(get_session),page:int = Query(default=1,ge=1)
                            ,page_size:int = Query(default=5,ge=1,le=100)):
    
    return await dataset_service.get_all_datasets(session,current_user.uid,page,page_size)


@dataset_router.get("/{dataset_uid}",response_model=DatasetDetailResponse)
async def get_dataset(dataset_uid: uuid.UUID,session: AsyncSession = Depends(get_session),dataset: Dataset = Depends(get_current_user)) -> dict:

    dataset = await dataset_service.get_dataset(dataset_uid,session)

    if dataset:
        return DatasetDetailResponse(
            uid = dataset.uid,
            original_filename = dataset.original_filename,
            stored_filename = dataset.stored_filename,
            file_path = dataset.file_path,
            equipment_count = dataset.equipment_count,
            statistics= DatasetStatistics(
                flowrate=ParameterStatistics(
                    min=dataset.min_flowrate,
                    max=dataset.max_flowrate,
                    average=dataset.average_flowrate
                ),
                pressure = ParameterStatistics(
                    min=dataset.min_pressure,
                    max=dataset.max_pressure,
                    average=dataset.average_pressure
                ),
                temperature=ParameterStatistics(
                    min=dataset.min_temperature,
                    max= dataset.max_temperature,
                    average= dataset.average_temperature
                )
            ),
            equipment_summary=dataset.equipment_summary,
            inactive_equipment=dataset.inactive_equipment,
            missing_data=dataset.missing_data,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
    else:
        raise DatasetNotFound()
    
@dataset_router.patch("/{dataset_uid}",response_model=DatasetDetailResponse)
async def update_dataset(dataset_uid: uuid.UUID,dataset_update_data: DatasetUpdate,
                         dataset: Dataset = Depends(require_dataset_owner),
                         session: AsyncSession = Depends(get_session))->dict:
    update_dataset = await dataset_service.update_dataset(dataset_uid,dataset_update_data,session)

    if update_dataset is None:
        raise DatasetNotFound()
    else:
        return DatasetDetailResponse(
    uid=update_dataset.uid,
    original_filename=update_dataset.original_filename,
    stored_filename=update_dataset.stored_filename,
    file_path=update_dataset.file_path,
    equipment_count=update_dataset.equipment_count,

    statistics=DatasetStatistics(
        flowrate=ParameterStatistics(
            min=update_dataset.min_flowrate,
            max=update_dataset.max_flowrate,
            average=update_dataset.average_flowrate,
        ),
        pressure=ParameterStatistics(
            min=update_dataset.min_pressure,
            max=update_dataset.max_pressure,
            average=update_dataset.average_pressure,
        ),
        temperature=ParameterStatistics(
            min=update_dataset.min_temperature,
            max=update_dataset.max_temperature,
            average=update_dataset.average_temperature,
        ),
    ),
    equipment_summary=update_dataset.equipment_summary,
    inactive_equipment=update_dataset.inactive_equipment,
    missing_data=update_dataset.missing_data,

    created_at=update_dataset.created_at,
    updated_at=update_dataset.updated_at,)
    

@dataset_router.delete("/{dataset_uid}")
async def delete_dataset(dataset: Dataset = Depends(require_dataset_delete_permission),session: AsyncSession = Depends(get_session)):
    dataset_to_delete = await dataset_service.delete_dataset(dataset.uid,session)
    if dataset_to_delete is None:
        raise DatasetNotFound()
    return{
        "message":"dataset deleted successfully."
    }
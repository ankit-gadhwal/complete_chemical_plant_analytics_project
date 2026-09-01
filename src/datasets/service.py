import uuid
from .schemas import DatasetUpdate,DatasetUploadResponse,UploadedFileInfo,DatasetSummary
from sqlmodel import select,desc
from sqlalchemy.ext.asyncio import AsyncSession
import shutil
from src.db.models import Dataset, Equipment,Datasetstatus,User
from pathlib import Path
from fastapi import UploadFile, status, BackgroundTasks
from fastapi.exceptions import HTTPException
import pandas as pd
from datetime import datetime
from src.error import (NoFileSelected,InvalidFileExtension,
                       InvalidContentType,FileTooLarge,CSVReadError,MissingCSVColumns,DuplicateDatasetException)
from sqlalchemy import func
import math
from src.logger import logger


class DatasetService:
    
    REQUIRED_COLUMNS = {
        "Equipment Name",
        "Type",
        "Flowrate",
        "Pressure",
        "Temperature"
    }
    MAX_FILE_SIZE = 5 * 1024 * 1024
    UPLOAD_DIR = Path("storage/uploads")
    ALLOWED_EXTENSIONS = {".csv"}
    ALLOWED_CONTENT_TYPES = {
        "text/csv",
        "application/vnd.ms-excel"
    }
    
    def validate_equipment_data(
            self,dataframe:pd.DataFrame,
    ):
        logger.info("Checking equipment data for missing values")
        missing_data = []
        inactive_equipment =[]
        valid_dataframe = dataframe.copy()

        important_columns = [
            "Flowrate",
            "Pressure",
            "Temperature"
        ]
        for index,row in dataframe.iterrows():
            missing_columns = []
            for column in important_columns:
                if pd.isna(row[column]):
                    missing_columns.append(column)
            eq_name = str(row.get("Equipment Name") or row.get("equipment_name", "Unknown"))
            eq_type = str(row.get("Type") or row.get("type", "Unknown"))
            if len(missing_columns) == len(important_columns):
                inactive_equipment.append(
                    {
                        "equipment_name": eq_name,
                        "equipment_type": eq_type,
                        "reason": "All operating parameters are missing (Equipment Offline)."
                    }
                )
                valid_dataframe = valid_dataframe.drop(index)
            elif len(missing_columns) > 0:
                missing_data.append(
                    {
                        "equipment_name": eq_name,
                        "equipment_type": eq_type,
                        "missing_columns": missing_columns
                    }
                )
                valid_dataframe = valid_dataframe.drop(index)
        logger.info(
            f"Inactive Equipment: {len(inactive_equipment)}, "
            f"Equipment with partial missing data: {len(missing_data)}")
        return (valid_dataframe,inactive_equipment,missing_data)
    
    def calculate_dataset_summary(self,dataframe:pd.DataFrame)->DatasetSummary:
        logger.info("Calculating dataset summary")
        logger.info(
            f"Equipment Count={len(dataframe)} "
            f"Average Pressure={round(float(dataframe['Pressure'].mean()),2)}")
        return DatasetSummary(
            equipment_count = len(dataframe),
            average_flowrate = round(float(dataframe["Flowrate"].mean()),2),
            average_pressure =round(float(dataframe["Pressure"].mean()),2),
            average_temperature = round(float(dataframe["Temperature"].mean()),2),
            min_flowrate =  float(dataframe["Flowrate"].min()),
            max_flowrate = float(dataframe["Flowrate"].max()),
            min_pressure = float(dataframe["Pressure"].min()),
            max_pressure = float(dataframe["Pressure"].max()),
            min_temperature = float(dataframe["Temperature"].min()),
            max_temperature = float(dataframe["Temperature"].max()),
            equipment_summary =  (
                dataframe["Type"].value_counts().to_dict()
            )
        )
    def validate_uploaded_file(self,file: UploadFile) -> None:

        # Check filename
        if not file.filename:
            raise NoFileSelected()
        logger.info(f"Validating uploaded file: {file.filename}")
        # Check extension
        extension = Path(file.filename).suffix.lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            logger.warning(f"Invalid file extension: {file.filename}")
            raise InvalidFileExtension()
        
        # check content type
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            logger.warning("Unsupported content type")
            raise InvalidContentType()
        
        # check file size
        file.file.seek(0,2)  # Move to end
        file_size = file.file.tell() # Current position = size in bytes
        file.file.seek(0)  # Reset back to beginning 
        if file_size > self.MAX_FILE_SIZE:
            logger.warning("File size exceeds 5 MB")
            raise FileTooLarge()
    
    def read_csv_file(self,file_path: str) -> pd.DataFrame:
        try:
            logger.info(f"Reading CSV file: {file_path}")
            dataframe = pd.read_csv(file_path)
            return dataframe
        
        except Exception as e:
            logger.exception(f"Failed to read CSV: {file_path}")
            raise CSVReadError()
        
    def validate_csv_columns(self,dataframe:pd.DataFrame):
        logger.info("Validating CSV columns")
        uploaded_columns = set(dataframe.columns)
        missing_columns = (self.REQUIRED_COLUMNS - uploaded_columns)
        if missing_columns:
            logger.warning(f"Validating columns: {missing_columns}")
            raise MissingCSVColumns(list(missing_columns))

    async def save_equipment_data(self,dataframe:pd.DataFrame,
                                  dataset_uid: uuid.UUID,session: AsyncSession)-> None:
        equipments = []
        logger.info(f"Saving {len(dataframe)} equipment records")
        for _,row in dataframe.iterrows():
            equipment = Equipment(
            dataset_uid=dataset_uid,
            equipment_name=row["Equipment Name"],
            equipment_type=row["Type"],
            flowrate=float(row["Flowrate"]),
            pressure=float(row["Pressure"]),
            temperature=float(row["Temperature"])
            )  
            equipments.append(equipment)

        session.add_all(equipments)
        logger.info("Equipment records added to session")

    async def check_duplicate_dataset(self,
    owner_uid: uuid.UUID,filename: str,session: AsyncSession,):
        statement = select(Dataset).where(Dataset.owner_uid == owner_uid,
                                          Dataset.original_filename == filename,)

        result = await session.exec(statement)
        return result.first()
    
    async def create_dataset(self,file_info: UploadedFileInfo,owner_uid:uuid.UUID,session: AsyncSession)->Dataset:

        logger.info(f"Creating dataset record for file: {file_info.original_filename}")

        dataset = Dataset(original_filename = file_info.original_filename,
                          stored_filename=file_info.stored_filename,
                          file_path=file_info.file_path,
                          owner_uid=owner_uid,
                          status=Datasetstatus.PENDING,)

        try:
            session.add(dataset)
            await session.commit()
            await session.refresh(dataset)
            logger.info(f"Dataset created successfully. UID={dataset.uid}")
            return dataset

        except Exception:
            logger.exception("Failed to create dataaset record")
            await session.rollback()
            raise
    def update_dataset_summary(self,dataset: Dataset,summary : DatasetSummary,
                                     inactive_equipment: list,missing_data: list) -> None:
         logger.info(f"Updating dataset summary: {dataset.uid}")

         dataset.equipment_count = summary.equipment_count
         dataset.average_flowrate = summary.average_flowrate
         dataset.average_pressure = summary.average_pressure
         dataset.average_temperature = summary.average_temperature

         dataset.min_flowrate = summary.min_flowrate
         dataset.max_flowrate = summary.max_flowrate

         dataset.min_pressure = summary.min_pressure
         dataset.max_pressure = summary.max_pressure

         dataset.min_temperature = summary.min_temperature
         dataset.max_temperature = summary.max_temperature

         dataset.equipment_summary = summary.equipment_summary

         dataset.inactive_equipment = inactive_equipment
         dataset.missing_data = missing_data

         dataset.status = Datasetstatus.COMPLETED

         logger.info("Dataset summary updated successfully "
                     f"(Equipment Count={dataset.equipment_count})")
         
    async def process_dataset(self,dataset_uid:uuid.UUID,session: AsyncSession) ->None:
        logger.info(f"Started processing dataset: {dataset_uid}")
        dataset = await self.get_dataset(dataset_uid,session)
        try:
            # Mark dataset as processing
            dataset.status = Datasetstatus.PROCESSING
            await session.commit()
            logger.info("Reading CSV file")
            dataframe = self.read_csv_file(dataset.file_path)
            logger.info(f"CSV loaded successfully ({len(dataframe)} rows)")
            self.validate_csv_columns(dataframe)
            (valid_dataframe,inactive_equipment,missing_data) = self.validate_equipment_data(dataframe)
            summary = self.calculate_dataset_summary(valid_dataframe)
            logger.info("Dataset summary generated")

            

            self.update_dataset_summary(
                dataset=dataset,summary = summary,inactive_equipment=inactive_equipment,
                missing_data=missing_data)

            await self.save_equipment_data(dataframe=valid_dataframe,dataset_uid=dataset.uid,session=session)


            await session.commit()
            logger.info(f"Dataset processing completed successfully: {dataset.uid}")

        except Exception:
            logger.exception(f"Dataset processing failed: {dataset_uid}")

            try:
                await session.rollback()
            except Exception:
                pass
            raise
    async def process_dataset_in_background(self, dataset_uid: uuid.UUID) -> None:
        logger.info(f"Background dataset processing task starting for: {dataset_uid}")
        from src.db.main import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            try:
                await self.process_dataset(dataset_uid=dataset_uid, session=session)
                logger.info(f"Background dataset processing finished for: {dataset_uid}")
            except Exception as e:
                logger.error(f"Background dataset processing error for {dataset_uid}: {e}")

    async def upload_dataset(
        self,
        file: UploadFile,
        current_user: User,
        session: AsyncSession,
        background_tasks: BackgroundTasks | None = None,
    ) -> DatasetUploadResponse:
        logger.info(f"Dataset upload started: {file.filename}")
        self.validate_uploaded_file(file)
        logger.info("File validation completed")
        file_info = await self.save_uploaded_file(file)

        duplicate = await self.check_duplicate_dataset(
            owner_uid=current_user.uid,
            filename=file.filename,
            session=session,
        )
        if duplicate:
            raise DuplicateDatasetException(file.filename)

        dataset = await self.create_dataset(
            file_info=file_info,
            owner_uid=current_user.uid,
            session=session,
        )

        if background_tasks:
            background_tasks.add_task(self.process_dataset_in_background, dataset.uid)
        else:
            try:
                from src.celery_tasks import process_dataset
                process_dataset.delay(str(dataset.uid))
            except Exception:
                import asyncio
                asyncio.create_task(self.process_dataset_in_background(dataset.uid))

        logger.info("Background processing task created")
        return DatasetUploadResponse(
            uid=dataset.uid,
            original_filename=dataset.original_filename,
            message="Dataset uploaded successfully. Processing started.",
        )
    
    async def save_uploaded_file(self,file: UploadFile)->UploadedFileInfo:
        # storage/uploads if it doesn't exist
        logger.info(f"Saving uploaded file: {file.filename}")
        self.UPLOAD_DIR.mkdir(parents=True,exist_ok = True)

        #  original filename
        original_filename = file.filename

        # Extract file extension
        extension = Path(original_filename).suffix

        # Generate file extension
        stored_filename = f"{uuid.uuid4()}{extension}"

        # full path where file will be saved
        file_path = self.UPLOAD_DIR / stored_filename

        # save file
        with open(file_path,"wb") as buffer: 
            shutil.copyfileobj(file.file,buffer)
        logger.info(f"File stored at: {file_path}")
        return UploadedFileInfo(
            original_filename = original_filename,
            stored_filename = stored_filename,
            file_path = str(file_path)
        )
    async def page_info(self,owner_uid,page,page_size,session:AsyncSession):
        count_statement = (select(func.count()).select_from(Dataset).where(Dataset.owner_uid == owner_uid))
        count_result = await session.exec(count_statement)
        total_items = count_result.one()
        total_pages = math.ceil(total_items/page_size)
        has_next = page < total_pages
        has_previous = page > 1
        offset = (page-1) * page_size
        return total_items,total_pages,has_next,has_previous,offset
    
    async def get_all_datasets(self,session:AsyncSession,owner_uid:uuid.UUID,page,page_size):
        logger.info(f"Fetching datasets (page={page}, page_size={page_size})")
        (total_items,total_pages,has_next,has_previous,offset) = await self.page_info(owner_uid,page,page_size,session)
        statement = select(Dataset).where(Dataset.owner_uid == owner_uid).order_by(desc(Dataset.created_at)).offset(offset).limit(page_size)
        result = await session.exec(statement)
        datasets = result.all()
        logger.info(f"Returned {len(datasets)} datasets")
        return {
            "items":datasets,
            "pagination":{
                "page":page,
                "page_size":page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
            }
        }
    
    async def get_dataset(self,dataset_uid:uuid.UUID,session: AsyncSession):
        logger.info(f"Fetching dataset: {dataset_uid}")
        logger.info(f"Requested dataset_uid: {dataset_uid}")
        logger.info(f"Type: {type(dataset_uid)}")
        if type(dataset_uid) == str:
            dataset_uid = uuid.UUID(dataset_uid)
        statement = select(Dataset).where(Dataset.uid == dataset_uid)

        result = await session.exec(statement)

        dataset = result.first()
        if dataset:
            logger.info("Dataset found")
            return dataset
        else:
            logger.warning(f"Dataset not found: {dataset_uid}")
            return None 
    
    async def update_dataset(
        self, dataset_uid: uuid.UUID, update_data: DatasetUpdate, session: AsyncSession
    ):
        logger.info(f"Updating dataset: {dataset_uid}")
        dataset_to_update = await self.get_dataset(dataset_uid,session)

        if dataset_to_update is not None:
            update_data_dict = update_data.model_dump(exclude_unset=True)

            for k, v in update_data_dict.items():
                setattr(dataset_to_update,k ,v)
            dataset_to_update.updated_at = datetime.now()
            await session.commit()
            await session.refresh(dataset_to_update)
            logger.info("Dataset updated successfully")
            return dataset_to_update
        else:
            logger.warning(f"Dataset not found: {dataset_uid}")
            return None

    async def delete_dataset(self,dataset_uid:uuid.UUID, session:AsyncSession):
        logger.info(f"Deleting dataset: {dataset_uid}")
        dataset_to_delete = await self.get_dataset(dataset_uid,session)

        if dataset_to_delete is not None:
            await session.delete(dataset_to_delete)

            await session.commit()
            logger.info("Dataset deleted successfully")
            return {"dataset is successfully deleted!"}

        else:
            logger.warning(f"Dataset not found: {dataset_uid}")
            return None

    
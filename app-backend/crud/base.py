from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        带有默认创建、读取、更新和删除 (CRUD) 方法的基类。
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any, include_deleted: bool = False) -> Optional[ModelType]:
        query = select(self.model).where(self.model.id == id)
        
        # 如果模型包含 deleted_at 字段且没有显式要求包含删除记录，则过滤掉已软删除记录
        if hasattr(self.model, "deleted_at") and not include_deleted:
            deleted_at_col = getattr(self.model, "deleted_at")
            query = query.where(deleted_at_col.is_(None))
            
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[ModelType]:
        query = select(self.model)

        # 同样在多条查询中过滤已软删除的记录
        if hasattr(self.model, "deleted_at") and not include_deleted:
            deleted_at_col = getattr(self.model, "deleted_at")
            query = query.where(deleted_at_col.is_(None))

        # 默认按 id 升序，确保分页结果稳定（无 ORDER BY 时 MySQL InnoDB 不保证顺序）
        if hasattr(self.model, "id"):
            query = query.order_by(self.model.id.asc())

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())


    async def create(self, db: AsyncSession, *, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        if isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
                
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int, hard_delete: bool = False) -> Optional[ModelType]:
        """
        删除记录。如果模型支持并开启了软删除（且未指定 hard_delete），默认执行软删除。
        """
        obj = await self.get(db=db, id=id, include_deleted=True)
        if obj:
            if hasattr(obj, "soft_delete") and not hard_delete:
                getattr(obj, "soft_delete")()
                db.add(obj)
            else:
                await db.delete(obj)
            await db.commit()
        return obj


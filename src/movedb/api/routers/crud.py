from fastapi import APIRouter
from sqlmodel import SQLModel
from ..dependencies import SessionDep

# TODO: Maybe switch to FastCRUD: https://benavlabs.github.io/fastcrud/
class CrudRouter(APIRouter):
    def __init__(self, model: type[SQLModel], db: SessionDep, **kwargs):
        self.model = model
        self.db = db
        super().__init__(**kwargs)

    def create_item(self, item):
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def read_item(self, id: int):
        return self.db.get(self.model, id)
    
    def update_item(self, id: int, item):
        db_item = self.db.get(self.model, id)
        if not db_item:
            return None
        for key, value in item.dict().items():
            setattr(db_item, key, value)
        self.db.commit()
        self.db.refresh(db_item)
        return db_item

    def delete_item(self, id: int):
        item = self.db.get(self.model, id)
        if item:
            self.db.delete(item)
            self.db.commit()
        return item

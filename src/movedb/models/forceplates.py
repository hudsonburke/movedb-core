from movedb.models.trial import Trial
from .data_models import DataSource, HypertableData
from sqlmodel import Field, Column, JSON, Relationship
from ..utils.shaped_arrays import CalMatrixArray, CornersArray, OriginArray, Matrix3x3
from typing import Any
import numpy as np
import polars as pl
from functools import cached_property

class ForcePlateData(HypertableData["ForcePlate"], table=True):
    force_x: float
    force_y: float
    force_z: float
    moment_x: float
    moment_y: float
    moment_z: float
    cop_x: float
    cop_y: float
    cop_z: float
    freemoment_x: float
    freemoment_y: float
    freemoment_z: float

class ForcePlate(DataSource[ForcePlateData], table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: Trial | None = Relationship(back_populates = "forceplates")
    
    unit_force: str = "N"
    unit_moment: str = "Nm"
    unit_position: str = "m"

    _cal_matrix: dict = Field(sa_column=Column(JSON), alias="cal_matrix")
    _corners: dict = Field(sa_column=Column(JSON), alias="corners")
    _origin: dict = Field(sa_column=Column(JSON), alias="origin")

    @property
    def _data_model(self) -> type[ForcePlateData]:
        return ForcePlateData

    @property
    def cal_matrix(self) -> CalMatrixArray:
        return np.array(self._cal_matrix.get('data', []))

    @cal_matrix.setter
    def cal_matrix(self, v: CalMatrixArray):
        self._cal_matrix = {"data": v.tolist()}

    @property
    def corners(self) -> CornersArray:
        return np.array(self._corners.get('data', []))

    @corners.setter
    def corners(self, v: CornersArray): 
        self._corners = {"data": v.tolist()}

    @property
    def origin(self) -> OriginArray:
        return np.array(self._origin.get('data', []))
    
    @origin.setter
    def origin(self, v: OriginArray): 
        self._origin = {"data": v.tolist()}

    @cached_property
    def _data_records(self) -> list[dict]:
        """Implementation of the abstract method from DataSource."""
        return [
            {
                "timestamp": d.timestamp,
                "force_x": d.force_x, "force_y": d.force_y, "force_z": d.force_z,
                "moment_x": d.moment_x, "moment_y": d.moment_y, "moment_z": d.moment_z,
                "cop_x": d.cop_x, "cop_y": d.cop_y, "cop_z": d.cop_z,
                "freemoment_x": d.freemoment_x, "freemoment_y": d.freemoment_y, "freemoment_z": d.freemoment_z
            }
            for d in self._data
        ]
    
    # TODO: Do this without polars
    @property
    def timestamp(self) -> np.ndarray:
        return self.to_polars.select("timestamp").to_numpy()

    @property
    def force(self) -> np.ndarray:
        return self.to_polars.select(["force_x", "force_y", "force_z"]).to_numpy()

    @property
    def moment(self) -> np.ndarray:
        return self.to_polars.select(["moment_x", "moment_y", "moment_z"]).to_numpy()
    
    @property
    def cop(self) -> np.ndarray:
        return self.to_polars.select(["cop_x", "cop_y", "cop_z"]).to_numpy()
    
    @property
    def freemoment(self) -> np.ndarray:
        return self.to_polars.select(["freemoment_x", "freemoment_y", "freemoment_z"]).to_numpy()

    def rotate(self, rotation: Matrix3x3) -> "ForcePlate":
        # Apply rotation to corners and origin 
        rotated_corners = rotation @ self.corners
        rotated_origin = rotation @ self.origin

        rotated_force = (rotation @ self.force.T).T
        rotated_moment = (rotation @ self.moment.T).T
        rotated_cop = (rotation @ self.cop.T).T
        rotated_freemoment = (rotation @ self.freemoment.T).T

        data_dict = {
            "timestamp": self.timestamp,
            "force_x": rotated_force[:, 0],
            "force_y": rotated_force[:, 1],
            "force_z": rotated_force[:, 2],
            "moment_x": rotated_moment[:, 0],
            "moment_y": rotated_moment[:, 1],
            "moment_z": rotated_moment[:, 2],
            "cop_x": rotated_cop[:, 0],
            "cop_y": rotated_cop[:, 1],
            "cop_z": rotated_cop[:, 2],
            "freemoment_x": rotated_freemoment[:, 0],
            "freemoment_y": rotated_freemoment[:, 1],
            "freemoment_z": rotated_freemoment[:, 2]
        }
        rotated_fp = self.model_copy(deep=True)
        rotated_fp.corners = rotated_corners
        rotated_fp.origin = rotated_origin
        rotated_fp.set_data(pl.DataFrame(data_dict))

        return rotated_fp

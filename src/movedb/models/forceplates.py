from .data_models import TimeSeriesData, DataSource
from sqlmodel import Field, Column, JSON, Relationship
from sqlalchemy import Interval
from ..utils.shaped_arrays import CalMatrixArray, CornersArray, OriginArray, Matrix3x3
from typing import TYPE_CHECKING, Type
from datetime import timedelta
import numpy as np
import polars as pl

if TYPE_CHECKING:
    from .trial import Trial

class ForcePlateData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for force plate data."""
    
    # Time series fields
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    
    # Database fields
    parent_id: int = Field(foreign_key="datasource.id", primary_key=True)
    parent: "ForcePlate" = Relationship(back_populates="data")
    
    # Data fields
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

class ForcePlate(DataSource, table=True):
    __mapper_args__ = {"polymorphic_identity": "forceplate"}
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates = "forceplates")
    
    unit_force: str = "N"
    unit_moment: str = "Nm"
    unit_position: str = "m"
    
    # Relationship to time series data
    data: list[ForcePlateData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[ForcePlateData]:
        return ForcePlateData

    cal_matrix_data: dict = Field(sa_column=Column(JSON))
    corners_data: dict = Field(sa_column=Column(JSON))
    origin_data: dict = Field(sa_column=Column(JSON))

    @property
    def cal_matrix(self) -> CalMatrixArray:
        return np.array(self.cal_matrix_data.get('data', []))

    @cal_matrix.setter
    def cal_matrix(self, v: CalMatrixArray):
        self.cal_matrix_data = {"data": v.tolist()}

    @property
    def corners(self) -> CornersArray:
        return np.array(self.corners_data.get('data', []))

    @corners.setter
    def corners(self, v: CornersArray): 
        self.corners_data = {"data": v.tolist()}

    @property
    def origin(self) -> OriginArray:
        return np.array(self.origin_data.get('data', []))
    
    @origin.setter
    def origin(self, v: OriginArray): 
        self.origin_data = {"data": v.tolist()}

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

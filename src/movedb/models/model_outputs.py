from .data_models import TimeSeriesData, DataSource

class AngleData(TimeSeriesData["Angle"], table=True):
    angle: float

class Angle(DataSource[AngleData]):
    units: str = "degrees"


class MomentData(TimeSeriesData["Moment"], table=True):
    moment: float

class Moment(DataSource[MomentData]):
    units: str = "Nm"
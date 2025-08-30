from .data_models import HypertableData, DataSource

class AngleData(HypertableData["Angle"], table=True):
    angle: float

class Angle(DataSource[AngleData]):
    units: str = "degrees"


class MomentData(HypertableData["Moment"], table=True):
    moment: float

class Moment(DataSource[MomentData]):
    units: str = "Nm"
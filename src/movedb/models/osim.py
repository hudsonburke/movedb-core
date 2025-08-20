from sqlmodel import SQLModel, Field, Relationship
from .files import File

class OpenSimModel(File, table=True):
    analyses: Relationship()
    # Do I want to try and put this in to SQL? 
    # Could use the OsimGraph structure

class OpenSimAnalysis(SQLModel):
    model: Relationship()

class OpenSimIKSetup(OpenSimAnalysis, table=True):
    time_range: tuple[float, float]
    marker_data: Relationship()
    results: Relationship() 
    
class OpenSimIDSetup(OpenSimAnalysis, table=True):
    results: Relationship()
    forces_to_exclude: list[str]
    external_loads: Relationship()
    coordinates: Relationship(IK)
    lowpass_freq: float = -1

#class OpenSimCMC(OpenSimAnalysis, table=True):
#class OpenSimSO(OpenSimAnalysis, table=True):
#class OpenSimFD(OpenSimAnalysis, table=True):
#class OpenSimRRA(OpenSimAnalysis, table=True):


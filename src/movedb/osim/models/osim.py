from sqlmodel import SQLModel, Field, Relationship
# TODO
class OpenSimModel(File, table=True):
    analyses: list["OpenSimAnalysis"] = Relationship(back_populates="model")
    
class OpenSimAnalysis(SQLModel):
    model_id: int | None = Field(default=None, foreign_key="model.id")
    model: OpenSimModel = Relationship(back_populates="analyses")

    results: list["OpenSimResults"] = Relationship(back_populates="analysis")

class OpenSimResults(File):
    analysis_id: int | None = Field(default=None, foreign_key="analysis.id")
    analysis: OpenSimAnalysis = Relationship(back_populates="results")

class OpenSimIKResults(OpenSimResults, table=True):
    angles: list[DataSource] = Relationship(back_populates="ik_results")

class OpenSimIKSetup(OpenSimAnalysis, table=True):
    time_range: tuple[float, float]
    # marker_data: Relationship()
    
class OpenSimIDSetup(OpenSimAnalysis, table=True):
    forces_to_exclude: list[str]
    # external_loads: Relationship()
    # coordinates: Relationship(IK)
    lowpass_freq: float = -1

#class OpenSimCMC(OpenSimAnalysis, table=True):
#class OpenSimSO(OpenSimAnalysis, table=True):
#class OpenSimFD(OpenSimAnalysis, table=True):
#class OpenSimRRA(OpenSimAnalysis, table=True):


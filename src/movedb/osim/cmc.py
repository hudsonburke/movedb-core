from pyopensim.tools import CMCTool
from pydantic import Field
from typing import Literal
from .abstract_tool import AbstractToolSettings


class CMCSettings(AbstractToolSettings):
    """CMC (Computed Muscle Control) settings.

    Descriptions are available in Field(...) metadata for runtime/schema usage.
    """
    solve_for_equilibrium_for_auxiliary_states: bool = Field(
        True,
        description=(
            "Flag indicating whether or not to compute equilibrium values for "
            "states other than the coordinates or speeds. For example, equilibrium "
            "muscle fiber lengths or muscle forces."
        ),
    )
    maximum_number_of_integrator_steps: int = Field(
        10000, description="Maximum number of integrator steps."
    )
    maximum_integrator_step_size: float = Field(
        1.0, description="Maximum integration step size."
    )
    minimum_integrator_step_size: float = Field(
        0.0, description="Minimum integration step size."
    )
    integrator_error_tolerance: float = Field(
        1e-6,
        description=(
            "Integrator error tolerance. When the error is greater, the integrator "
            "step size is decreased."
        ),
    )
    desired_points_file: str = Field(
        "",
        description=(
            "Motion (.mot) or storage (.sto) file containing the desired point "
            "trajectories."
        ),
    )
    desired_kinematics_file: str = Field(
        "",
        description=(
            "Motion (.mot) or storage (.sto) file containing the desired kinematic "
            "trajectories."
        ),
    )
    task_set_file: str = Field(
        "",
        description=(
            "File containing the tracking tasks. Which coordinates are tracked and "
            "with what weights are specified here."
        ),
    )
    constraints_file: str = Field(
        "",
        description="File containing the constraints on the controls.",
    )
    rra_controls_file: str = Field(
        "",
        description=(
            "File containing the controls output by RRA. These can be used to place "
            "constraints on the residuals during CMC."
        ),
    )
    lowpass_cutoff_frequency: float = Field(
        -1.0,
        description=(
            "Low-pass cut-off frequency for filtering the desired kinematics. A "
            "negative value results in no filtering. The default value is -1.0, so "
            "no filtering."
        ),
    )
    cmc_time_window: float = Field(
        0.01,
        description=(
            "Time window over which the desired actuator forces are achieved. "
            "Muscles forces cannot change instantaneously, so a finite time window "
            "must be allowed. The recommended time window for RRA is about 0.001 "
            "sec, and for CMC is about 0.010 sec."
        ),
    )
    use_curvature_filter: bool = Field(
        False,
        description=(
            "Flag (true or false) indicating whether or not to use the curvature "
            "filter. Setting this flag to true can reduce oscillations in the "
            "computed muscle excitations."
        ),
    )
    use_fast_optimization_target: bool = Field(
        True,
        description=(
            "Flag (true or false) indicating whether to use the fast CMC "
            "optimization target. The fast target requires the desired "
            "accelerations to be met. The optimizer fails if the accelerations "
            "constraints cannot be met, so the fast target can be less robust. The "
            "regular target does not require the acceleration constraints to be "
            "met; it meets them as well as it can, but it is slower and less "
            "accurate."
        ),
    )
    optimizer_algorithm: Literal["ipopt", "cfsqp"] = Field(
        "ipopt",
        description=(
            "Preferred optimizer algorithm (currently support \"ipopt\" or \"cfsqp\","
            " the latter requiring the osimFSQP library.)"
        ),
    )
    optimizer_derivative_dx: float = Field(
        1e-6,
        description=(
            "Perturbation size used by the optimizer to compute numerical "
            "derivatives. A value between 1.0e-4 and 1.0e-8 is usually appropriate."
        ),
    )
    optimizer_convergence_criterion: float = Field(
        1e-4,
        description=(
            "Convergence criterion for the optimizer. The smaller this value, the "
            "deeper the convergence. Decreasing this number can improve a solution, "
            "but will also likely increase computation time."
        ),
    )
    optimizer_max_iterations: int = Field(
        500, description="Maximum number of iterations for the optimizer."
    )
    optimizer_print_level: int = Field(
        0,
        description=(
            "Print level for the optimizer, 0 - 3. 0=no printing, 3=detailed "
            "printing, 2=in between"
        ),
    )
    use_verbose_printing: bool = Field(
        False,
        description=(
            "True-false flag indicating whether or not to turn on verbose printing "
            "for cmc."
        ),
    )
    actuators_to_exclude: list[str] = Field(
        default_factory=list,
        description=(
            "List of individual Actuators by individual or user-defined group name to be "
            "excluded from CMC's control."
        ),
    )
    
    def _create_tool_instance(self) -> CMCTool:
        """Create a CMCTool instance."""
        return CMCTool()
    
    def _configure_tool_specific_settings(self, tool: CMCTool) -> None:
        """Configure CMC-specific settings.
        
        Parameters
        ----------
        tool : CMCTool
            The CMC tool instance to configure.
        """
        tool.setDesiredPointsFileName(self.desired_points_file)
        tool.setDesiredKinematicsFileName(self.desired_kinematics_file)
        tool.setTaskSetFileName(self.task_set_file)
        tool.setConstraintsFileName(self.constraints_file)
        tool.setRRAControlsFileName(self.rra_controls_file)
        tool.setLowpassCutoffFrequency(self.lowpass_cutoff_frequency)
        tool.setUseFastTarget(self.use_fast_optimization_target)
        
        # Set actuators to exclude
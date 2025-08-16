import spm1d
import numpy as np
import matplotlib.pyplot as plt

def plot_significant_clusters(
    ax: plt.Axes,
    data1: np.ndarray,
    data2: np.ndarray,
    x: np.ndarray | None = None,
    alpha: float = 0.05,
    paired: bool = True,
    two_tailed: bool = True,
    interpolation: bool = True,
    color: tuple[float, float, float] | str = (1, 0, 0)
) -> tuple[plt.Axes, spm1d.stats._spm.SPMi_T]:
    """
    Plot SPM analysis results on a matplotlib axes.
    https://spm1d.org/doc/Stats1D/onetwosample.html#paired-t-test
    
    Args:
        ax: Matplotlib axes to plot on
        data1: First dataset
        data2: Second dataset
        x: x-values for plotting ; especially useful for time series data (default: None)
        alpha: Significance level (default: 0.05)
        paired: Whether to use paired t-test (default: True)
        two_tailed: Whether to use two-tailed test (default: True)
        interpolation: Interpolate clusters to the critical threshold (default: True)
        color: Color for significance patches (default: red)
        
    Returns:
        matplotlib.pyplot.Axes: The modified axes object
    """

    # Squeeze data
    squeezed_data1 = np.squeeze(data1)
    squeezed_data2 = np.squeeze(data2) 
    
    # Generate x values if not provided
    if x is None:
        print(f"No x value provided. Generating x values from 0 to {squeezed_data1.shape[1]}")
        x = np.arange(squeezed_data1.shape[1])
    
    # Find indices of zero variance nodes
    zero_var = (np.std(squeezed_data1, axis=0) < np.finfo(float).eps) | \
               (np.std(squeezed_data2, axis=0) < np.finfo(float).eps)
    
    if np.any(zero_var):
        print(f"Warning: Zero variance nodes detected at {np.where(zero_var)[0]}. "
              f"Removing them from analysis.")
        squeezed_data1[:, zero_var] = np.nan
        squeezed_data2[:, zero_var] = np.nan
    
    # Conduct SPM analysis without zero variance nodes
    if paired:
        t = spm1d.stats.ttest_paired(squeezed_data1, squeezed_data2)
    else:
        t = spm1d.stats.ttest2(squeezed_data1, squeezed_data2)
    
    # Perform inference
    inference = t.inference(alpha, two_tailed=two_tailed, interp=interpolation)

    # Get axis limits
    y1, y2 = ax.get_ylim()
    
    # Plot significance patches
    for cluster in inference.clusters:
        # Map indices to x-values
        x1 = x[int(cluster.endpoints[0])]
        x2 = x[int(cluster.endpoints[1])]        
        print(f"Significant cluster: {x1} to {x2}")
        ax.fill_between(
            [x1, x2],
            y1,
            y2,
            color=color,
            alpha=0.3,
            edgecolor='none',
            zorder=0  # Place behind other plotted elements
        )
    
    return ax, inference

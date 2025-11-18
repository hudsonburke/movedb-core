"""Tests for OpenSim export with HDF5 storage."""
import pytest
import numpy as np
from pathlib import Path
from datetime import datetime
from movedb.models import Trial
from movedb.storage import HDF5TrialStorage, StorageConfig, set_storage_config


class TestOpenSimExportFromHDF5:
    """Test OpenSim export functions with HDF5-backed trials."""
    
    @pytest.fixture
    def trial_with_hdf5(self, tmp_path):
        """Create a trial with HDF5 data."""
        # Set storage config
        config = StorageConfig(hdf5_base_dir=tmp_path / "hdf5")
        set_storage_config(config)
        
        # Create trial
        trial = Trial(
            id=1,
            name="test_trial",
            timestamp=datetime.now(),
            marker_names=["LASI", "RASI", "SACR"],
            analog_names=["EMG1", "EMG2"],
            forceplate_names=["FP1"],
            marker_rate=100.0,
            analog_rate=1000.0,
            forceplate_rate=1000.0,
            n_frames=100,
            first_frame=0,
            last_frame=99
        )
        
        # Generate HDF5 path
        hdf5_dir = tmp_path / "hdf5" / "trials_000000"
        hdf5_dir.mkdir(parents=True, exist_ok=True)
        hdf5_path = hdf5_dir / "trial_000001.h5"
        trial.hdf5_path = str(hdf5_path)
        
        # Write test data to HDF5
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            # Markers: (n_frames, n_markers, 3)
            marker_data = np.random.randn(100, 3, 3) * 100  # 100 frames, 3 markers, xyz
            storage.write_markers(
                data=marker_data,
                marker_names=trial.marker_names,
                rate=100.0,
                units="mm",
                first_frame=0
            )
            
            # Analogs: (n_frames, n_channels)
            analog_data = np.random.randn(100, 2) * 5  # 100 frames, 2 channels
            storage.write_analogs(
                data=analog_data,
                channel_names=trial.analog_names,
                rate=1000.0,
                units="V",
                first_frame=0
            )
            
            # Force plate: forces, moments, cop
            forces = np.random.randn(100, 3) * 500  # N
            moments = np.random.randn(100, 3) * 50  # Nm
            cop = np.random.randn(100, 3) * 0.1  # m
            
            storage.write_forceplate(
                name="FP1",
                forces=forces,
                moments=moments,
                cop=cop,
                rate=1000.0,
                cal_matrix=np.eye(6),
                corners=np.zeros((4, 3)),
                origin=np.zeros(3),
                unit_force="N",
                unit_moment="Nm",
                unit_position="m"
            )
        
        return trial
    
    def test_export_trial_to_trc(self, trial_with_hdf5, tmp_path):
        """Test exporting trial to TRC format."""
        from movedb.osim import export_trial_to_trc
        
        output_file = tmp_path / "markers.trc"
        
        # Export to TRC
        export_trial_to_trc(
            trial=trial_with_hdf5,
            filepath=str(output_file)
        )
        
        # Verify file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        
        # Verify file can be read
        with open(output_file, 'r') as f:
            content = f.read()
            # Check for marker names in header
            assert "LASI" in content
            assert "RASI" in content
            assert "SACR" in content
    
    def test_export_trial_to_trc_with_units_conversion(self, trial_with_hdf5, tmp_path):
        """Test TRC export with units conversion."""
        from movedb.osim import export_trial_to_trc
        
        output_file = tmp_path / "markers_m.trc"
        
        # Export with conversion from mm to m
        export_trial_to_trc(
            trial=trial_with_hdf5,
            filepath=str(output_file),
            output_units="m"
        )
        
        assert output_file.exists()
    
    def test_export_trial_forceplates_to_mot(self, trial_with_hdf5, tmp_path):
        """Test exporting force plates to MOT format."""
        from movedb.osim import export_trial_forceplates_to_mot
        
        output_file = tmp_path / "forces.mot"
        
        # Export to MOT
        export_trial_forceplates_to_mot(
            trial=trial_with_hdf5,
            filepath=str(output_file)
        )
        
        # Verify file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        
        # Verify file structure
        with open(output_file, 'r') as f:
            content = f.read()
            # Check for force plate data columns
            assert "FP1" in content
            assert "force" in content.lower()
    
    def test_export_without_hdf5_path_fails(self, tmp_path):
        """Test that export fails gracefully without HDF5 path."""
        from movedb.osim import export_trial_to_trc
        
        trial = Trial(name="no_hdf5_trial")
        output_file = tmp_path / "should_fail.trc"
        
        with pytest.raises(ValueError, match="no HDF5 data path"):
            export_trial_to_trc(trial=trial, filepath=str(output_file))
    
    def test_export_forceplates_without_data_fails(self, tmp_path):
        """Test that force plate export fails without force plates."""
        from movedb.osim import export_trial_forceplates_to_mot
        
        # Create trial with HDF5 but no force plates
        trial = Trial(
            id=2,
            name="no_fp_trial",
            hdf5_path=str(tmp_path / "dummy.h5"),
            forceplate_names=[]
        )
        output_file = tmp_path / "should_fail.mot"
        
        with pytest.raises(ValueError, match="no force plates"):
            export_trial_forceplates_to_mot(trial=trial, filepath=str(output_file))

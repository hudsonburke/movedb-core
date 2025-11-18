"""Tests for HDF5 storage layer."""
import pytest
import numpy as np
from pathlib import Path
from datetime import timedelta

from movedb.storage.hdf5_storage import HDF5TrialStorage, get_trial_hdf5_path
from movedb.storage.config import StorageConfig


class TestHDF5TrialStorage:
    """Test HDF5 storage operations."""
    
    def test_marker_write_and_read(self, tmp_path):
        """Test writing and reading marker data."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Create test data
        n_frames, n_markers = 100, 5
        data = np.random.randn(n_frames, n_markers, 3).astype('float32')
        marker_names = [f"Marker_{i}" for i in range(n_markers)]
        residuals = np.random.rand(n_frames, n_markers).astype('float32')
        
        # Write
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_markers(
                data=data,
                marker_names=marker_names,
                rate=100.0,
                units="mm",
                first_frame=0,
                residuals=residuals
            )
        
        # Read
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            result = storage.read_markers()
        
        # Verify
        assert np.allclose(result['data'], data)
        assert result['marker_names'] == marker_names
        assert result['rate'] == 100.0
        assert result['units'] == "mm"
        assert result['first_frame'] == 0
        assert np.allclose(result['residuals'], residuals)
    
    def test_get_marker_by_name(self, tmp_path):
        """Test getting individual marker data."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Create test data
        data = np.random.randn(100, 3, 3).astype('float32')
        marker_names = ["LASI", "RASI", "SACR"]
        
        # Write
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_markers(
                data=data,
                marker_names=marker_names,
                rate=100.0,
                units="mm"
            )
        
        # Read specific marker
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            lasi = storage.get_marker_by_name("LASI")
            nonexistent = storage.get_marker_by_name("NONEXISTENT")
        
        # Verify
        assert lasi is not None
        assert lasi.shape == (100, 3)
        assert np.allclose(lasi, data[:, 0, :])
        assert nonexistent is None
    
    def test_analog_write_and_read(self, tmp_path):
        """Test writing and reading analog data."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Create test data
        n_frames, n_channels = 1000, 8
        data = np.random.randn(n_frames, n_channels).astype('float32')
        channel_names = [f"Channel_{i}" for i in range(n_channels)]
        
        # Write
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_analogs(
                data=data,
                channel_names=channel_names,
                rate=1000.0,
                units="V",
                first_frame=0
            )
        
        # Read
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            result = storage.read_analogs()
        
        # Verify
        assert np.allclose(result['data'], data)
        assert result['channel_names'] == channel_names
        assert result['rate'] == 1000.0
        assert result['units'] == "V"
    
    def test_forceplate_write_and_read(self, tmp_path):
        """Test writing and reading force plate data."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Create test data
        n_frames = 1000
        forces = np.random.randn(n_frames, 3).astype('float32')
        moments = np.random.randn(n_frames, 3).astype('float32')
        cop = np.random.randn(n_frames, 3).astype('float32')
        cal_matrix = np.eye(6).astype('float32')
        corners = np.random.randn(4, 3).astype('float32')
        origin = np.array([0.0, 0.0, 0.0]).astype('float32')
        
        # Write
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_forceplate(
                name="FP1",
                forces=forces,
                moments=moments,
                cop=cop,
                rate=1000.0,
                cal_matrix=cal_matrix,
                corners=corners,
                origin=origin,
                unit_force="N",
                unit_moment="Nm",
                unit_position="m"
            )
        
        # Read
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            result = storage.read_forceplate("FP1")
            fp_list = storage.list_forceplates()
        
        # Verify
        assert np.allclose(result['forces'], forces)
        assert np.allclose(result['moments'], moments)
        assert np.allclose(result['cop'], cop)
        assert np.allclose(result['cal_matrix'], cal_matrix)
        assert np.allclose(result['corners'], corners)
        assert np.allclose(result['origin'], origin)
        assert result['rate'] == 1000.0
        assert result['unit_force'] == "N"
        assert fp_list == ["FP1"]
    
    def test_multiple_forceplates(self, tmp_path):
        """Test writing and listing multiple force plates."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        n_frames = 100
        
        # Write multiple force plates
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            for i in range(3):
                storage.write_forceplate(
                    name=f"FP{i+1}",
                    forces=np.random.randn(n_frames, 3).astype('float32'),
                    moments=np.random.randn(n_frames, 3).astype('float32'),
                    cop=np.random.randn(n_frames, 3).astype('float32'),
                    rate=1000.0,
                    cal_matrix=np.eye(6).astype('float32'),
                    corners=np.zeros((4, 3)).astype('float32'),
                    origin=np.zeros(3).astype('float32')
                )
        
        # List force plates
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            fp_list = storage.list_forceplates()
        
        assert len(fp_list) == 3
        assert "FP1" in fp_list
        assert "FP2" in fp_list
        assert "FP3" in fp_list
    
    def test_events_write_and_read(self, tmp_path):
        """Test writing and reading events."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Create test events
        events = [
            {
                'context': 'Left',
                'label': 'Foot Strike',
                'time': timedelta(seconds=1.5),
                'description': 'Left foot initial contact'
            },
            {
                'context': 'Right',
                'label': 'Foot Off',
                'time': timedelta(seconds=2.3),
                'description': 'Right foot toe off'
            }
        ]
        
        # Write
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_events(events)
        
        # Read
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            result = storage.read_events()
        
        # Verify
        assert len(result) == 2
        assert result[0]['context'] == 'Left'
        assert result[0]['label'] == 'Foot Strike'
        assert result[0]['time'] == timedelta(seconds=1.5)
        assert result[1]['context'] == 'Right'
    
    def test_empty_events(self, tmp_path):
        """Test reading when no events are stored."""
        hdf5_path = tmp_path / "test_trial.h5"
        
        # Write markers only (no events)
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
            storage.write_markers(
                data=np.random.randn(10, 3, 3).astype('float32'),
                marker_names=["M1", "M2", "M3"],
                rate=100.0,
                units="mm"
            )
        
        # Try to read events
        with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
            result = storage.read_events()
        
        assert result == []


class TestGetTrialHDF5Path:
    """Test HDF5 path generation."""
    
    def test_path_generation(self, tmp_path):
        """Test that paths are generated correctly."""
        path_1 = get_trial_hdf5_path(1, tmp_path)
        path_500 = get_trial_hdf5_path(500, tmp_path)
        path_1000 = get_trial_hdf5_path(1000, tmp_path)
        path_1500 = get_trial_hdf5_path(1500, tmp_path)
        
        # Check folder grouping
        assert path_1.parent.name == "trials_000000"
        assert path_500.parent.name == "trials_000000"
        assert path_1000.parent.name == "trials_001000"
        assert path_1500.parent.name == "trials_001000"
        
        # Check filenames
        assert path_1.name == "trial_000001.h5"
        assert path_500.name == "trial_000500.h5"
        assert path_1000.name == "trial_001000.h5"
    
    def test_directory_creation(self, tmp_path):
        """Test that directories are created automatically."""
        path = get_trial_hdf5_path(12345, tmp_path)
        
        assert path.parent.exists()
        assert path.parent.is_dir()


class TestStorageConfig:
    """Test storage configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        from movedb.storage.config import StorageConfig
        
        config = StorageConfig()
        
        assert config.hdf5_base_dir == Path("./data/hdf5_storage")
        assert config.database_url == "sqlite:///./data/movedb.db"
        assert config.compression == "gzip"
        assert config.compression_opts == 4
    
    def test_custom_config(self, tmp_path):
        """Test custom configuration."""
        from movedb.storage.config import StorageConfig, set_storage_config, get_storage_config
        
        custom_config = StorageConfig(
            hdf5_base_dir=tmp_path / "custom_hdf5",
            database_url="postgresql://localhost/test",
            compression="lzf"
        )
        
        set_storage_config(custom_config)
        retrieved = get_storage_config()
        
        assert retrieved.hdf5_base_dir == tmp_path / "custom_hdf5"
        assert retrieved.database_url == "postgresql://localhost/test"
        assert retrieved.compression == "lzf"

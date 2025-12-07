"""Tests for refactored Trial model with HDF5 storage."""
import pytest
import numpy as np
import json
from pathlib import Path
from datetime import timedelta, datetime

from movedb.models import Trial, Event
from movedb.storage import HDF5TrialStorage, get_trial_hdf5_path, StorageConfig, set_storage_config


class TestTrialModel:
    """Test the refactored Trial model."""
    
    def test_trial_creation(self):
        """Test creating a basic trial."""
        trial = Trial(
            name="test_trial",
            timestamp=datetime.now(),
            marker_names=["LASI", "RASI", "SACR"],
            analog_names=["EMG1", "EMG2"],
            forceplate_names=["FP1", "FP2"],
            marker_rate=100.0,
            analog_rate=1000.0,
            n_frames=1000,
            first_frame=0,
            last_frame=999
        )
        
        assert trial.name == "test_trial"
        assert len(trial.marker_names) == 3
        assert trial.marker_rate == 100.0
        assert trial.n_frames == 1000
    
    def test_trial_with_events(self):
        """Test trial with events."""
        trial = Trial(name="test_trial")
        
        event1 = Event(
            trial=trial,
            context="Left",
            label="Foot Strike",
            time=timedelta(seconds=1.5)
        )
        event2 = Event(
            trial=trial,
            context="Right",
            label="Foot Off",
            time=timedelta(seconds=2.3)
        )
        
        trial.events = [event1, event2]
        
        assert len(trial.events) == 2
        assert trial.events[0].label == "Foot Strike"
    
    def test_get_events_filtered(self):
        """Test filtering events."""
        trial = Trial(name="test_trial")
        
        trial.events = [
            Event(trial=trial, context="Left", label="Foot Strike", time=timedelta(seconds=1.0)),
            Event(trial=trial, context="Right", label="Foot Strike", time=timedelta(seconds=1.5)),
            Event(trial=trial, context="Left", label="Foot Off", time=timedelta(seconds=2.0)),
            Event(trial=trial, context="Right", label="Foot Off", time=timedelta(seconds=2.5)),
        ]
        
        left_events = trial.get_events(context="Left")
        assert len(left_events) == 2
        assert all(e.context == "Left" for e in left_events)
        
        foot_strikes = trial.get_events(label="Foot Strike")
        assert len(foot_strikes) == 2
        assert all(e.label == "Foot Strike" for e in foot_strikes)
        
        left_strikes = trial.get_events(context="Left", label="Foot Strike")
        assert len(left_strikes) == 1
        assert left_strikes[0].context == "Left"
        assert left_strikes[0].label == "Foot Strike"
    
    def test_hdf5_path_generation(self, tmp_path):
        """Test HDF5 path is generated correctly."""
        # Set custom storage config
        config = StorageConfig(hdf5_base_dir=tmp_path / "hdf5")
        set_storage_config(config)
        
        trial = Trial(id=1, name="test_trial")
        
        # Path should be generated automatically
        assert trial.hdf5_path is not None
        assert "trial_000001.h5" in trial.hdf5_path
    
    def test_load_markers_with_hdf5(self, tmp_path):
        """Test loading marker data from HDF5."""
        # Setup storage
        config = StorageConfig(hdf5_base_dir=tmp_path / "hdf5")
        set_storage_config(config)
        
        trial = Trial(id=1, name="test_trial")
        trial.hdf5_path = str(tmp_path / "test_trial.h5")
        
        # Write some marker data
        marker_data = np.random.randn(100, 3, 3).astype('float32')
        marker_names = ["LASI", "RASI", "SACR"]
        
        with HDF5TrialStorage(trial.hdf5_path, trial.id, mode='w') as storage:
            storage.write_markers(
                data=marker_data,
                marker_names=marker_names,
                rate=100.0,
                units="mm"
            )
        
        # Update trial metadata
        trial.marker_names = marker_names
        trial.marker_rate = 100.0
        trial.n_frames = 100
        
        # Load markers
        result = trial.load_markers()
        
        assert np.allclose(result['data'], marker_data)
        assert result['marker_names'] == marker_names
        assert result['rate'] == 100.0
    
    def test_get_marker_by_name(self, tmp_path):
        """Test getting a specific marker."""
        trial = Trial(id=1, name="test_trial")
        trial.hdf5_path = str(tmp_path / "test_trial.h5")
        
        # Write marker data
        marker_data = np.random.randn(100, 3, 3).astype('float32')
        marker_names = ["LASI", "RASI", "SACR"]
        
        with HDF5TrialStorage(trial.hdf5_path, trial.id, mode='w') as storage:
            storage.write_markers(
                data=marker_data,
                marker_names=marker_names,
                rate=100.0,
                units="mm"
            )
        
        # Get specific marker
        lasi = trial.get_marker("LASI")
        
        assert lasi is not None
        assert lasi.shape == (100, 3)
        assert np.allclose(lasi, marker_data[:, 0, :])
    
    def test_load_analogs(self, tmp_path):
        """Test loading analog data."""
        trial = Trial(id=1, name="test_trial")
        trial.hdf5_path = str(tmp_path / "test_trial.h5")
        
        # Write analog data
        analog_data = np.random.randn(1000, 8).astype('float32')
        channel_names = [f"EMG{i}" for i in range(8)]
        
        with HDF5TrialStorage(trial.hdf5_path, trial.id, mode='w') as storage:
            storage.write_analogs(
                data=analog_data,
                channel_names=channel_names,
                rate=1000.0,
                units="V"
            )
        
        # Load analogs
        result = trial.load_analogs()
        
        assert np.allclose(result['data'], analog_data)
        assert result['channel_names'] == channel_names
    
    def test_load_forceplates(self, tmp_path):
        """Test loading force plate data."""
        trial = Trial(id=1, name="test_trial")
        trial.hdf5_path = str(tmp_path / "test_trial.h5")
        
        # Write force plate data
        n_frames = 1000
        with HDF5TrialStorage(trial.hdf5_path, trial.id, mode='w') as storage:
            storage.write_forceplate(
                name="FP1",
                forces=np.random.randn(n_frames, 3).astype('float32'),
                moments=np.random.randn(n_frames, 3).astype('float32'),
                cop=np.random.randn(n_frames, 3).astype('float32'),
                rate=1000.0,
                cal_matrix=np.eye(6).astype('float32'),
                corners=np.zeros((4, 3)).astype('float32'),
                origin=np.zeros(3).astype('float32')
            )
            storage.write_forceplate(
                name="FP2",
                forces=np.random.randn(n_frames, 3).astype('float32'),
                moments=np.random.randn(n_frames, 3).astype('float32'),
                cop=np.random.randn(n_frames, 3).astype('float32'),
                rate=1000.0,
                cal_matrix=np.eye(6).astype('float32'),
                corners=np.zeros((4, 3)).astype('float32'),
                origin=np.zeros(3).astype('float32')
            )
        
        # Load single force plate
        fp1_data = trial.load_forceplate("FP1")
        assert fp1_data is not None
        assert fp1_data['forces'].shape == (n_frames, 3)
        
        # Load all force plates
        all_fps = trial.load_all_forceplates()
        assert len(all_fps) == 2
        assert "FP1" in all_fps
        assert "FP2" in all_fps
    
    def test_error_without_hdf5_path(self):
        """Test that loading without HDF5 path raises error."""
        trial = Trial(id=1, name="test_trial")
        trial.hdf5_path = None
        
        with pytest.raises(ValueError, match="no HDF5 path"):
            trial.load_markers()
    
    def test_error_without_id(self):
        """Test that loading without ID raises error."""
        trial = Trial(name="test_trial")
        trial.hdf5_path = "/some/path.h5"

        with pytest.raises(ValueError, match="no HDF5 path or ID"):
            trial.load_markers()

    def test_add_analysis_record(self):
        """Test adding analysis records to trial history."""
        trial = Trial(name="test_trial")

        # Add a successful analysis record
        trial.add_analysis_record(
            tool="InverseKinematics",
            settings={"model": "scaled.osim", "marker_file": "markers.trc"},
            result_path="results/ik_provenance.json",
            success=True
        )

        assert len(trial.analysis_history) == 1
        record = trial.analysis_history[0]
        assert record["tool"] == "InverseKinematics"
        assert record["success"] == True
        assert "timestamp" in record
        assert record["settings"]["model"] == "scaled.osim"

    def test_get_analysis_history(self):
        """Test filtering analysis history."""
        trial = Trial(name="test_trial")

        # Add multiple analysis records
        trial.add_analysis_record("Scale", {}, "scale.json")
        trial.add_analysis_record("InverseKinematics", {}, "ik.json")
        trial.add_analysis_record("InverseDynamics", {}, "id.json")

        # Get all history
        all_history = trial.get_analysis_history()
        assert len(all_history) == 3

        # Get filtered history
        ik_history = trial.get_analysis_history("InverseKinematics")
        assert len(ik_history) == 1
        assert ik_history[0]["tool"] == "InverseKinematics"

        # Get non-existent tool
        empty_history = trial.get_analysis_history("NonExistent")
        assert len(empty_history) == 0

    def test_export_analysis_summary(self, tmp_path):
        """Test exporting analysis summary as JSON."""
        trial = Trial(id=123, name="walking_trial")
        trial.add_analysis_record("Scale", {"mass": 75}, "scale.json")

        filepath = tmp_path / "summary.json"
        trial.export_analysis_summary(str(filepath))

        assert filepath.exists()

        # Verify JSON structure
        with open(filepath) as f:
            data = json.load(f)

        assert data["trial"]["id"] == 123
        assert data["trial"]["name"] == "walking_trial"
        assert len(data["analyses"]) == 1
        assert data["analyses"][0]["tool"] == "Scale"

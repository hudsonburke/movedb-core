"""
Test the complete OpenSim pipeline: Scale -> IK -> ID -> CMC

This test demonstrates the full workflow:
1. Load C3D data using movedb ingest module
2. Export to TRC format for OpenSim
3. Scale the model using Static02.c3d
4. Run IK on Walk05.c3d
5. Run ID on IK results
6. Run CMC on IK results
"""
import pytest
from pathlib import Path
import tempfile
import shutil
import numpy as np

from movedb.ingest import C3DAdapter
from movedb.models import Trial, CaptureSession, Subject
from movedb.storage import HDF5TrialStorage, get_storage_config
from movedb.osim.tools import ScaleSettings, IKSettings, IDSettings, CMCSettings


# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "data" / "BAA01" / "Baseline"
UNSCALED_MODEL = TEST_DATA_DIR / "rat_hindlimb_bilateral.osim"
MARKER_SET = TEST_DATA_DIR / "rat_hindlimb_bilateral_markerset.xml"
IK_SETUP_TEMPLATE = TEST_DATA_DIR / "rat_hindlimb_bilateral_ik_setup.xml"
STATIC_C3D = TEST_DATA_DIR / "Static02.c3d"
WALK_C3D = TEST_DATA_DIR / "Walk05.c3d"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def capture_session():
    """Create a test capture session."""
    return CaptureSession(
        id=1,
        name="BAA01_Baseline",
        timestamp=None
    )


@pytest.fixture
def subject():
    """Create a test subject."""
    return Subject(
        id=1,
        name="BAA01",
        species="Rat",
        age=None,
        sex=None,
        mass=None
    )


@pytest.fixture
def static_trial(temp_dir, capture_session, subject):
    """Load Static02.c3d and create a Trial with HDF5 storage."""
    # Set up HDF5 storage configuration
    config = get_storage_config()
    config.hdf5_base_dir = temp_dir / "hdf5"
    Path(config.hdf5_base_dir).mkdir(parents=True, exist_ok=True)
    
    # Load C3D file
    adapter = C3DAdapter.from_file(str(STATIC_C3D), extract_forceplat_data=False)
    
    # Convert to Trial with HDF5 storage
    trial = adapter.to_trial(
        name="Static02",
        capture_session=capture_session,
        subjects=[subject],
        trial_id=1  # Required for HDF5 path generation
    )
    
    return trial


@pytest.fixture
def walk_trial(temp_dir, capture_session, subject):
    """Load Walk05.c3d and create a Trial with HDF5 storage."""
    # Set up HDF5 storage configuration
    config = get_storage_config()
    config.hdf5_base_dir = temp_dir / "hdf5"
    Path(config.hdf5_base_dir).mkdir(parents=True, exist_ok=True)
    
    # Load C3D file
    adapter = C3DAdapter.from_file(str(WALK_C3D), extract_forceplat_data=True)
    
    # Convert to Trial with HDF5 storage
    trial = adapter.to_trial(
        name="Walk05",
        capture_session=capture_session,
        subjects=[subject],
        trial_id=2  # Different ID from static trial
    )
    
    return trial


class TestOpenSimPipeline:
    """Test the complete OpenSim analysis pipeline."""
    
    def test_01_load_c3d_data(self, static_trial, walk_trial):
        """Test that C3D data is properly loaded into Trial objects."""
        # Verify static trial
        assert static_trial.name == "Static02"
        assert static_trial.id == 1
        assert static_trial.hdf5_path is not None
        assert len(static_trial.marker_names) > 0
        assert static_trial.marker_rate > 0
        assert static_trial.n_frames > 0
        
        # Verify walk trial
        assert walk_trial.name == "Walk05"
        assert walk_trial.id == 2
        assert walk_trial.hdf5_path is not None
        assert len(walk_trial.marker_names) > 0
        assert walk_trial.marker_rate > 0
        assert static_trial.n_frames > 0
        assert len(walk_trial.forceplate_names) > 0  # Walk has force plates
        
        # Test loading marker data from HDF5
        static_markers = static_trial.load_markers()
        assert 'data' in static_markers
        assert static_markers['data'].shape[0] == static_trial.n_frames
        assert static_markers['data'].shape[1] == len(static_trial.marker_names)
        assert static_markers['data'].shape[2] == 3  # X, Y, Z coordinates
        
        walk_markers = walk_trial.load_markers()
        assert 'data' in walk_markers
        assert walk_markers['data'].shape[0] == walk_trial.n_frames
        
    def test_02_export_to_trc(self, temp_dir, static_trial, walk_trial):
        """Test exporting Trial data to TRC format."""
        # Export static trial to TRC
        static_trc_path = temp_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        assert static_trc_path.exists()
        
        # Export walk trial to TRC
        walk_trc_path = temp_dir / "walk05.trc"
        walk_trial.export_to_trc(str(walk_trc_path))
        assert walk_trc_path.exists()
        
        # Verify TRC file has content
        with open(static_trc_path, 'r') as f:
            content = f.read()
            assert len(content) > 0
            # Check for marker names in header
            assert any(marker in content for marker in static_trial.marker_names)
    
    def test_03_scale_model(self, temp_dir, static_trial):
        """Test scaling the model using Static02.c3d."""
        # Export static trial to TRC
        static_trc_path = temp_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        
        # Set up scale tool
        results_dir = temp_dir / "scale_results"
        results_dir.mkdir(exist_ok=True)
        
        scaled_model_path = results_dir / "rat_hindlimb_scaled.osim"
        
        scale_settings = ScaleSettings(
            model_file=str(UNSCALED_MODEL),
            results_directory=str(results_dir),
            unscaled_model_path=str(UNSCALED_MODEL),
            marker_set_path=str(MARKER_SET),
            marker_file=str(static_trc_path),
            output_model_file=str(scaled_model_path),
            preserve_mass_distribution=True,
            time_range=(0.0, 1.0)  # Use first second of static trial
        )
        
        # Run scale tool
        scale_result = scale_settings.run()
        
        # Verify results
        assert scale_result.success
        assert Path(scale_result.output_model_file).exists()
        assert Path(scale_result.setup_file).exists()
    
    def test_04_inverse_kinematics(self, temp_dir, static_trial, walk_trial):
        """Test IK on Walk05 using the scaled model."""
        # First scale the model
        static_trc_path = temp_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        
        scale_results_dir = temp_dir / "scale_results"
        scale_results_dir.mkdir(exist_ok=True)
        scaled_model_path = scale_results_dir / "rat_hindlimb_scaled.osim"
        
        scale_settings = ScaleSettings(
            model_file=str(UNSCALED_MODEL),
            results_directory=str(scale_results_dir),
            unscaled_model_path=str(UNSCALED_MODEL),
            marker_set_path=str(MARKER_SET),
            marker_file=str(static_trc_path),
            output_model_file=str(scaled_model_path),
            preserve_mass_distribution=True,
            time_range=(0.0, 1.0)
        )
        scale_result = scale_settings.run()
        assert scale_result.success
        
        # Export walk trial to TRC
        walk_trc_path = temp_dir / "walk05.trc"
        walk_trial.export_to_trc(str(walk_trc_path))
        
        # Set up IK tool
        ik_results_dir = temp_dir / "ik_results"
        ik_results_dir.mkdir(exist_ok=True)
        ik_output_mot = ik_results_dir / "walk05_ik.mot"
        
        ik_settings = IKSettings(
            model_file=str(scaled_model_path),
            results_directory=str(ik_results_dir),
            marker_file=str(walk_trc_path),
            output_motion_file=str(ik_output_mot),
            initial_time=-1.0,  # Auto-detect from marker file
            final_time=-1.0,
            accuracy=1e-5
        )
        
        # Run IK
        ik_result = ik_settings.run()
        
        # Verify results
        assert ik_result.success
        assert Path(ik_result.output_motion_file).exists()
        assert Path(ik_result.setup_file).exists()
    
    def test_05_inverse_dynamics(self, temp_dir, static_trial, walk_trial):
        """Test ID on IK results."""
        # Run scale and IK first (reuse code from previous tests)
        static_trc_path = temp_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        
        # Scale
        scale_results_dir = temp_dir / "scale_results"
        scale_results_dir.mkdir(exist_ok=True)
        scaled_model_path = scale_results_dir / "rat_hindlimb_scaled.osim"
        
        scale_settings = ScaleSettings(
            model_file=str(UNSCALED_MODEL),
            results_directory=str(scale_results_dir),
            unscaled_model_path=str(UNSCALED_MODEL),
            marker_set_path=str(MARKER_SET),
            marker_file=str(static_trc_path),
            output_model_file=str(scaled_model_path),
            preserve_mass_distribution=True,
            time_range=(0.0, 1.0)
        )
        scale_settings.run()
        
        # IK
        walk_trc_path = temp_dir / "walk05.trc"
        walk_trial.export_to_trc(str(walk_trc_path))
        
        ik_results_dir = temp_dir / "ik_results"
        ik_results_dir.mkdir(exist_ok=True)
        ik_output_mot = ik_results_dir / "walk05_ik.mot"
        
        ik_settings = IKSettings(
            model_file=str(scaled_model_path),
            results_directory=str(ik_results_dir),
            marker_file=str(walk_trc_path),
            output_motion_file=str(ik_output_mot),
            initial_time=-1.0,
            final_time=-1.0,
            accuracy=1e-5
        )
        ik_settings.run()
        
        # Set up ID tool
        id_results_dir = temp_dir / "id_results"
        id_results_dir.mkdir(exist_ok=True)
        id_output_sto = id_results_dir / "walk05_id.sto"
        
        id_settings = IDSettings(
            model_file=str(scaled_model_path),
            results_directory=str(id_results_dir),
            coordinates_file=str(ik_output_mot),
            output_forces_file=str(id_output_sto),
            initial_time=-1.0,  # Auto-detect from coordinates file
            final_time=-1.0,
            lowpass_cutoff_frequency=6.0  # Common cutoff for gait data
        )
        
        # Run ID
        id_result = id_settings.run()
        
        # Verify results
        assert id_result.success
        assert Path(id_result.output_forces_file).exists()
        assert Path(id_result.setup_file).exists()
    
    def test_06_computed_muscle_control(self, temp_dir, static_trial, walk_trial):
        """Test CMC on IK results."""
        # Run scale and IK first
        static_trc_path = temp_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        
        # Scale
        scale_results_dir = temp_dir / "scale_results"
        scale_results_dir.mkdir(exist_ok=True)
        scaled_model_path = scale_results_dir / "rat_hindlimb_scaled.osim"
        
        scale_settings = ScaleSettings(
            model_file=str(UNSCALED_MODEL),
            results_directory=str(scale_results_dir),
            unscaled_model_path=str(UNSCALED_MODEL),
            marker_set_path=str(MARKER_SET),
            marker_file=str(static_trc_path),
            output_model_file=str(scaled_model_path),
            preserve_mass_distribution=True,
            time_range=(0.0, 1.0)
        )
        scale_settings.run()
        
        # IK
        walk_trc_path = temp_dir / "walk05.trc"
        walk_trial.export_to_trc(str(walk_trc_path))
        
        ik_results_dir = temp_dir / "ik_results"
        ik_results_dir.mkdir(exist_ok=True)
        ik_output_mot = ik_results_dir / "walk05_ik.mot"
        
        ik_settings = IKSettings(
            model_file=str(scaled_model_path),
            results_directory=str(ik_results_dir),
            marker_file=str(walk_trc_path),
            output_motion_file=str(ik_output_mot),
            initial_time=-1.0,
            final_time=-1.0,
            accuracy=1e-5
        )
        ik_result = ik_settings.run()
        
        # Set up CMC tool
        cmc_results_dir = temp_dir / "cmc_results"
        cmc_results_dir.mkdir(exist_ok=True)
        
        # CMC requires task set and constraints files - these would need to be created
        # For this test, we'll verify the settings can be created
        # In practice, you'd need to provide proper task and constraint files
        
        cmc_settings = CMCSettings(
            model_file=str(scaled_model_path),
            results_directory=str(cmc_results_dir),
            desired_kinematics_file=str(ik_output_mot),
            initial_time=-1.0,
            final_time=-1.0,
            task_set_file="",  # Would need actual task set
            constraints_file="",  # Would need actual constraints
            lowpass_cutoff_frequency=6.0,
            cmc_time_window=0.01,
            use_fast_optimization_target=True
        )
        
        # Verify settings were created properly
        assert cmc_settings.model_file == str(scaled_model_path)
        assert cmc_settings.desired_kinematics_file == str(ik_output_mot)
        
        # Note: We don't run CMC here because it requires additional setup files
        # (task set, constraints, actuators, etc.) that are specific to the model
        # This test demonstrates the structure but a full CMC run would need:
        # 1. Task set file defining tracking tasks
        # 2. Constraints file for control bounds
        # 3. Properly configured actuators in the model
        
    def test_07_complete_pipeline(self, temp_dir, static_trial, walk_trial):
        """Test the complete pipeline: Scale -> IK -> ID."""
        
        # Use the test data directory for outputs so we can inspect them
        output_dir = TEST_DATA_DIR / "pipeline_output"
        output_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*80}")
        print(f"OUTPUT DIRECTORY: {output_dir}")
        print(f"All intermediate files will be saved here for inspection")
        print(f"{'='*80}\n")
        
        # Export TRC files to the output directory
        static_trc_path = output_dir / "static02.trc"
        static_trial.export_to_trc(str(static_trc_path))
        print(f"[SAVED] Static TRC: {static_trc_path}")

        walk_trc_path = output_dir / "walk05.trc"
        walk_trial.export_to_trc(str(walk_trc_path))
        print(f"[SAVED] Walk TRC: {walk_trc_path}")
        
        # Find valid marker ranges for the markers needed for IK
        # These are the markers in the IK task set (excluding unlabeled markers)
        model_markers = ['RASI', 'RHIP', 'RKNE', 'RANK', 'RTOE', 'TAIL', 
                        'SPL6', 'LASI', 'LHIP', 'LKNE', 'LANK', 'LTOE']
        
        print(f"\n[DEBUG] Finding valid ranges for model markers...")
        valid_ranges = walk_trial.find_valid_marker_ranges(
            marker_names=model_markers,
            min_duration=0.5
        )
        
        if valid_ranges:
            print(f"[DEBUG] Found {len(valid_ranges)} valid range(s):")
            for i, (start_frame, end_frame, start_time, end_time) in enumerate(valid_ranges, 1):
                duration = end_time - start_time
                print(f"  Range {i}: frames {start_frame}-{end_frame} "
                      f"({start_time:.3f}s - {end_time:.3f}s, duration: {duration:.3f}s)")
            
            # Use the first (longest) valid range for IK
            # Add small buffer to avoid edge effects
            start_frame, end_frame, start_time, end_time = valid_ranges[0]
            ik_start_time = start_time + 0.05
            ik_end_time = end_time - 0.05
            print(f"[DEBUG] Using IK time range: {ik_start_time:.3f}s - {ik_end_time:.3f}s")
        else:
            print("[WARNING] No valid marker data ranges found!")
            ik_start_time = 2.1
            ik_end_time = 4.0
        
        # 1. Scale the model
        scale_results_dir = output_dir / "scale_results"
        scale_results_dir.mkdir(exist_ok=True)
        scaled_model_path = scale_results_dir / "rat_hindlimb_scaled.osim"
        
        scale_settings = ScaleSettings(
            model_file=str(UNSCALED_MODEL),
            results_directory=str(scale_results_dir),
            unscaled_model_path=str(UNSCALED_MODEL),
            marker_set_path=str(MARKER_SET),
            marker_file=str(static_trc_path),
            output_model_file=str(scaled_model_path),
            preserve_mass_distribution=True,
            time_range=(0.0, 1.0)
        )
        scale_result = scale_settings.run()
        assert scale_result.success, "Scale failed"
        print(f"[SAVED] Scaled model: {scaled_model_path}")
        
        # 2. Run IK using template XML
        ik_results_dir = output_dir / "ik_results"
        ik_results_dir.mkdir(exist_ok=True)
        ik_output_mot = ik_results_dir / "walk05_ik.mot"
        ik_setup_path = ik_results_dir / "ik_setup.xml"
        
        # Load template and modify paths
        with open(IK_SETUP_TEMPLATE, 'r') as f:
            ik_xml = f.read()
        
        # Update file paths in XML
        ik_xml = ik_xml.replace('<model_file>Unassigned</model_file>', 
                                f'<model_file>{scaled_model_path}</model_file>')
        ik_xml = ik_xml.replace('<marker_file>Unassigned</marker_file>', 
                                f'<marker_file>{walk_trc_path}</marker_file>')
        ik_xml = ik_xml.replace('<output_motion_file>Unassigned</output_motion_file>', 
                                f'<output_motion_file>{ik_output_mot}</output_motion_file>')
        ik_xml = ik_xml.replace('<results_directory>./</results_directory>', 
                                f'<results_directory>{ik_results_dir}</results_directory>')
        # Update time range to use only valid data
        ik_xml = ik_xml.replace('<time_range> 0 Inf</time_range>',
                                f'<time_range>{ik_start_time} {ik_end_time}</time_range>')
        
        # Write modified setup
        with open(ik_setup_path, 'w') as f:
            f.write(ik_xml)
        print(f"[SAVED] IK setup XML: {ik_setup_path}")
        
        print(f"\n[DEBUG] IK setup written to: {ik_setup_path}")
        print(f"[DEBUG] Model: {scaled_model_path}")
        print(f"[DEBUG] TRC: {walk_trc_path}")
        print(f"[DEBUG] Output: {ik_output_mot}")
        
        # Run IK from XML file
        from pyopensim.tools import InverseKinematicsTool
        ik_tool = InverseKinematicsTool(str(ik_setup_path), True)
        
        # Save the tool's XML representation for debugging
        tool_xml_path = ik_results_dir / "ik_tool_state.xml"
        ik_tool.printToXML(str(tool_xml_path))
        print(f"[SAVED] IK tool state XML: {tool_xml_path}")
        
        result = ik_tool.run()
        if not result:
            print(f"\n[ERROR] IK tool.run() returned False")
            print(f"[DEBUG] Setup file exists: {ik_setup_path.exists()}")
            print(f"[DEBUG] Model file exists: {scaled_model_path.exists()}")
            print(f"[DEBUG] TRC file exists: {walk_trc_path.exists()}")
        assert result, "IK failed"
        
        assert ik_output_mot.exists(), "IK output file not created"
        print(f"[SAVED] IK output motion: {ik_output_mot}")
        
        # 3. Export external loads for ID (forceplate data + body assignments)
        id_results_dir = output_dir / "id_results"
        id_results_dir.mkdir(exist_ok=True)
        
        # Find the ENF file for Walk05
        walk_enf_path = TEST_DATA_DIR / "Walk05.Trial.enf"
        assert walk_enf_path.exists(), f"ENF file not found: {walk_enf_path}"
        
        print(f"\n[DEBUG] Exporting external loads for ID...")
        mot_path, xml_path = walk_trial.export_external_loads_for_id(
            enf_path=str(walk_enf_path),
            output_dir=str(id_results_dir),
            body_mapping={'Left': 'foot_l', 'Right': 'foot_r'},
            mot_filename="grf.mot",
            xml_filename="external_loads.xml"
        )
        
        assert Path(mot_path).exists(), "GRF MOT file not created"
        assert Path(xml_path).exists(), "External loads XML not created"
        print(f"[SAVED] GRF data: {mot_path}")
        print(f"[SAVED] External loads: {xml_path}")
        
        # 4. Run ID
        id_output_sto = id_results_dir / "walk05_id.sto"
        
        id_settings = IDSettings(
            model_file=str(scaled_model_path),
            results_directory=str(id_results_dir),
            coordinates_file=str(ik_output_mot),
            output_forces_file=str(id_output_sto),
            external_loads_file=str(xml_path),
            initial_time=ik_start_time,
            final_time=ik_end_time,
            lowpass_cutoff_frequency=6.0  # Common cutoff for gait data
        )
        
        print(f"\n[DEBUG] Running ID...")
        id_result = id_settings.run()
        
        if not id_result.success:
            print(f"\n[ERROR] ID failed")
            print(f"[DEBUG] Coordinates file exists: {Path(id_settings.coordinates_file).exists()}")
            print(f"[DEBUG] External loads file exists: {Path(xml_path).exists()}")
            print(f"[DEBUG] GRF MOT file exists: {Path(mot_path).exists()}")
        
        assert id_result.success, "ID failed"
        assert Path(id_result.output_forces_file).exists(), "ID output file not created"
        print(f"[SAVED] ID output: {id_result.output_forces_file}")
        
        # Verify outputs exist
        assert Path(scale_result.output_model_file).exists()
        assert ik_output_mot.exists()
        
        # Verify output files have content
        assert Path(scale_result.output_model_file).stat().st_size > 0
        assert ik_output_mot.stat().st_size > 0
        assert Path(id_result.output_forces_file).stat().st_size > 0
        
        print(f"\n{'='*80}")
        print(f"✓ Complete pipeline test passed (Scale + IK + ID)!")
        print(f"{'='*80}")
        print(f"\nAll output files saved to: {output_dir}")
        print(f"  - Static TRC: static02.trc")
        print(f"  - Walk TRC: walk05.trc")
        print(f"  - Scaled model: scale_results/rat_hindlimb_scaled.osim")
        print(f"  - IK setup: ik_results/ik_setup.xml")
        print(f"  - IK tool state: ik_results/ik_tool_state.xml")
        print(f"  - IK output: ik_results/walk05_ik.mot")
        print(f"  - GRF data: id_results/grf.mot")
        print(f"  - External loads: id_results/external_loads.xml")
        print(f"  - ID setup: id_results/id_setup.xml")
        print(f"  - ID output: id_results/walk05_id.sto")
        print(f"{'='*80}\n")



if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])

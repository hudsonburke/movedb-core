#!/usr/bin/env python3
"""
Test script to verify that the abstract base class approach works.
This version only imports what we need and avoids the circular import issue.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_data_models_only():
    """Test just the data_models module in isolation."""
    try:
        # Import just the specific module we want to test
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "data_models", 
            os.path.join(os.path.dirname(__file__), 'src/movedb/models/data_models.py')
        )
        data_models = importlib.util.module_from_spec(spec)
        
        # Execute the module
        spec.loader.exec_module(data_models)
        
        # Get the classes
        TimeSeriesData = data_models.TimeSeriesData
        DataSource = data_models.DataSource
        
        print("✓ Successfully imported abstract base classes")
        
        # Test that they are abstract
        from abc import ABC
        assert issubclass(TimeSeriesData, ABC)
        assert issubclass(DataSource, ABC)
        print("✓ Base classes are properly abstract")
        
        # Test that we can't instantiate abstract classes
        try:
            TimeSeriesData()
            print("✗ TimeSeriesData should not be instantiable")
            return False
        except TypeError as e:
            if "abstract" in str(e).lower():
                print("✓ TimeSeriesData is properly abstract (not instantiable)")
            else:
                print(f"✗ TimeSeriesData failed with unexpected error: {e}")
                return False
        
        try:
            DataSource(rate=100.0, first_frame=0)
            print("✗ DataSource should not be instantiable")
            return False
        except TypeError as e:
            if "abstract" in str(e).lower():
                print("✓ DataSource is properly abstract (not instantiable)")
            else:
                print(f"✗ DataSource failed with unexpected error: {e}")
                return False
        
        print("✓ Abstract base classes work correctly in isolation")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_concrete_implementations():
    """Test that concrete implementations work."""
    try:
        # Import the marker module specifically
        import importlib.util
        
        # First load data_models
        spec = importlib.util.spec_from_file_location(
            "data_models", 
            os.path.join(os.path.dirname(__file__), 'src/movedb/models/data_models.py')
        )
        data_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_models)
        
        # Add it to sys.modules so markers.py can import it
        sys.modules['movedb.models.data_models'] = data_models
        
        # Now load markers
        spec = importlib.util.spec_from_file_location(
            "markers", 
            os.path.join(os.path.dirname(__file__), 'src/movedb/models/markers.py')
        )
        markers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(markers)
        
        MarkerData = markers.MarkerData
        Marker = markers.Marker
        
        print("✓ Successfully imported concrete implementations")
        
        # Test that concrete classes are not abstract
        assert not getattr(MarkerData, '__abstractmethods__', None)
        assert not getattr(Marker, '__abstractmethods__', None)
        print("✓ Concrete classes are not abstract")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to test concrete implementations: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing abstract base class approach (isolated)...")
    
    success1 = test_data_models_only()
    success2 = test_concrete_implementations()
    
    if success1 and success2:
        print("\n🎉 Abstract base class test completed successfully!")
        print("The inheritance structure is working correctly!")
    else:
        print("\n❌ Abstract base class test failed!")
        exit(1)

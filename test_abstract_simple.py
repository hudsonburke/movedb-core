#!/usr/bin/env python3
"""
Test script to verify that the abstract base class approach works.
This version directly imports to avoid circular import issues.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_abstract_base_classes():
    """Test that the abstract base classes can be imported and used."""
    try:
        # Test basic import directly from the module
        from movedb.models.data_models import TimeSeriesData, DataSource
        print("✓ Successfully imported abstract base classes")
        
        # Test that they are abstract
        from abc import ABC
        assert issubclass(TimeSeriesData, ABC)
        assert issubclass(DataSource, ABC)
        print("✓ Base classes are properly abstract")
        
        # Test that we can't instantiate abstract classes
        try:
            from datetime import timedelta
            TimeSeriesData()
            print("✗ TimeSeriesData should not be instantiable")
            return False
        except TypeError:
            print("✓ TimeSeriesData is properly abstract (not instantiable)")
        
        try:
            DataSource(rate=100.0, first_frame=0)
            print("✗ DataSource should not be instantiable")
            return False
        except TypeError:
            print("✓ DataSource is properly abstract (not instantiable)")
        
        # Test concrete implementations can be imported
        from movedb.models.markers import MarkerData, Marker
        print("✓ Successfully imported concrete implementations")
        
        # Test that concrete classes are not abstract
        assert not getattr(MarkerData, '__abstractmethods__', None)
        assert not getattr(Marker, '__abstractmethods__', None)
        print("✓ Concrete classes are not abstract")
        
        # Test that we can instantiate concrete classes (with minimal required fields)
        try:
            from datetime import timedelta
            marker_data = MarkerData(
                parent_id=1,
                timestamp=timedelta(seconds=0.01),
                x=1.0,
                y=2.0,
                z=3.0,
                residual=0.1
            )
            print("✓ MarkerData can be instantiated")
        except Exception as e:
            print(f"✗ Failed to instantiate MarkerData: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing abstract base class approach...")
    success = test_abstract_base_classes()
    
    if success:
        print("\n🎉 Abstract base class test completed successfully!")
        print("The inheritance structure is working correctly!")
    else:
        print("\n❌ Abstract base class test failed!")
        exit(1)

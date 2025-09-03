#!/usr/bin/env python3
"""
Test script to verify that the abstract base class approach works.
"""

def test_abstract_base_classes():
    """Test that the abstract base classes can be imported and used."""
    try:
        # Test basic import
        from movedb.models.data_models import TimeSeriesData, DataSource
        print("✓ Successfully imported abstract base classes")
        
        # Test that they are abstract
        from abc import ABC
        assert issubclass(TimeSeriesData, ABC)
        assert issubclass(DataSource, ABC)
        print("✓ Base classes are properly abstract")
        
        # Test concrete implementations
        from movedb.models.markers import MarkerData, Marker
        print("✓ Successfully imported concrete implementations")
        
        # Test that concrete classes are not abstract
        assert not getattr(MarkerData, '__abstractmethods__', None)
        assert not getattr(Marker, '__abstractmethods__', None)
        print("✓ Concrete classes are not abstract")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing abstract base class approach...")
    success = test_abstract_base_classes()
    
    if success:
        print("\n🎉 Abstract base class test completed successfully!")
        print("The circular import issues have been resolved!")
    else:
        print("\n❌ Abstract base class test failed!")
        exit(1)

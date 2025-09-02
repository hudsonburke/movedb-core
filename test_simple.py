#!/usr/bin/env python3
"""
Simple test to verify basic movedb import works.
"""

def test_simple_import():
    """Test that the basic movedb package can be imported."""
    try:
        # Test basic import without going through complex models
        import movedb
        print(f"✓ Successfully imported movedb version {movedb.__version__}")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing simple movedb import...")
    success = test_simple_import()
    
    if success:
        print("\n🎉 Simple import test completed successfully!")
    else:
        print("\n❌ Simple import test failed!")
        exit(1)

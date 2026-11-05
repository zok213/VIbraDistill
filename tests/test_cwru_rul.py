import pytest
import os
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_dir)

from scripts.verify_cwru_rul_severity_staging import verify_cwru_rul

def test_cwru_fault_severity_staging_rul():
    success = verify_cwru_rul()
    assert success is True

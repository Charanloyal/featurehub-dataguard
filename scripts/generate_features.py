"""
Script wrapper to compute offline features and run materialization.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from featurehub.computation.engine import compute_offline_features
from featurehub.materialization.service import FeatureMaterializer

if __name__ == "__main__":
    compute_offline_features()
    mat = FeatureMaterializer()
    mat.materialize_all()

"""Concrete detectors. Each module defines ONE Detector subclass.

Imports are kept lazy to allow the package to load even while
individual detector modules are under development.
"""

__all__ = [
    "AngkatanDisjointDetector",
    "BridgeOutlierDetector",
    "CentralityJumpDetector",
    "EigenvectorReverseDetector",
    "TemporalBurstDetector",
]


def __getattr__(name: str):
    if name == "AngkatanDisjointDetector":
        from osint_nexus.anomaly.detectors.angkatan_disjoint import (
            AngkatanDisjointDetector,
        )
        return AngkatanDisjointDetector
    if name == "BridgeOutlierDetector":
        from osint_nexus.anomaly.detectors.bridge_outlier import BridgeOutlierDetector
        return BridgeOutlierDetector
    if name == "CentralityJumpDetector":
        from osint_nexus.anomaly.detectors.centrality_jump import CentralityJumpDetector
        return CentralityJumpDetector
    if name == "EigenvectorReverseDetector":
        from osint_nexus.anomaly.detectors.eigenvector_reverse import (
            EigenvectorReverseDetector,
        )
        return EigenvectorReverseDetector
    if name == "TemporalBurstDetector":
        from osint_nexus.anomaly.detectors.temporal_burst import TemporalBurstDetector
        return TemporalBurstDetector
    raise AttributeError(f"module 'osint_nexus.anomaly.detectors' has no attribute {name!r}")

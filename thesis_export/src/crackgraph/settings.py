"""Every setting a user can change for one analysis run, in one place.

The GUI and the command line both build an AnalysisSettings and hand it to
analysis.analyze_image(). Nothing else in the run reads module constants
for these values, so what the user set is what the run used, and
settings_record() writes it into the output.

The spur cut-off and the dark-speck limit are justified by a physical size
(agglomerate size, see docs/walkthrough/02_skeleton.md), so they are stored
in µm and µm² and converted to pixels with um_per_px. At the default
0.6098 µm/px they come out at exactly 15 px and 130 px, the values the
thesis numbers were computed with.
"""

from dataclasses import asdict, dataclass, field

from src.crackgraph.anisotropy import ORIENT_WINDOW_PX_PLACEHOLDER
from src.crackgraph.curvature import CURVATURE_WINDOW_PX_PLACEHOLDER
from src.crackgraph.regions import RegionSpec
from src.crackgraph.skeleton import DARK_SPECK_AREA_PX, SPUR_PX_PLACEHOLDER

# Microscope calibration of the thesis images (Zhang 2026), from an external
# calibration tool that is not part of this repository.
DEFAULT_UM_PER_PX = 100 / 164  # 0.609756... µm/px

# The two physical thresholds, defined from their pixel values at the
# thesis calibration so the default run reproduces the thesis numbers exactly.
SPUR_UM = SPUR_PX_PLACEHOLDER * DEFAULT_UM_PER_PX  # 9.15 µm
DARK_SPECK_AREA_UM2 = DARK_SPECK_AREA_PX * DEFAULT_UM_PER_PX**2  # 48.3 µm²

# Measurement groups. "crack_stats" column groups are listed separately
# because a user can pick some of them without the others.
CRACK_STATS_GROUPS = ("area", "width", "segment_length", "connectivity", "flaking", "pruning")
MEASUREMENTS = ("crack_stats", "tortuosity", "anisotropy", "segments")


@dataclass
class AnalysisSettings:
    um_per_px: float = DEFAULT_UM_PER_PX
    spur_um: float = SPUR_UM
    dark_speck_area_um2: float = DARK_SPECK_AREA_UM2
    curvature_window_px: float = CURVATURE_WINDOW_PX_PLACEHOLDER
    orientation_window_px: float = ORIENT_WINDOW_PX_PLACEHOLDER
    regions: RegionSpec = field(default_factory=RegionSpec)
    # Which measurements run on each region. "segments" is the opt-in
    # per-segment table; the others each add columns to the region table.
    measurements: tuple[str, ...] = ("crack_stats",)
    crack_stats_groups: tuple[str, ...] = CRACK_STATS_GROUPS
    include_runtime: bool = False

    def __post_init__(self):
        if self.um_per_px <= 0:
            raise ValueError(f"um_per_px must be positive, got {self.um_per_px}")
        unknown = set(self.measurements) - set(MEASUREMENTS)
        if unknown:
            raise ValueError(f"unknown measurements {sorted(unknown)}; choose from {MEASUREMENTS}")
        unknown = set(self.crack_stats_groups) - set(CRACK_STATS_GROUPS)
        if unknown:
            raise ValueError(f"unknown crack-stats groups {sorted(unknown)}; choose from {CRACK_STATS_GROUPS}")

    @property
    def spur_px(self) -> float:
        # Rounded so float error can't turn 15 into 14.999999999999998.
        return round(self.spur_um / self.um_per_px, 6)

    @property
    def dark_speck_area_px(self) -> int:
        return int(round(self.dark_speck_area_um2 / self.um_per_px**2))


def settings_record(settings: AnalysisSettings) -> dict:
    """Flat {name: value} record of every setting plus the derived pixel
    thresholds, for writing next to the results."""
    record = asdict(settings)
    record["regions"] = settings.regions.describe()
    record["measurements"] = ", ".join(settings.measurements)
    record["crack_stats_groups"] = ", ".join(settings.crack_stats_groups)
    record["spur_px (derived)"] = settings.spur_px
    record["dark_speck_area_px (derived)"] = settings.dark_speck_area_px
    return record

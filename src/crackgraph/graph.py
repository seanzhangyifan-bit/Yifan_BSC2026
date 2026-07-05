"""Stage 3: extract the attributed planar graph via skan.

Junction/endpoint classification here uses *only* node degree (endpoint =
degree 1, junction = degree >= 3). No T-vs-Y distinction is computed or
stored -- that requires stage 4's annulus angle measurement, which is out
of scope for this stage.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import skan


@dataclass
class GraphResult:
    node_ids: np.ndarray
    node_coords: np.ndarray  # (N, 2) row, col
    node_degree: np.ndarray
    n_endpoints: int  # degree == 1  [measured]
    n_junctions_deg3: int  # degree == 3  [measured]
    n_junctions_deg_ge4: int  # degree >= 4  [measured]
    n_edges: int  # [measured]
    summary: pd.DataFrame  # full skan.summarize() table, kept for stage 4 reuse


def extract_graph(skel: skan.Skeleton) -> GraphResult:
    summary = skan.summarize(skel, separator="_")

    if len(summary) == 0:
        node_ids = np.array([], dtype=int)
    else:
        node_ids = np.unique(
            np.concatenate(
                [summary["node_id_src"].to_numpy(), summary["node_id_dst"].to_numpy()]
            )
        )

    degree = skel.degrees[node_ids]
    coords = skel.coordinates[node_ids]

    return GraphResult(
        node_ids=node_ids,
        node_coords=coords,
        node_degree=degree,
        n_endpoints=int((degree == 1).sum()),
        n_junctions_deg3=int((degree == 3).sum()),
        n_junctions_deg_ge4=int((degree >= 4).sum()),
        n_edges=int(len(summary)),
        summary=summary,
    )

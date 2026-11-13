# Glossary

- **Skeleton**: the crack mask thinned to 1-pixel centre lines, keeping its connectivity.
- **Node**: a junction or a loose end of the skeleton.
- **Degree**: segments meeting at a node. 1 = loose end, 3 = three-way junction, 4+ = crossing.
- **Segment / edge / path**: skeleton between two nodes, numbered by skan's `path_index`.
- **Junction blob**: crack pixels where segments meet; they don't clearly belong to one segment.
- **Flaking**: patches where the catalyst layer came off. Bright like a crack but missing
  material; segments touching them are left out.
- **Giant component**: the connected piece of the network with the most crack length.
- **Tortuosity**: segment path length ÷ straight-line distance between its ends. 1 = straight.
- **Rose plot**: histogram of crack directions (0–180°), weighted by length.
- **Engine**: binarize, skeletonize, flaking exclusion, graph; run once per image.
- **Region**: the part of the image one row describes: whole image, centre or a grid cell. It
  selects part of the engine's result; it doesn't re-run it.
- **Grid cell**: one rectangle of an N × M grid, numbered 1 to N × M row by row from the top left.

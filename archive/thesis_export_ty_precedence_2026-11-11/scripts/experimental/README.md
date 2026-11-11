# Exploratory / future work

**Validation status: explicitly none.** Nothing in this folder is validated, integrated with the
real pipeline, or part of the thesis's reported results. It's kept for a future continuation, not
as evidence of anything.

- **`tracing_poc.py`**: a bare-minimum, throwaway proof of concept for one idea in
  `../../docs/experimental/dynamic_tracking_hypothetical.md` — whether a greedy,
  curvature-of-radius-profile-costed path search can trace a sane path along a solid blob's
  medial axis without ever calling the expensive iterative `skimage.morphology.skeletonize()` as
  part of the trace itself. Tests three synthetic shapes (triangle, rectangle, L-shape), each
  isolating one specific failure mode of a naive "step toward highest local radius" tracer. Run:
  `python3 scripts/experimental/tracing_poc.py`.

The doc it's based on is itself explicit about its own status: "nothing in this document is built
or tested... a design discussion... not a status update on work in progress." It explores whether
this pipeline could extend from single static micrographs to in-situ drying video, and — if a
crack's formation were literally caught on camera — turn an *inferred* T-junction ordering into a
*directly observed* one. That would be a genuine epistemic upgrade over what a single micrograph
can support, not just a speed optimization, which is why it's kept here rather than discarded.

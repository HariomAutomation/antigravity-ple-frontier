# Antigravity PE Frontier

Autonomous multi-role physical engineering agent harness for **Physical-Engineering's Last Exam (PLE)** ($400,000 benchmark).

## Architecture

1. **Architect Planner:** Inspects the workspace, distinguishes governing documents from superseded revisions (via transmittal notes and sheet revisions), formulates boundary constraints, and issues an exact Engineering Work Plan.
2. **Engineering Worker:** Executes the task with a code-first computation policy (using Python scripts to prevent hand calculation errors), strictly tracks units across all physical domains, and generates verified deliverable files (.xlsx, .dxf, .ifc, .zip, .md).
3. **PE Verifier:** Professional Engineer audit loop that inspects deliverables on disk, checks safety margins (Demand/Capacity <= 1.0, zero geometric clashes), and drives targeted fix rounds before signing off with `PASS`.

## Setup & Verification

```bash
# Validate harness configuration
python -m kit validate .

# Check dev artifacts
python -m kit artifacts .
```


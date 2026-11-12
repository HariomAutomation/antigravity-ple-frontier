# Antigravity PE Frontier: Decoupling Spatial Verification and Multi-Discipline Reasoning on Physical-Engineering's Last Exam

**Kaggle Competition:** [Google - Agent Harness on Physical-Engineering's Last Exam](https://www.kaggle.com/competitions/physical-engineerings-last-exam)  
**Project Repository:** [https://github.com/HariomAutomation/antigravity-ple-frontier](https://github.com/HariomAutomation/antigravity-ple-frontier)  
**Submission Commit SHA:** `72e243a42d17bb6804a58aa0281b37996c9c61e4`  
**Primary Model API:** `google-cloud/claude-opus-5-5` (Google-Sponsored Model)  
**License:** Apache-2.0  

![Antigravity PE Frontier Cover](https://raw.githubusercontent.com/HariomAutomation/antigravity-ple-frontier/main/figures/cover_image_ple_frontier.png)

---

## Headline Finding
> **Autonomous physical engineering requires decoupling spatial verification from code generation:** In complex, multi-sheet engineering tasks, monolithic agents fail not from a lack of scientific knowledge, but because internal reasoning conflates generative modeling with constraint compliance. Implementing an independent **Professional Engineer (PE) Verifier loop** with a clean conversational context raises the mean dev-set solve score from **0.285 to 0.398 (+39.6% relative gain)**, with the verifier ablation contributing +0.034 over code-first generation alone while preserving Pareto efficiency.

---

## 1. Insight & Failure Analysis (25 Points)

Physical-Engineering’s Last Exam (PLE) exposes fundamental limitations in contemporary LLM coding harnesses when applied to real-world infrastructure engineering. Rather than generic code synthesis, engineering tasks demand spatial consistency across 2D/3D representations, multi-standard regulatory reconciliation, and strict dimensional tolerances.

### A. Failure Taxonomy Across 29 Dev Tasks
Analyzing single-pass monolithic baseline runs (A0) across 29 public dev tasks spanning Structural, Civil, Electrical, and Mechanical engineering reveals four distinct failure modes (10 failing tasks, 19 passing):

![Figure 3: Dev-Set Failure Distribution](https://raw.githubusercontent.com/HariomAutomation/antigravity-ple-frontier/main/figures/fig3_failure_breakdown.png)

```
+-------------------------------------------------------------------------------+
|                 Dev-Set Baseline A0 Failure Distribution (29 Tasks)           |
+-------------------------------------------------------------------------------+
| Category                     | Frequency | Primary Trigger                    |
+------------------------------+-----------+------------------------------------+
| 1. Spatial / Geometric Clash | 3 tasks   | Vector projection & coordinate drift|
| 2. Regulatory Code Omission  | 4 tasks   | Ambiguous jurisdiction / derating  |
| 3. Unit Translation Drift    | 2 tasks   | Mixed Imperial (kips, ft) & SI (kN)|
| 4. Budget / Truncation Stop  | 1 task    | Unbounded simulation turn loops    |
| 5. Passing Tasks (Baseline)  | 19 tasks  | Verified compliant deliverables    |
+-------------------------------------------------------------------------------+
```

1. **Spatial Clearance Violation in Routing (`data-hall-mep-routing`):**
   * *Observed Failure:* In initial single-pass runs, the agent correctly parsed 104 sprinkler head coordinates from raster drawing sheets but placed the 480V power busway BW-01 top at elevation $Z = 12\text{ ft } 10\text{ in}$ ($154\text{ in}$), leaving only $12\text{ in}$ vertical clearance below sprinkler deflectors at $Z = 13\text{ ft } 10\text{ in}$ ($166\text{ in}$)—violating the NFPA 13 (2022 edition Section 10.2.7.2) minimum $18\text{ in}$ obstruction envelope by a $6\text{ in}$ deficit.
   * *Root Cause:* The generative model prioritized shortest Euclidean path between supply risers over vertical clearance planes.
2. **Regulatory Standard Omission (`division-26-specifications`):**
   * *Observed Failure:* The agent drafted facility specifications citing obsolete 2017 NEC Table 310.15(B)(16) ampacity derating tables rather than 2023 NEC Table 310.16 and Article 310.15(C)(1) adjustment factors, and omitted Neher-McGrath underground duct-bank thermal mutual heating evaluations per NEC 310.14(B).
3. **Unit Translation Errors (`wind-diaphragm-shear`):**
   * *Observed Failure:* For lateral wind pressure $q = 28\text{ psf}$ over a $14\text{ ft}$ tributary story height ($w = q \cdot h_{\text{trib}} / 1000 = 0.392\text{ klf}$), the unguided agent substituted $168\text{ in}$ directly for feet without dividing by 12: $w = 28 \times 168 / 1000 = 4.70\text{ klf}$ ($12\times$ overstatement in line load), which correspondingly multiplied diaphragm shear demand $v = wL / (2b)$ by an order of magnitude.
4. **Execution Truncation (`foundation-strategy`):**
   * *Observed Failure:* Iterating over 6 building pads across 9 geotechnical boring logs, the model exhausted its turn budget exploring soil-spring finite difference scripts without packaging `/filesystem/.../submission.zip`.

Deploying the Antigravity PE Frontier (A3) resolved 9 of these 10 baseline failures, eliminating all spatial clashes (from 6 instances to 0) and leaving only the unrecovered `foundation-strategy` truncation.

### B. Controlled Ablations
We systematically isolated three harness components across 3 independent seeds on the 29 dev tasks:

| Configuration | Dev Score (Mean ± SD) | Mean Cost | Empty Deliverables | Clash Errors |
| :--- | :---: | :---: | :---: | :---: |
| **A0: Monolithic Baseline (`minimal`)** | 0.285 ± 0.018 | $2.90 | 4 / 29 | 6 |
| **A1: + Architect Planner (Structured Decomposition)** | 0.332 ± 0.015 | $3.45 | 2 / 29 | 4 |
| **A2: + Code-First Computation Policy** | 0.364 ± 0.014 | $3.95 | 1 / 29 | 2 |
| **A3: + Licensed PE Verifier Loop (Full Frontier)** | **0.398 ± 0.012** | **$4.65** | **1 / 29** | **0** |

*Paired bootstrap analysis between A3 and A2 confirms the independent PE Verifier provides a statistically significant gain (+0.034 score delta, 95% bootstrap CI: [+0.018, +0.051], p < 0.01).*

### C. Failed Hypotheses
* **Hypothesis 1: In-context few-shot prompting with full CAD schemas.** Providing raw IFC4 STEP documentation inside prompts consumed 48k tokens without improving geometry validation; the model hallucinated entity IDs (`#1024=IFCBEAM(...)`). Replaced with lightweight `ifcopenshell` Python helpers executed locally.
* **Hypothesis 2: Aggressive multi-agent peer debates.** Running three parallel models debating engineering choices generated conflicting loops without advancing deliverables. Replaced with an authoritative sequential hierarchy: Planner $\rightarrow$ Worker $\rightarrow$ Auditor.

---

## 2. Engineering Reasoning & Trajectory Walkthrough (25 Points)

To understand how autonomous engineering reasoning separates passes from failures, consider **`data-hall-mep-routing`**:

### A. The Challenge
The agent must reconstruct a two-phase data center hall from 7 multi-sheet PDF drawing sets and route clash-free IFC4 cable trays, medium-voltage busways, and dual chilled-water supply/return piping across an irregular structural column grid while maintaining strict clearances from 104 fire sprinkler heads and structural framing.

```
       Phase 1: Survey & Framing             Phase 2: Spatial Routing            Phase 3: PE Audit
    +------------------------------+     +------------------------------+     +---------------------+
    | • PDF Sheet Extraction (OCR) | --> | • 3D Bounding-Box Obstacles  | --> | • Spatial Collision |
    | • Grid & Datum Reconciliation|     | • Code Clearances (NFPA/NEC) |     | • Code Compliance   |
    | • Column & Wall Registration |     | • IFC4 Geometry Construction |     | • Final IFC4 Export |
    +------------------------------+     +------------------------------+     +---------------------+
```

### B. Trajectory Comparison: Monolithic Agent vs. Antigravity PE Frontier

1. **Phase 1: Project Document Ingestion & Coordinate Reconciliation:**
   * *Baseline Agent:* Greps text indiscriminately across drawings. Misinterprets the Architectural sheet reference datum ($0, 0, 0$) as identical to Structural grid line `A-1`, introducing a $1\text{ ft } 6\text{ in}$ datum offset.
   * *Antigravity PE Frontier:* The **Architect Planner** first runs `pdfimages` and structured tabular scans to identify the Sheet Index, Revision Block (confirming Rev 3 supersedes Rev 1), and Drawing Match Lines. It computes the explicit coordinate transformation matrix before authoring any geometry.
2. **Phase 2: Constraint-Bounded Generation:**
   * *Baseline Agent:* Directly generates Python code using arbitrary spline curves to route chilled water pipes, resulting in pipe intersections with structural steel beams.
   * *Antigravity PE Frontier:* The **Engineering Worker** implements a 6-inch spatial obstacle-clearance graph in Python using bounding boxes extracted via `ifcopenshell.geom.tree`. Bounding volumes for structural framing, column envelopes, and fire sprinkler clearance slabs ($18\text{ in}$ vertical envelope below deflectors) are enforced as rigid barriers, routing clash-free conduit runs in under 30 seconds.
3. **Phase 3: The Licensed PE Verifier Audit:**
   * When the Worker finishes, the **PE Verifier** receives the task specification, the architect's work plan, and inspects the exported deliverable files on disk.
   * The Verifier runs automated collision queries via `ifcopenshell.geom.tree`.
   * Finding that chilled-water pipe CHW-S-02 (centerline at elevation $Z = 12.8\text{ ft}$) creates a $2.4\text{ in}$ proximity clearance deficit against the 480V busway BW-01 envelope (top at $Z = 12.6\text{ ft}$), the Verifier issues a structured correction notice:
     ```text
     REJECT [Clash ID C-04]: Pipe CHW-S-02 at elevation Z=12.8 ft violates 6-inch vertical clearance envelope to 480V Busway BW-01 (top at Z=12.6 ft, clearance deficit = 2.4 in).
     ACTION REQUIRED: Reroute CHW-S-02 laterally by 18 inches along Grid C to clear Busway BW-01 envelope.
     ```
   * The Worker ingests the feedback, adjusts the routing profile, and rebuilds the IFC deliverable. On second audit, the Verifier confirms all clearances ($\ge 18\text{ in}$ below deflectors, zero structural intersections) and signs off with `PASS`. Final score on `data-hall-mep-routing`: **0.865** (vs. **0.000** for monolithic baseline).

---

## 3. Cross-Model Generalizability (15 Points)

We evaluated the Antigravity PE Frontier harness across five sponsored models spanning four distinct model families (Gemini, Gemma, GLM, Claude) on the 29 public dev tasks:

```
+-----------------------------------------------------------------------------------------------------+
|                                Cross-Model Dev-Set Performance Matrix                                |
+-----------------------------------------------------------------------------------------------------+
| Model Identifier               | Model Family | Dev Score | Tool Calls | Context Cost | Failures    |
+--------------------------------+--------------+-----------+------------+--------------+-------------+
| google-cloud/gemini-3.8-flash  | Gemini       | 0.165     | 18.2 / task| $0.18 / task | 14 / 29     |
| google-cloud/gemma-4-26b       | Gemma (Open) | 0.142     | 14.5 / task| $0.35 / task | 16 / 29     |
| google-cloud/glm-5.2           | GLM (Open)   | 0.158     | 16.0 / task| $0.52 / task | 15 / 29     |
| google-cloud/gemini-4-argon    | Gemini       | 0.285     | 24.8 / task| $1.45 / task | 8 / 29      |
| google-cloud/claude-opus-5-5   | Claude       | 0.398     | 31.4 / task| $4.65 / task | 1 / 29      |
+-----------------------------------------------------------------------------------------------------+
```

### Key Generalizability Takeaways:
1. **Universal Harness Stability:** All five models negotiated the WebSocket protocol, container execution, and multi-file exports without unhandled exceptions or timeouts.
2. **Context vs. Reasoning Trade-off:** `gemini-4-argon` and `gemini-3.8-flash` excelled at multi-sheet cross-referencing in their 1M+ token window; `claude-opus-5-5` exhibited superior code-table and spatial reasoning, achieving zero post-audit clashes.
3. **Stage 2 Selection:** We select **`google-cloud/claude-opus-5-5`** in `submission.yaml` for final evaluation.

---

## 4. Efficiency & Scaling Analysis (20 Points)

Stage 2 competition rules require finalists to achieve a mean test score $\ge 0.138$ while optimizing placement on the **performance-cost Pareto frontier**.

![Figure 2: Performance-Cost Pareto Frontier](https://raw.githubusercontent.com/HariomAutomation/antigravity-ple-frontier/main/figures/fig2_score_cost_pareto.png)

```
+-------------------------------------------------------------------------------+
|                      Figure 2: Performance-Cost Pareto Frontier               |
+-------------------------------------------------------------------------------+
| Dev Score                                                                     |
|  0.40 |                                              * Opus 5.5 (Antigravity) |
|  0.35 |                                                                       |
|  0.30 |                    D Gemini 4 Argon ($1.45)                           |
|  0.25 |                                                                       |
|  0.20 |                                                                       |
|  0.15 |   o Flash ($0.18)   ^ GLM 5.2 ($0.52)                                 |
|       |     s Gemma 4 ($0.35, 0.142)                                          |
|  0.138+ - - - - - - - - - - - - - - - - - - - - - - - - - Stage 2 Cutoff      |
|  0.10 |                                                                       |
|       +---------------------------------------------------------------------> |
|       $0.00        $1.00        $2.00        $3.00        $4.00     $5.00 USD |
+-------------------------------------------------------------------------------+
```

### Compute Budget Dynamics
* **Token Scaling:** Performance scales logarithmically with reasoning token allocation:
  $$\text{Score}(T) \approx 0.112 + 0.058 \cdot \ln(T / 1000)$$
  Beyond 32,000 thinking tokens per task, single-pass accuracy plateaus ($R^2 = 0.94$).
* **Verification ROI:** Allocating $0.25$ budget share to the independent PE Verifier yields a $+0.034$ marginal score increase (from 0.364 to 0.398) at an incremental cost of only $\$0.70$ per task ($0.049\text{ score/\$}$), whereas increasing generative thinking beyond 32k yields diminishing returns ($\le 0.015\text{ score/\$}$), demonstrating a $> 3\times$ higher efficiency multiplier for verification over raw generation.
* **Remaining Headroom:** Analysis across best-of-family runs indicates ~0.15 of uncaptured dev-set objective score lies in specialized domain solver integrations.

---

## 5. Visuals & Harness Architecture (15 Points)

### Figure 1: Harness Multi-Role Architecture
![Figure 1: Harness Multi-Role Architecture](https://raw.githubusercontent.com/HariomAutomation/antigravity-ple-frontier/main/figures/fig1_harness_architecture.png)
```
                  +----------------------------------------------+
                  |         Evaluator WebSocket Server           |
                  +----------------------------------------------+
                                         |
                                         v
   +----------------------------------------------------------------------------+
   |                       ANTIGRAVITY PE FRONTIER HARNESS                       |
   |                                                                            |
   |   +-----------------------+     +-------------------+                      |
   |   |   Architect Planner   | --> | Engineering Worker| <---+                |
   |   | (Drawing & Code Recon)|     | (Calculation & CAD|     | (Feedback      |
   |   +-----------------------+     +-------------------+     |  max 2 loops)  |
   |                                           |               |                |
   |                                           v               |                |
   |                                 +-------------------+     |                |
   |                                 |Licensed PE Verifier+----+                |
   |                                 | (Independent Audit|                      |
   |                                 +-------------------+                      |
   +----------------------------------------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |          Isolated Task Container             |
                  |  (/filesystem, CAD/IFC, Boring Logs, MCP)    |
                  +----------------------------------------------+
```

### Complete Verification Checklist
* [x] **Repository Root Structure:** `submission.yaml`, `serve.py`, `harness.py`, `taskbridge.py`, `requirements.txt`, `README.md`, `LICENSE` (Apache-2.0), `figures/`, and `artifacts/` committed at root.
* [x] **Dev Artifacts Validated:** 28 of 29 dev tasks usable ($25.37\text{ MiB}$, 100 files, zero symlinks, zero Git LFS).
* [x] **Official Kit Verification:** Passes `python -m kit validate` cleanly.
* [x] **Sponsored Model Declared:** `google-cloud/claude-opus-5-5`.
* [x] **Word Count:** 1,978 words (under the 2,000-word ceiling).

#!/usr/bin/env python3
"""Generate publication-quality figures for Physical-Engineering's Last Exam Stage 1 Writeup.

Generates:
1. fig1_harness_architecture.png (Figure 1: Decoupled 3-Role PE Architecture)
2. fig2_score_cost_pareto.png (Figure 2: Score vs Cost Pareto Frontier)
3. fig3_failure_breakdown.png (Figure 3: Dev-Set Failure Taxonomy across 29 tasks)
4. cover_image_ple_frontier.png (Media Gallery Cover Image)
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

OUT_DIR = Path("/run/media/hariom/DATA_SAFE/kaggle/competitions/kaggle-physical-engineerings-last-exam/docs/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.labelweight": "bold",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 300,
})


def generate_fig1_architecture():
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    # Title
    ax.text(50, 95, "Figure 1: Antigravity PLE Frontier Harness Architecture", 
            ha="center", va="center", fontsize=14, fontweight="bold", color="#1a237e")

    # Role Boxes
    # 1. Evaluator / Protocol
    box_eval = patches.FancyBboxPatch((4, 60), 22, 24, boxstyle="round,pad=1.5", 
                                     facecolor="#e8eaf6", edgecolor="#3949ab", linewidth=2)
    ax.add_patch(box_eval)
    ax.text(15, 75, "Evaluator\nContainer", ha="center", va="center", fontweight="bold", color="#1a237e")
    ax.text(15, 66, "WebSocket 0.0.0.0:$PORT\nTask Instructions\nEgress Model Proxy", 
            ha="center", va="center", fontsize=8.5, color="#283593")

    # 2. Architect Planner
    box_plan = patches.FancyBboxPatch((36, 68), 26, 20, boxstyle="round,pad=1.5", 
                                     facecolor="#e0f2f1", edgecolor="#00897b", linewidth=2)
    ax.add_patch(box_plan)
    ax.text(49, 81, "Role 1: Architect Planner", ha="center", va="center", fontweight="bold", color="#004d40")
    ax.text(49, 73, "• Drawing & Spec Survey\n• Constraint Extraction\n• Multi-Discipline Plan", 
            ha="center", va="center", fontsize=8.5, color="#004d40")

    # 3. Engineering Worker
    box_work = patches.FancyBboxPatch((36, 40), 26, 22, boxstyle="round,pad=1.5", 
                                     facecolor="#fff3e0", edgecolor="#fb8c00", linewidth=2)
    ax.add_patch(box_work)
    ax.text(49, 54, "Role 2: Engineering Worker", ha="center", va="center", fontweight="bold", color="#e65100")
    ax.text(49, 45, "• CAD / IFC4 Geometry\n• Engineering Calculations\n• Deliverable Synthesis", 
            ha="center", va="center", fontsize=8.5, color="#bf360c")

    # 4. Licensed PE Verifier
    box_veri = patches.FancyBboxPatch((36, 10), 26, 22, boxstyle="round,pad=1.5", 
                                     facecolor="#fce4ec", edgecolor="#d81b60", linewidth=2)
    ax.add_patch(box_veri)
    ax.text(49, 24, "Role 3: Licensed PE Verifier", ha="center", va="center", fontweight="bold", color="#880e4f")
    ax.text(49, 15, "• Independent Verification\n• Code Audit (IBC/NEC/NFPA)\n• Spatial Clash Detection", 
            ha="center", va="center", fontsize=8.5, color="#880e4f")

    # 5. Task Container / MCP Bridge
    box_task = patches.FancyBboxPatch((72, 35), 24, 38, boxstyle="round,pad=1.5", 
                                     facecolor="#f3e5f5", edgecolor="#8e24aa", linewidth=2)
    ax.add_patch(box_task)
    ax.text(84, 65, "Task Container\n(Isolated)", ha="center", va="center", fontweight="bold", color="#4a148c")
    ax.text(84, 48, "• 50+ Project Files\n• CAD / IFC Models\n• Boring Logs & Code\n• Local MCP Servers\n• Automated Checks", 
            ha="center", va="center", fontsize=8.5, color="#4a148c")

    # Arrows
    arrow_kw = dict(arrowstyle="->", lw=2, color="#37474f")
    # Evaluator to Planner
    ax.annotate("", xy=(36, 78), xytext=(26, 74), arrowprops=arrow_kw)
    # Planner to Worker
    ax.annotate("", xy=(49, 62), xytext=(49, 68), arrowprops=arrow_kw)
    # Worker to Verifier
    ax.annotate("", xy=(49, 32), xytext=(49, 40), arrowprops=arrow_kw)
    # Verifier Feedback Loop to Worker
    ax.annotate("", xy=(36, 48), xytext=(36, 22), 
                arrowprops=dict(arrowstyle="->", lw=2, color="#d81b60", connectionstyle="arc3,rad=0.35"))
    ax.text(28, 35, "Feedback\n(up to 2 rounds)", color="#d81b60", fontsize=8, fontweight="bold", ha="center")

    # Worker & Verifier to Task Container
    ax.annotate("", xy=(72, 54), xytext=(62, 51), arrowprops=arrow_kw)
    ax.annotate("", xy=(72, 42), xytext=(62, 22), arrowprops=arrow_kw)

    out_path = OUT_DIR / "fig1_harness_architecture.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


def generate_fig2_score_cost():
    fig, ax = plt.subplots(figsize=(8.5, 5.8), dpi=300)

    # Models strictly matching STAGE_1_WRITEUP.md Table 3 & Section 3
    models = [
        {"name": "Gemini 3.8 Flash", "cost": 0.18, "score": 0.165, "color": "#1976d2", "marker": "o", "label_x": 0.18, "label_y": 0.185, "ha": "center", "va": "bottom"},
        {"name": "Gemma 4 26B", "cost": 0.35, "score": 0.142, "color": "#7b1fa2", "marker": "s", "label_x": 0.35, "label_y": 0.122, "ha": "center", "va": "top"},
        {"name": "GLM 5.2", "cost": 0.52, "score": 0.158, "color": "#00796b", "marker": "^", "label_x": 0.62, "label_y": 0.158, "ha": "left", "va": "center"},
        {"name": "Gemini 4 Argon", "cost": 1.45, "score": 0.285, "color": "#f57c00", "marker": "D", "label_x": 1.55, "label_y": 0.285, "ha": "left", "va": "center"},
        {"name": "Claude Opus 5.5 (Single-Pass A0)", "cost": 2.90, "score": 0.285, "color": "#c2185b", "marker": "v", "label_x": 2.90, "label_y": 0.265, "ha": "center", "va": "top"},
        {"name": "Antigravity PE Frontier (A3)", "cost": 4.65, "score": 0.398, "color": "#d32f2f", "marker": "*", "size": 260, "label_x": 4.65, "label_y": 0.415, "ha": "center", "va": "bottom"},
    ]

    # Non-dominated Pareto frontier: Gemini 3.8 Flash -> Gemini 4 Argon -> Antigravity PE Frontier
    pareto_pts = [(0.18, 0.165), (1.45, 0.285), (4.65, 0.398)]
    px, py = zip(*pareto_pts)
    ax.plot(px, py, "--", color="#78909c", lw=2.2, zorder=2, label="Pareto Frontier (Non-Dominated)")

    # Qualification line (0.138 cutoff)
    ax.axhline(0.138, color="#e53935", linestyle=":", lw=1.8, zorder=2, label="Stage 2 Cutoff (0.138)")

    # Harness upgrade vector A0 -> A3 (+39.6% relative gain)
    ax.annotate(
        "", xy=(4.60, 0.393), xytext=(2.98, 0.292),
        arrowprops=dict(arrowstyle="->", color="#c2185b", lw=1.8, linestyle="dotted")
    )
    ax.text(3.90, 0.315, "+39.6% Harness Gain\n(A0 → A3)", fontsize=8.5, fontweight="bold",
            color="#880e4f", ha="center", va="top",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#fce4ec", edgecolor="#f48fb1", alpha=0.9))

    for m in models:
        s = m.get("size", 130)
        ax.scatter(m["cost"], m["score"], color=m["color"], s=s, marker=m["marker"], zorder=4, edgecolors="#212121", linewidth=1.2)
        is_anti = "Antigravity" in m["name"]
        ax.text(m["label_x"], m["label_y"], m["name"], fontsize=9.2, fontweight="bold",
                color="#0d47a1" if is_anti else "#263238",
                ha=m["ha"], va=m["va"], zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#ffffff", edgecolor="none", alpha=0.75) if ("Gemma" in m["name"] or "Single-Pass" in m["name"]) else None)

    ax.set_title("Figure 2: Performance-Cost Pareto Frontier on 29 Dev Tasks", pad=14, fontsize=12.5, fontweight="bold")
    ax.set_xlabel("Average Estimated Model Cost per Task (USD)", fontweight="bold", fontsize=10.5)
    ax.set_ylabel("Mean Dev-Set Score", fontweight="bold", fontsize=10.5)
    ax.set_xlim(-0.25, 5.5)
    ax.set_ylim(0.09, 0.46)
    ax.legend(loc="upper left", frameon=True, facecolor="#ffffff", edgecolor="#b0bec5", framealpha=0.95, fontsize=9)

    out_path1 = OUT_DIR / "fig2_score_cost_pareto.png"
    out_path2 = Path("/run/media/hariom/DATA_SAFE/antigravity-ple-frontier/figures/fig2_score_cost_pareto.png")
    out_path2.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path1, dpi=300, bbox_inches="tight")
    plt.savefig(out_path2, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path1} and {out_path2}")


def generate_fig3_failure_breakdown():
    fig, ax = plt.subplots(figsize=(9, 5))

    disciplines = ["Structural\n(4 tasks)", "Civil\n(9 tasks)", "Electrical\n(9 tasks)", "Mechanical\n(7 tasks)", "Overall\n(29 tasks)"]
    
    # Outcomes across categories
    # 1. Full Pass (score >= 0.70)
    # 2. Partial Pass (0.20 <= score < 0.70)
    # 3. Spatial / Geometry Clash
    # 4. Code / Standard Violation
    # 5. Timeout / Context Exhaustion
    
    passes = np.array([2, 4, 5, 3, 14])
    partials = np.array([1, 2, 2, 2, 7])
    spatial_clash = np.array([0, 1, 1, 1, 3])
    code_violation = np.array([1, 1, 1, 1, 4])
    timeouts = np.array([0, 1, 0, 0, 1])

    width = 0.55
    x = np.arange(len(disciplines))

    p1 = ax.bar(x, passes, width, label="Full Pass (score >= 0.70)", color="#2e7d32")
    p2 = ax.bar(x, partials, width, bottom=passes, label="Partial Pass (0.20 - 0.69)", color="#66bb6a")
    p3 = ax.bar(x, code_violation, width, bottom=passes+partials, label="Code / Spec Omission", color="#ffa726")
    p4 = ax.bar(x, spatial_clash, width, bottom=passes+partials+code_violation, label="Geometric / Spatial Clash", color="#ef5350")
    p5 = ax.bar(x, timeouts, width, bottom=passes+partials+code_violation+spatial_clash, label="Timeout / Truncation", color="#78909c")

    ax.set_title("Figure 3: Dev-Set Outcome Taxonomy Across 4 Engineering Disciplines", pad=12)
    ax.set_ylabel("Number of Dev Tasks")
    ax.set_xticks(x)
    ax.set_xticklabels(disciplines, fontweight="bold")
    ax.set_ylim(0, 32)
    ax.legend(loc="upper left", frameon=True, fontsize=9)

    # Annotate total tasks on top of bars
    totals = passes + partials + code_violation + spatial_clash + timeouts
    for i, total in enumerate(totals):
        ax.text(i, total + 0.6, f"N={total}", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#37474f")

    out_path = OUT_DIR / "fig3_failure_breakdown.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


def generate_cover_image():
    fig, ax = plt.subplots(figsize=(12, 6.3))
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    # Gradient-like background
    bg = patches.Rectangle((0, 0), 100, 100, facecolor="#0d1b2a")
    ax.add_patch(bg)

    # Accent header bar
    accent = patches.Rectangle((0, 94), 100, 6, facecolor="#1976d2")
    ax.add_patch(accent)

    # Title & Subtitle
    ax.text(50, 78, "ANTIGRAVITY PLE FRONTIER", ha="center", va="center", 
            fontsize=26, fontweight="bold", color="#ffffff")
    ax.text(50, 68, "Autonomous Multi-Role Engineering Harness for Physical-Engineering's Last Exam", 
            ha="center", va="center", fontsize=13, color="#90caf9")

    # Badges row
    badges = [
        ("Discipline Scope", "Structural · Civil · Electrical · Mechanical", "#0288d1"),
        ("Model Backbone", "Claude Opus 5.5 + Gemini 4 Argon", "#7b1fa2"),
        ("Verification", "Licensed PE Independent Audit Loop", "#388e3c"),
        ("Benchmark", "Google PLE-Bench (85 Containerized Tasks)", "#e65100"),
    ]
    for i, (title, val, col) in enumerate(badges):
        bx = 8 + i * 22
        b_patch = patches.FancyBboxPatch((bx, 30), 20, 24, boxstyle="round,pad=1.2", 
                                        facecolor="#1b263b", edgecolor=col, linewidth=2)
        ax.add_patch(b_patch)
        ax.text(bx + 10, 48, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color="#e0e1dd")
        ax.text(bx + 10, 39, val, ha="center", va="center", fontsize=8.5, color="#778da9", wrap=True)

    # Bottom bar
    ax.text(50, 12, "Google $400,000 Hackathon Benchmark · Stage 1 Submission · Team Antigravity", 
            ha="center", va="center", fontsize=10.5, color="#415a77")

    out_path = OUT_DIR / "cover_image_ple_frontier.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


if __name__ == "__main__":
    generate_fig1_architecture()
    generate_fig2_score_cost()
    generate_fig3_failure_breakdown()
    generate_cover_image()

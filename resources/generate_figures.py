import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os

# Data Configuration
data = pd.DataFrame([
    {"Method": "OpenRewrite", "SSR": 62.0, "Hallucination": 0.0, "Cost": 0.00, "Type": "Rule-Based"},
    {"Method": "AgentCoder", "SSR": 59.1, "Hallucination": 10.2, "Cost": 0.12, "Type": "Multi-Agent"},
    {"Method": "GPT-5.1", "SSR": 65.2, "Hallucination": 8.1, "Cost": 0.09, "Type": "Single-Agent"},
    {"Method": "TriArchitect", "SSR": 68.4, "Hallucination": 1.8, "Cost": 0.06, "Type": "Multi-Agent"}
])

output_dir = r"d:\Projects\AI_POCs\TriArchitect-Agent\resources\paper\figures"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Set style
sns.set_theme(style="whitegrid")
colors = {"Rule-Based": "#95a5a6", "Single-Agent": "#3498db", "Multi-Agent": "#2ecc71"}
custom_palette = [colors[x] for x in data["Type"]]

# Figure 3: System Success Rate
plt.figure(figsize=(10, 6))
ax = sns.barplot(x="Method", y="SSR", data=data, palette=custom_palette)
plt.title("System Success Rate (SSR) Comparison", fontsize=16)
plt.ylabel("Success Rate (%)", fontsize=12)
plt.ylim(0, 80)
for p in ax.patches:
    ax.annotate(f'{p.get_height()}%', (p.get_x() + p.get_width() / 2., p.get_height()),
                ha='center', va='center', xytext=(0, 10), textcoords='offset points', fontsize=12, fontweight='bold')
plt.savefig(os.path.join(output_dir, "fig3_success_rate.png"), dpi=300)
plt.close()

# Figure 4: Hallucination Rate
plt.figure(figsize=(10, 6))
# Remove OpenRewrite for this chart or keep it at 0
ax = sns.barplot(x="Method", y="Hallucination", data=data, palette=custom_palette)
plt.title("Hallucination Rate Comparison", fontsize=16)
plt.ylabel("Hallucination Rate (%)", fontsize=12)
plt.ylim(0, 15)
for p in ax.patches:
    ax.annotate(f'{p.get_height()}%', (p.get_x() + p.get_width() / 2., p.get_height()),
                ha='center', va='center', xytext=(0, 10), textcoords='offset points', fontsize=12, fontweight='bold')
plt.savefig(os.path.join(output_dir, "fig4_hallucination_scale.png"), dpi=300)
plt.close()

# Figure 5: Efficiency Frontier (Cost vs SSR)
plt.figure(figsize=(10, 6))
sns.scatterplot(data=data, x="Cost", y="SSR", hue="Method", style="Type", s=200, palette="deep")
plt.title("Efficiency Frontier: Cost vs. Success", fontsize=16)
plt.xlabel("Cost per Task ($)", fontsize=12)
plt.ylabel("Success Rate (%)", fontsize=12)
plt.xlim(-0.02, 0.15)
plt.ylim(40, 75)

# Annotate points
for i, row in data.iterrows():
    plt.text(row["Cost"]+0.005, row["SSR"], row["Method"], fontsize=11, fontweight='bold')

plt.grid(True, linestyle="--", alpha=0.7)
plt.savefig(os.path.join(output_dir, "fig5_efficiency.png"), dpi=300)
plt.close()

print("Figures generated successfully.")

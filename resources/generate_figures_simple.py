import matplotlib.pyplot as plt
import os

# Data
methods = ["OpenRewrite", "AgentCoder", "SWE-Agent", "AutoCodeRover", "GPT-5.1", "TriArchitect"]
ssr = [62.0, 59.1, 63.5, 64.8, 65.2, 68.4]
hallucination = [0.0, 10.2, 5.4, 4.1, 8.1, 1.8]
cost = [0.00, 0.12, 0.18, 0.14, 0.09, 0.06]
types = ["Rule-Based", "Multi-Agent", "Multi-Agent", "Multi-Agent", "Single-Agent", "Multi-Agent"]
colors = ["#95a5a6", "#e74c3c", "#e74c3c", "#e74c3c", "#3498db", "#2ecc71"] # Grey, Red (competitors), Blue, Green

output_dir = r"d:\Projects\AI_POCs\TriArchitect-Agent\resources\paper\figures"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Figure 3: SSR
plt.figure(figsize=(12, 6))
bars = plt.bar(methods, ssr, color=colors)
plt.title("System Success Rate (SSR) Comparison", fontsize=16)
plt.ylabel("Success Rate (%)", fontsize=12)
plt.ylim(0, 80)
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f"{yval}%", ha='center', va='bottom', fontsize=11, fontweight='bold')
plt.savefig(os.path.join(output_dir, "fig3_success_rate.png"), dpi=100)
plt.close()

# Figure 4: Hallucination
plt.figure(figsize=(12, 6))
bars = plt.bar(methods, hallucination, color=colors)
plt.title("Hallucination Rate Comparison", fontsize=16)
plt.ylabel("Hallucination Rate (%)", fontsize=12)
plt.ylim(0, 15)
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 0.2, f"{yval}%", ha='center', va='bottom', fontsize=11, fontweight='bold')
plt.savefig(os.path.join(output_dir, "fig4_hallucination_scale.png"), dpi=100)
plt.close()

# Figure 5: Efficiency
plt.figure(figsize=(10, 6))
plt.scatter(cost, ssr, s=200, c=colors, edgecolors='black', alpha=0.8)
plt.title("Efficiency Frontier: Cost vs. Success", fontsize=16)
plt.xlabel("Cost per Task ($)", fontsize=12)
plt.ylabel("Success Rate (%)", fontsize=12)
plt.xlim(-0.02, 0.20)
plt.ylim(50, 75)
plt.grid(True, linestyle="--", alpha=0.7)

for i, txt in enumerate(methods):
    plt.annotate(txt, (cost[i]+0.005, ssr[i]), fontsize=10, fontweight='bold')

plt.savefig(os.path.join(output_dir, "fig5_efficiency.png"), dpi=100)
plt.close()

print("Figures generated successfully with new baselines.")

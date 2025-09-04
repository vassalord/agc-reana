# pip install uproot matplotlib numpy
import re
import numpy as np
import uproot
import matplotlib.pyplot as plt

ROOT_PATH = "histograms_merged.root"  
CHANNELS = ["4j1b", "4j2b"]

def collect_nominals(file, channel):
    
    out = {}
    
    keys = [k.split(";")[0] for k in file.keys()]
    pat = re.compile(rf"^{re.escape(channel)}_zprimett(\d+)_nominal$")
    for k in keys:
        m = pat.match(k)
        if not m:
            continue
        mass = int(m.group(1))
        values, edges = file[k].to_numpy()  
        out[mass] = (values, edges)
    return out

def plot_channel(ax, nominals, channel, masses, title_suffix):
   
    if not masses:
        ax.text(0.5, 0.5, "No histograms found",
                transform=ax.transAxes, ha="center")
        return

    min_edge = float("inf")
    max_edge = float("-inf")

    for mass in sorted(masses):
        vals, edges = nominals[mass]
        ax.step(edges[:-1], vals, where="post", label=f"{mass} GeV", lw=1.2)
        min_edge = min(min_edge, edges[0])
        max_edge = max(max_edge, edges[-1])

    left = max(0.0, min_edge - 50.0)
    ax.set_xlim(left, max_edge)

    ax.set_xlabel(r"$H_T$ [GeV]")
    ax.set_ylabel("Events")
    ax.set_title(rf"Z′ → t$\bar{{t}}$ masses — {channel} {title_suffix}")
    ax.legend(
        title="Masses",
        loc="upper right",
        fontsize="small",
        title_fontsize="small",
        frameon=True,
        framealpha=0.85,
        ncol=2
    )


def main():
    with uproot.open(ROOT_PATH) as f:
        for ch in CHANNELS:
            nom = collect_nominals(f, ch)
            if not nom:
                print(f"No data for {ch}")
                continue

            
            low_masses = [m for m in nom if 400 <= m <= 2500]
            high_masses = [m for m in nom if m > 2500]

            
            fig1, ax1 = plt.subplots(figsize=(6.2, 4.8))
            plot_channel(ax1, nom, ch, low_masses, "(400–2500 GeV)")
            fig1.tight_layout()
            fig1.savefig(f"zprimett_masses_{ch}_low.png", dpi=130)

            
            fig2, ax2 = plt.subplots(figsize=(6.2, 4.8))
            plot_channel(ax2, nom, ch, high_masses, "(>2500 GeV)")
            fig2.tight_layout()
            fig2.savefig(f"zprimett_masses_{ch}_high.png", dpi=130)

            print(f"Saved: zprimett_masses_{ch}_low.png, zprimett_masses_{ch}_high.png")

if __name__ == "__main__":
    main()

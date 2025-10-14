import uproot
import hist
import matplotlib.pyplot as plt
import os
import numpy as np
import re
import utils.plotting


utils.plotting.set_style()
os.makedirs("png_outputs", exist_ok=True)

FILENAME = "histograms_merged.root"
CHANNELS = ["4j1b", "4j2b"]


PROCESS_ORDER = [
    "single_top_tW",
    "single_top_t_chan",
    "single_top_s_chan",
    "wjets",
    "ttbar",
    "zprimett500",  # example signal just for the variation plots below
]


def normalize_variation(v: str) -> str:
    """Normalize variation name:
       - 'nominal' kept as-is
       - ...Up   -> ..._up
       - ...Down -> ..._down
       - other strings returned unchanged
    """
    if v == "nominal":
        return v
    if v.endswith("Up"):
        return v[:-2] + "_up"
    if v.endswith("Down"):
        return v[:-4] + "_down"
    return v


def parse_key(key: str):
    
    if "_" not in key:
        return None
    channel, rest = key.split("_", 1)

    # Try to match a known process (longest first)
    candidates = sorted(PROCESS_ORDER, key=len, reverse=True)
    proc = None
    var = None
    for p in candidates:
        if rest == p:
            proc = p
            var = "nominal"
            break
        prefix = p + "_"
        if rest.startswith(prefix):
            proc = p
            var = rest[len(prefix):]
            break

    if proc is None:
        # Fallback: assume last '_' separates process and variation
        if "_" not in rest:
            return None
        proc, var = rest.rsplit("_", 1)

    var = normalize_variation(var)
    return channel, proc, var



def load_all_histograms(filename: str):
    """Read all TH1 from a ROOT file and organize them by (channel, process, variation)."""
    file = uproot.open(filename)
    histograms = {}

    for key_with_version in file.keys():
        key = key_with_version.split(";")[0]
        parsed = parse_key(key)
        if not parsed:
            # Key not matching the expected scheme
            continue

        channel, proc, variation = parsed

        try:
            values, edges = file[key_with_version].to_numpy()
        except Exception:
            
            continue

        
        h = hist.Hist.new.Var(edges, name="x").Double()
        
        h.view(flow=False)[...] = values

        histograms.setdefault(channel, {}).setdefault(proc, {})[variation] = h

    return histograms



def plot_stack(hist_dict, channel: str, variation: str, out_file: str, xlabel: str, title: str):
    """Make a stacked plot of the processes in PROCESS_ORDER for one channel & variation."""
    from hist.stack import Stack

    proc_hists = []
    labels = []

    for proc in PROCESS_ORDER:
        if proc in hist_dict and variation in hist_dict[proc]:
            # Light rebin example: by a factor of 2 (adjust/remove as needed)
            h = hist_dict[proc][variation][::hist.rebin(2)]
            proc_hists.append(h)
            labels.append(proc)

    if not proc_hists:
        print(f"[WARN] No histograms found for channel={channel}, variation={variation}")
        return

    stack = Stack(*proc_hists)
    fig, ax = plt.subplots()
    stack.plot(stack=True, histtype="fill", edgecolor="grey", linewidth=1, label=labels, ax=ax)
    ax.legend(frameon=False)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Events")
    fig.tight_layout()
    fig.savefig(out_file, dpi=300)
    plt.close(fig)


def plot_variations(hist_dict):
    
    if "4j1b" in hist_dict and "zprimett500" in hist_dict["4j1b"]:
        base = hist_dict["4j1b"]["zprimett500"].get("nominal")
        if base is not None:
            fig, ax = plt.subplots()
            # Example: slice/rebin on x-axis (120j is a complex step; keep as in the original code)
            base[120j::hist.rebin(2)].plot(label="nominal", linewidth=2, ax=ax)
            for i in range(4):
                var = f"btag_var_{i}_up"
                if var in hist_dict["4j1b"]["zprimett500"]:
                    hist_dict["4j1b"]["zprimett500"][var][120j::hist.rebin(2)].plot(
                        label=f"NP {i+1}", linewidth=2, ax=ax
                    )
            ax.legend(frameon=False)
            ax.set_xlabel(r"$H_T$ [GeV]")
            ax.set_title("b-tagging variations (4j1b, zprimett500)")
            fig.tight_layout()
            fig.savefig("png_outputs/btagging_variations_4j1b_zprimett500.png", dpi=300)
            plt.close(fig)

    
    if "4j2b" in hist_dict and "zprimett500" in hist_dict["4j2b"]:
        base = hist_dict["4j2b"]["zprimett500"].get("nominal")
        if base is not None:
            fig, ax = plt.subplots()
            base.plot(label="nominal", linewidth=2, ax=ax)
            # Try to plot pt_scale_up and pt_res_up if they exist
            if "pt_scale_up" in hist_dict["4j2b"]["zprimett500"]:
                hist_dict["4j2b"]["zprimett500"]["pt_scale_up"].plot(label="scale up", linewidth=2, ax=ax)
            if "pt_res_up" in hist_dict["4j2b"]["zprimett500"]:
                hist_dict["4j2b"]["zprimett500"]["pt_res_up"].plot(label="resolution up", linewidth=2, ax=ax)
            ax.legend(frameon=False)
            ax.set_xlabel(r"$m_{bjj}$ [GeV]")
            ax.set_title("Jet energy variations (4j2b, zprimett500)")
            fig.tight_layout()
            fig.savefig("png_outputs/jet_energy_variations_4j2b_zprimett500.png", dpi=300)
            plt.close(fig)



def find_signals(histograms, prefix="zprimett"):
    """Return sorted list of processes starting with 'prefix' seen in any channel."""
    procs = set()
    for ch in histograms.values():
        for p in ch.keys():
            if p.startswith(prefix):
                procs.add(p)
    return sorted(procs)



if __name__ == "__main__":
    all_hists = load_all_histograms(FILENAME)

    
    if "4j1b" in all_hists:
        plot_stack(
            all_hists["4j1b"], "4j1b", "nominal",
            "png_outputs/final_stack_histogram_4j1b.png",
            r"$H_T$ [GeV]",
            r"$\geq$ 4 jets, 1 b-tag"
        )

    if "4j2b" in all_hists:
        plot_stack(
            all_hists["4j2b"], "4j2b", "nominal",
            "png_outputs/stack_4j2b_nominal.png",
            r"$m_{bjj}$ [GeV]",
            r"$\geq$ 4 jets, $\geq$ 2 b-tags"
        )

    
    plot_variations(all_hists)

    

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
    "zprimett4000"
]

def parse_key(key):
    match = re.match(r"(?P<channel>[^_]+)_(?P<process>.+)_(?P<variation>[^_]+)$", key)
    if not match:
        return None
    return match.group("channel"), match.group("process"), match.group("variation")

def load_all_histograms(filename):
    file = uproot.open(filename)
    histograms = {}

    for key_with_version in file.keys():
        key = key_with_version.split(";")[0]
        parsed = parse_key(key)
        if not parsed:
            continue
        channel, proc, variation = parsed

        try:
            values, edges = file[key_with_version].to_numpy()
        except Exception:
            continue

        h = hist.Hist.new.Reg(len(values), edges[0], edges[-1], name="x").Double()
        h.view(flow=False)[...] = values
        histograms.setdefault(channel, {}).setdefault(proc, {})[variation] = h

    return histograms

def plot_stack(hist_dict, channel, variation, out_file, xlabel, title):
    from hist.stack import Stack

    proc_hists = []
    labels = []
    for proc in PROCESS_ORDER:
        if proc in hist_dict and variation in hist_dict[proc]:
            h = hist_dict[proc][variation][::hist.rebin(2)]
            proc_hists.append(h)
            labels.append(proc)

    if not proc_hists:
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
    if "4j1b" in hist_dict and "ttbar" in hist_dict["4j1b"]:
        base = hist_dict["4j1b"]["ttbar"].get("nominal")
        if base:
            fig, ax = plt.subplots()
            base[120j::hist.rebin(2)].plot(label="nominal", linewidth=2, ax=ax)
            for i in range(4):
                var = f"btag_var_{i}_up"
                if var in hist_dict["4j1b"]["ttbar"]:
                    hist_dict["4j1b"]["ttbar"][var][120j::hist.rebin(2)].plot(label=f"NP {i+1}", linewidth=2, ax=ax)
            ax.legend(frameon=False)
            ax.set_xlabel(r"$H_T$ [GeV]")
            ax.set_title("b-tagging variations")
            fig.tight_layout()
            fig.savefig("png_outputs/btagging_variations_4j1b_ttbar.png", dpi=300)
            plt.close(fig)

    if "4j2b" in hist_dict and "ttbar" in hist_dict["4j2b"]:
        base = hist_dict["4j2b"]["ttbar"].get("nominal")
        if base:
            fig, ax = plt.subplots()
            base.plot(label="nominal", linewidth=2, ax=ax)
            hist_dict["4j2b"]["ttbar"].get("pt_scale_up", base).plot(label="scale up", linewidth=2, ax=ax)
            hist_dict["4j2b"]["ttbar"].get("pt_res_up", base).plot(label="resolution up", linewidth=2, ax=ax)
            ax.legend(frameon=False)
            ax.set_xlabel(r"$m_{bjj}$ [GeV]")
            ax.set_title("Jet energy variations")
            fig.tight_layout()
            fig.savefig("png_outputs/jet_energy_variations_4j2b_ttbar.png", dpi=300)
            plt.close(fig)

if __name__ == "__main__":
    all_hists = load_all_histograms(FILENAME)

    if "4j1b" in all_hists:
        plot_stack(all_hists["4j1b"], "4j1b", "nominal", "png_outputs/final_stack_histogram_4j1b.png",
                   r"$H_T$ [GeV]", r"$\geq$ 4 jets, 1 b-tag")

    if "4j2b" in all_hists:
        plot_stack(all_hists["4j2b"], "4j2b", "nominal", "png_outputs/stack_4j2b_nominal.png",
                   r"$m_{bjj}$ [GeV]", r"$\geq$ 4 jets, $\geq$ 2 b-tags")

    plot_variations(all_hists)

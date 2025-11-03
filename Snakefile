import os
import json

RECAST_DIR = "/eos/user/s/shoienko/REANA_file"
GLOBAL_MERGED = f"{RECAST_DIR}/histograms_merged.root"
GLOBAL_STAMP = "eos_sync.updated"

N_FILES_MAX_PER_SAMPLE = -1

url_prefix = "root://eospublic.cern.ch//eos/opendata"
# To run from Nebraska, you may use:
# url_prefix = "https://xrootd-local.unl.edu:1094//"

def extract_samples_from_json(json_file):
    
    output_files = []
    with open(json_file, "r") as fd:
        data = json.load(fd)
        for sample, conditions in data.items():
            for condition, details in conditions.items():
                sample_name = f"{sample}__{condition}"
                output_files.append(sample_name)
                with open(f"sample_{sample_name}_paths.txt", "w") as path_file:
                    paths = [
                        file_info["path"].replace(
                            "https://xrootd-local.unl.edu:1094//store/user/AGC/nanoAOD",
                            "root://eospublic.cern.ch//eos/opendata/cms/upload/agc/1.0.0/"
                        )
                        for file_info in details["files"]
                    ]
                    path_file.write("\n".join(paths))
    return output_files


def get_file_paths(wildcards, max=N_FILES_MAX_PER_SAMPLE):
    
    with open(f"sample_{wildcards.sample}__{wildcards.condition}_paths.txt") as fd:
        filepaths = fd.read().splitlines()
    outs = [f"histograms/histograms_{wildcards.sample}__{wildcards.condition}__" + fp[38:] for fp in filepaths]
    return outs if max == -1 else outs[:max]


def get_items(json_file):
    """Return list of (sample, condition) tuples."""
    items = []
    with open(json_file, "r") as fd:
        data = json.load(fd)
        for sample, conditions in data.items():
            for condition in conditions:
                items.append((sample, condition))
    return items


# Bootstrap: prepare per-sample path lists
_ = extract_samples_from_json("nanoaod_inputs.json")
ITEMS = get_items("nanoaod_inputs.json")
EVERYTHING_MERGED_ROOTS = [f"everything_merged_{sample}__{condition}.root" for (sample, condition) in ITEMS]

# Mass points to process with Combine
MASSES = [600]


# -------------------------- Workflow --------------------------

rule all:
    input:
        "histograms_merged.root",
        "png_outputs/final_stack_histogram_4j1b.png",
        "png_outputs/stack_4j2b_nominal.png",
        "png_outputs/btagging_variations_4j1b_zprimett500.png",
        "png_outputs/jet_energy_variations_4j2b_zprimett500.png",
        "results/limits.json",
        "results/limit_summary.txt",
        "datacard_by_hand.root",
        expand("combine_plots/impacts_r{m}.pdf", m=MASSES),
        expand("combine_limits/limit_summary_{m}.txt", m=MASSES),
        expand("combine_limits/limits_zprimett{m}.json", m=MASSES),
        expand("combine_plots/likelihood_scan_m{m}.{ext}", m=MASSES, ext=["pdf","png","root"]),
        expand("combine_plots/stacked_plot_shapes_fit_b_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_b_bin4j2b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_prefit_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_prefit_bin4j2b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_s_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_s_bin4j2b_m{m}.png", m=MASSES),
        GLOBAL_STAMP


rule process_sample_one_file_in_sample:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    resources:
        kubernetes_memory_limit="3700Mi"
    input:
        "ttbar_analysis_reana.ipynb"
    output:
        "histograms/histograms_{sample}__{condition}__{filename}"
    params:
        sample_name = '{sample}__{condition}'
    shell:
        "/bin/bash -l && source fix-env.sh && "
        "python prepare_workspace.py sample_{params.sample_name}_{wildcards.filename} && "
        "papermill ttbar_analysis_reana.ipynb sample_{params.sample_name}_{wildcards.filename}_out.ipynb "
        "-p sample_name {params.sample_name} -p filename {url_prefix}{wildcards.filename} -k python3"


rule process_sample:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    resources:
        kubernetes_memory_limit="1850Mi"
    input:
        "file_merging.ipynb",
        get_file_paths
    output:
        "everything_merged_{sample}__{condition}.root"
    params:
        sample_name = '{sample}__{condition}'
    shell:
        "/bin/bash -l && source fix-env.sh && "
        "papermill file_merging.ipynb merged_{params.sample_name}.ipynb "
        "-p sample_name {params.sample_name} -k python3"


rule merging_histograms:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    resources:
        kubernetes_memory_limit="1850Mi"
    input:
        EVERYTHING_MERGED_ROOTS,
        "final_merging.ipynb"
    output:
        "histograms_merged.root"
    params:
        recast_dir = RECAST_DIR,
        global_merged = GLOBAL_MERGED
    shell:
        r'''
        set -e
        /bin/bash -l && source fix-env.sh
        if [ -d "{params.recast_dir}" ]; then
          TGT="{params.global_merged}"
        else
          TGT="histograms_merged.root"
        fi
        export TARGET_ROOT="$TGT"
        papermill final_merging.ipynb result_notebook.ipynb -k python3 -p target_root "$TGT"
        if [ "$TGT" != "histograms_merged.root" ]; then
          cp -f "$TGT" histograms_merged.root || true
        fi
        python - <<'PY'
import os, time, sys
for _ in range(60):
    if os.path.exists("histograms_merged.root") and os.path.getsize("histograms_merged.root") > 0:
        sys.exit(0)
    time.sleep(1)
print("histograms_merged.root not found after wait", file=sys.stderr)
sys.exit(1)
PY
        '''


rule sync_to_eos:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    input:
        "histograms_merged.root"
    output:
        GLOBAL_STAMP
    params:
        recast_dir = RECAST_DIR,
        global_merged = GLOBAL_MERGED
    shell:
        r'''
        set -e
        if [ -d "{params.recast_dir}" ]; then
          printf "%s\n" "$(date) OK: symlink -> {params.global_merged}" > "{output}"
        else
          printf "%s\n" "$(date) LOCAL ONLY: symlink -> histograms_merged.local.root" > "{output}"
        fi
        '''


rule final_stack_histogram:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    input:
        "histograms_merged.root",
        "plot_final_stack.py"
    output:
        "png_outputs/final_stack_histogram_4j1b.png",
        "png_outputs/stack_4j2b_nominal.png",
        "png_outputs/btagging_variations_4j1b_zprimett500.png",
        "png_outputs/jet_energy_variations_4j2b_zprimett500.png"
    shell:
        "/bin/bash -l && source fix-env.sh && python3 plot_final_stack.py"


rule compute_limit:
    """
    Run limit extraction using cabinetry.
    cabinetry_config.yml now points to the local symlink path; no env needed.
    """
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    input:
        "histograms_merged.root",
        "cabinetry_config.yml",
        "cabinetry_fit_limit.py"
    output:
        "results/limits.json",
        "results/limit_summary.txt",
        "workspace.json"
    shell:
        "/bin/bash -l && source fix-env.sh && python3 cabinetry_fit_limit.py"


rule combine:
    container:
        "gitlab-registry.cern.ch/cms-cloud/combine-standalone:latest"
    input:
        "histograms_merged.root",
        "statistical_inference.py",
        "make_mirrored_down.py",
        "datacard_by_hand.txt",
        "combine_scripts/plot1DScan.py",
        "combine_scripts/postFitPlot_new.py"
    output:
        "datacard_by_hand.root",
        expand("combine_plots/likelihood_scan_m{m}.{ext}", m=MASSES, ext=["pdf","png","root"]),
        expand("combine_plots/impacts_r{m}.pdf", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_b_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_b_bin4j2b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_prefit_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_prefit_bin4j2b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_s_bin4j1b_m{m}.png", m=MASSES),
        expand("combine_plots/stacked_plot_shapes_fit_s_bin4j2b_m{m}.png", m=MASSES),
        expand("combine_limits/limit_summary_{m}.txt", m=MASSES),
        expand("combine_limits/limits_zprimett{m}.json", m=MASSES)
    shell:
        r"""
        set -e
        /bin/bash -l && source fix-env.sh
        python3 statistical_inference.py
        """

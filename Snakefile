N_FILES_MAX_PER_SAMPLE = -1
download_sleep = 0
url_prefix = "root://eospublic.cern.ch//eos/opendata"
#In order to run analysis from Nebraska use this prefix
#url_prefix = "https://xrootd-local.unl.edu:1094//" 
import glob
import json
import os

def extract_samples_from_json(json_file):
    output_files = []
    with open(json_file, "r") as fd:
        data = json.load(fd)

        for sample, conditions in data.items():
            for condition, details in conditions.items():
                sample_name = f"{sample}__{condition}"
                output_files.append(sample_name)
                with open(f"sample_{sample_name}_paths.txt", "w") as path_file:
                    paths = [file_info["path"].replace("https://xrootd-local.unl.edu:1094//store/user/AGC/nanoAOD",
                                                       "root://eospublic.cern.ch//eos/opendata/cms/upload/agc/1.0.0/") for file_info in details["files"]]
                    path_file.write("\n".join(paths))

    return output_files
    
def get_file_paths(wildcards, max=N_FILES_MAX_PER_SAMPLE):
    "Return list of at most MAX file paths for the given SAMPLE."
    import json
    import os
    filepaths = []
    fd = open(f"sample_{wildcards.sample}__{wildcards.condition}_paths.txt")
    filepaths = fd.read().splitlines()
    fd.close()
    return [f"histograms/histograms_{wildcards.sample}__{wildcards.condition}__"+filepath[38:] for filepath in filepaths][:max] 

samples = extract_samples_from_json("nanoaod_inputs.json")

def get_items(json_file):
    samples = []
    
    with open(json_file, "r") as fd:
        data = json.load(fd)
        
        for sample, conditions in data.items():
            for condition in conditions:
                samples.append((sample, condition))
    
    return samples 

ITEMS = get_items("nanoaod_inputs.json")
EVERYTHING_MERGED_ROOTS = [f"everything_merged_{sample}__{condition}.root" for (sample, condition) in ITEMS]    

rule all:
    input:
        "histograms_merged.root",
        "png_outputs/final_stack_histogram_4j1b.png",
        "png_outputs/stack_4j2b_nominal.png",
        "png_outputs/btagging_variations_4j1b_ttbar.png",
        "png_outputs/jet_energy_variations_4j2b_ttbar.png",
        "results/limits.json",
        "results/limit_summary.txt"
        

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
        "/bin/bash -l && source fix-env.sh && python prepare_workspace.py sample_{params.sample_name}_{wildcards.filename} && papermill ttbar_analysis_reana.ipynb sample_{params.sample_name}_{wildcards.filename}_out.ipynb -p sample_name {params.sample_name} -p filename {url_prefix}{wildcards.filename} -k python3"

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
        "/bin/bash -l && source fix-env.sh && papermill file_merging.ipynb merged_{params.sample_name}.ipynb -p sample_name {params.sample_name} -k python3"

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
    shell:
        "/bin/bash -l && source fix-env.sh && papermill final_merging.ipynb result_notebook.ipynb -k python3"
        
rule final_stack_histogram:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    input:
        "histograms_merged.root",
        "plot_final_stack.py"
    output:
        "png_outputs/final_stack_histogram_4j1b.png",
        "png_outputs/stack_4j2b_nominal.png",
        "png_outputs/btagging_variations_4j1b_ttbar.png",
        "png_outputs/jet_energy_variations_4j2b_ttbar.png"
    shell:
        "/bin/bash -l && source fix-env.sh && python plot_final_stack.py"

rule compute_limit:
    container:
        "reanahub/reana-demo-agc-cms-ttbar-coffea:1.0.0"
    resources:
        kubernetes_memory_limit="1850Mi"
    input:
        "histograms_merged.root",
        "cabinetry_config.yml",
        "cabinetry_fit_limit.py"
    output:
        "results/limits.json",
        "results/limit_summary.txt",
        "workspace.json"
    shell:
        "/bin/bash -l && source fix-env.sh && python3s cabinetry_fit_limit.py"
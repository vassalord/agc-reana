#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

def run(cmd):
    print(f"\n$ {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    # output dir
    Path("combine_plots").mkdir(parents=True, exist_ok=True)

    # Workaround for combine issue #1049 (harmless if set)
    os.environ.setdefault("CMSSW_BASE", ".")
    os.environ.setdefault("SCRAM_ARCH", ".")

    # 1) Text datacard -> workspace
    #    Adjust the POI mapping as needed (here: ttbar strength r in [0,3])
    run("text2workspace.py datacard_by_hand.txt --PO 'map=.*/zprimett500:r500[1,0,3]'")

    # 2) Impacts (3 steps)
    run("combineTool.py -M Impacts -d datacard_by_hand.root --robustFit 1 --doInitialFit -m 125 --nllbackend legacy")
    run("combineTool.py -M Impacts -d datacard_by_hand.root --robustFit 1 --doFits -m 125")
    run("combineTool.py -M Impacts -d datacard_by_hand.root --robustFit 1 --output impacts.json -m 125")
    run("plotImpacts.py -i impacts.json -o combine_plots/impacts")

    # 3) Prefit / postfit shapes
    run("combine -M FitDiagnostics datacard_by_hand.root --saveShapes --saveWithUncertainties -n FitDiagnosticsStuff")
    for region in ["bin4j1b", "bin4j2b"]:
        for shape in ["shapes_prefit", "shapes_fit_b", "shapes_fit_s"]:
            run(f"python3 combine_scripts/postFitPlot_new.py "
                f"--input_file fitDiagnosticsFitDiagnosticsStuff.root "
                f"--shape_type {shape} --region {region}")

    # 4) Likelihood scan for mu
    run("combine -M MultiDimFit datacard_by_hand.root -n .datacard_by_hand.snapshot --rMin -1 --rMax 4 --saveWorkspace")
    run("combine -M MultiDimFit higgsCombine.datacard_by_hand.snapshot.MultiDimFit.mH120.root "
        "-n .datacard_by_hand --rMin 0 --rMax 2 --algo grid --points 80 --snapshotName MultiDimFit")
    run("combine -M MultiDimFit higgsCombine.datacard_by_hand.snapshot.MultiDimFit.mH120.root "
        "-n .datacard_by_hand.freezeAll --rMin 0 --rMax 2 --algo grid --points 800 "
        "--snapshotName MultiDimFit --freezeParameters allConstrainedNuisances")
    run("python3 combine_scripts/plot1DScan.py "
        "higgsCombine.datacard_by_hand.MultiDimFit.mH120.root "
        "--others 'higgsCombine.datacard_by_hand.freezeAll.MultiDimFit.mH120.root:FreezeAll:2' "
        "-o combine_plots/likelihood_scan --breakdown Syst,Stat")

    print("\n[OK] Done. Plots in combine_plots/")

if __name__ == "__main__":
    main()

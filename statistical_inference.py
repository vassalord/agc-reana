#!/usr/bin/env python3
import os
import json
import subprocess
from pathlib import Path

# MASSES = [400, 500, 600, 700, 800, 900, 1000, 1200]
MASSES = [400]

def run(cmd, check=True):
    print(f"\n$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check)

def freeze_other_pois(m):
    others = [f"r{x}=0" for x in MASSES if x != m]
    setpars = ",".join(others) if others else ""
    freeze = ",".join([f"r{x}" for x in MASSES if x != m]) if len(MASSES) > 1 else ""
    opts = ""
    if setpars:
        opts += f" --setParameters {setpars}"
    if freeze:
        opts += f" --freezeParameters {freeze}"
    return opts

def write_text_summary(json_path, m, out_txt):
    with open(json_path) as f:
        obj = json.load(f)
    
    rec = next(iter(obj.values()))
    obs = rec.get("Observed", None)
    exp = rec.get("Expected", {})
    exp_median = exp.get("50.0", None)
    with open(out_txt, "w") as g:
        g.write(f"POI: zprimett{m}\n")
        if obs is not None:
            g.write(f"Observed 95% CL: {obs}\n")
        if exp_median is not None:
            g.write(f"Expected (median) 95% CL: {exp_median}\n")

def main():
    Path("combine_plots").mkdir(parents=True, exist_ok=True)
    Path("combine_limits").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("CMSSW_BASE", ".")
    os.environ.setdefault("SCRAM_ARCH", ".")

    run("python3 make_mirrored_down.py")

    maps = " ".join([f"--PO 'map=.*/zprimett{m}:r{m}[1,0,3]'" for m in MASSES])
    run(f"text2workspace.py datacard_by_hand.txt "
        f"-P HiggsAnalysis.CombinedLimit.PhysicsModel:multiSignalModel {maps}")

    pois_csv = ",".join([f"r{m}" for m in MASSES])
    run(f"combineTool.py -M Impacts -d datacard_by_hand.root "
        f"--redefineSignalPOIs {pois_csv} --robustFit 1 --doInitialFit -m 125", check=False)
    run(f"combineTool.py -M Impacts -d datacard_by_hand.root "
        f"--redefineSignalPOIs {pois_csv} --robustFit 1 --doFits -m 125", check=False)
    run("combineTool.py -M Impacts -d datacard_by_hand.root --robustFit 1 --output impacts.json -m 125", check=False)
    for m in MASSES:
        run(f"plotImpacts.py -i impacts.json -o combine_plots/impacts_r{m} --POI r{m}", check=False)

    for m in MASSES:
        tag = f"m{m}"
        poi = f"r{m}"
        onepoi = f"--redefineSignalPOIs {poi}"
        freeze = freeze_other_pois(m)

        # Fits + постфіт-плоти
        run(f"combine -M FitDiagnostics datacard_by_hand.root {onepoi}{freeze} "
            f"-n _{tag} --saveShapes -m 125 --cminDefaultMinimizerStrategy 0", check=True)

        for region in ["bin4j1b", "bin4j2b"]:
            for shape in ["shapes_prefit", "shapes_fit_b", "shapes_fit_s"]:
                run("python3 combine_scripts/postFitPlot_new.py "
                    f"--input_file fitDiagnostics_{tag}.root "
                    f"--shape_type {shape} --region {region} --extra_suffix _{tag}", check=True)

        
        run(f"combine -M AsymptoticLimits datacard_by_hand.root {onepoi}{freeze} "
            f"-n _{tag} -m 125", check=True)

        al_root = f"higgsCombine_{tag}.AsymptoticLimits.mH125.root"
        if not os.path.exists(al_root):
            alt = f"higgsCombine{tag}.AsymptoticLimits.mH125.root"
            if os.path.exists(alt):
                al_root = alt

        if os.path.exists(al_root):
          
            out_json = f"combine_limits/limits_zprimett{m}.json"
            run(f"combineTool.py -M CollectLimits {al_root} -o {out_json}", check=True)

           
            out_txt = f"combine_limits/limit_summary_{m}.txt"
            write_text_summary(out_json, m, out_txt)

        
        run(f"combine -M MultiDimFit datacard_by_hand.root {onepoi}{freeze} "
            f"-n .{tag}.snapshot --rMin 0 --rMax 2 --saveWorkspace -m 125")
        run(f"combine -M MultiDimFit higgsCombine.{tag}.snapshot.MultiDimFit.mH125.root "
            f"-n .{tag} --rMin 0 --rMax 2 --algo grid --points 80 --snapshotName MultiDimFit -m 125")
        run(f"combine -M MultiDimFit higgsCombine.{tag}.snapshot.MultiDimFit.mH125.root "
            f"-n .{tag}.freezeAll --rMin 0 --rMax 2 --algo grid --points 800 "
            f"--snapshotName MultiDimFit --freezeParameters allConstrainedNuisances -m 125")
        run("python3 combine_scripts/plot1DScan.py "
            f"higgsCombine.{tag}.MultiDimFit.mH125.root "
            f"--others 'higgsCombine.{tag}.freezeAll.MultiDimFit.mH125.root:FreezeAll:2' "
            f"--POI {poi} "
            f"-o combine_plots/likelihood_scan_{tag} --breakdown Syst,Stat")

    print("\n[OK] Done. Outputs in combine_plots/ and combine_limits/")

if __name__ == "__main__":
    main()

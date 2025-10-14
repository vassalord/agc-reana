# make_mirrored_down.py
#!/usr/bin/env python3
import ROOT

f = ROOT.TFile.Open("histograms_merged.root", "UPDATE")
if not f or f.IsZombie():
    raise RuntimeError("cannot open histograms_merged.root")

systs = ["pt_scale", "pt_res"]
eps = 1e-9

def get(name):
    obj = f.Get(name)
    return obj if obj else None

def make_down(ch, proc, syst):
    hNom = get(f"{ch}_{proc}_nominal")
    if not hNom:
        return False
    hUp = get(f"{ch}_{proc}_{syst}Up") or get(f"{ch}_{proc}_{syst}_up")
    if not hUp:
        return False

    hDown = hNom.Clone(f"{ch}_{proc}_{syst}Down")
    hDown.Add(hUp, -1.0)
    hDown.Scale(2.0)

    for ib in range(1, hDown.GetNbinsX() + 1):
        if hDown.GetBinContent(ib) < 0.0:
            hDown.SetBinContent(ib, 0.0)
            hDown.SetBinError(ib, 0.0)

    int_nom = max(hNom.Integral(), eps)
    int_down = hDown.Integral()

    if int_down > eps:
        hDown.Scale(int_nom / int_down)
    else:
        hDown = hNom.Clone(f"{ch}_{proc}_{syst}Down")

    f.WriteTObject(hDown, hDown.GetName(), "Overwrite")
    return True

created = 0
for key in f.GetListOfKeys():
    name = key.GetName()
    if not name.endswith("_nominal"):
        continue
    parts = name.split("_")
    ch = parts[0]
    proc = "_".join(parts[1:-1])
    for syst in systs:
        if make_down(ch, proc, syst):
            created += 1

print(f"Fixed/created {created} Down histograms")
f.Close()

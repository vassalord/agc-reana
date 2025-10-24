#!/usr/bin/env python3
import os, re, glob, json, argparse
import numpy as np
import matplotlib.pyplot as plt

def parse_summary(path):
    poi = obs = exp_med = None
    try:
        with open(path) as f:
            for line in f:
                s = line.strip()
                if s.startswith("POI:"):
                    poi = s.split(":", 1)[1].strip()
                elif s.startswith("Observed 95% CL:"):
                    try: obs = float(s.split(":", 1)[1])
                    except: obs = None
                elif s.startswith("Expected (median) 95% CL:"):
                    try: exp_med = float(s.split(":", 1)[1])
                    except: exp_med = None
    except FileNotFoundError:
        pass
    return poi, obs, exp_med

def mass_from(fname, poi):
    m = re.search(r"limit_summary[_-](\d+)", os.path.basename(fname))
    if m: return int(m.group(1))
    if poi:
        m = re.search(r"zprimett(\d+)", poi)
        if m: return int(m.group(1))
    return None

def _read_collectlimits_json(path):
    
    with open(path) as f:
        obj = json.load(f)
    
    if isinstance(obj, dict) and len(obj) == 1 and isinstance(next(iter(obj.values())), dict):
        obj = next(iter(obj.values()))
    return obj

def load_bands(mass, dirs):
    """Зчитує [−2σ, −1σ, median, +1σ, +2σ] з CollectLimits JSON."""
    cands = []
    for d in dirs:
        d = d.strip()
        cands += glob.glob(os.path.join(d, f"limits_zprimett{mass}.json"))
        cands += glob.glob(os.path.join(d, f"limits_{mass}.json"))
    for p in cands:
        try:
            obj = _read_collectlimits_json(p)
           
            keys = ("exp-2","exp-1","exp0","exp+1","exp+2")
            if all(k in obj for k in keys):
                return [float(obj["exp-2"]), float(obj["exp-1"]), float(obj["exp0"]),
                        float(obj["exp+1"]), float(obj["exp+2"])]
        except Exception:
            pass
    return None

def load_obs_exp_from_json(mass, dirs):
    """Повертає (obs, exp_median) з CollectLimits JSON, якщо доступно."""
    cands = []
    for d in dirs:
        d = d.strip()
        cands += glob.glob(os.path.join(d, f"limits_zprimett{mass}.json"))
        cands += glob.glob(os.path.join(d, f"limits_{mass}.json"))
    for p in cands:
        try:
            obj = _read_collectlimits_json(p)
            obs = float(obj["obs"]) if "obs" in obj else None
            exp0 = float(obj["exp0"]) if "exp0" in obj else None
            if (obs is not None) or (exp0 is not None):
                return obs, exp0
        except Exception:
            pass
    return None, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summaries_glob", default="combine_limits/limit_summary_*.txt")
    ap.add_argument("--search_json_dirs", default="combine_limits,results,.")
    ap.add_argument("--xlabel", default=r"$m_{Z'}$ [GeV]")
    ap.add_argument("--ylabel", default=r"95% CL upper limit on $\mu$")
    ap.add_argument("--out", default="limits_summary.png")
    ap.add_argument("--title", default="")
    ap.add_argument("--logy", action="store_true")
    args = ap.parse_args()

    search_dirs = [d for d in args.search_json_dirs.split(",") if d]

    rows = []
    
    summary_paths = sorted(glob.glob(args.summaries_glob))
    for p in summary_paths:
        poi, obs, exp_med = parse_summary(p)
        m = mass_from(p, poi)
        if m is None:
            continue
       
        if obs is None or exp_med is None:
            j_obs, j_exp = load_obs_exp_from_json(m, search_dirs)
            if obs is None: obs = j_obs
            if exp_med is None: exp_med = j_exp
        bands = load_bands(m, search_dirs)
        rows.append((m, obs, exp_med, bands))

    
    if not rows:
      
        jsons = []
        for d in search_dirs:
            jsons += glob.glob(os.path.join(d, "limits_zprimett*.json"))
            jsons += glob.glob(os.path.join(d, "limits_*.json"))
        for jp in sorted(set(jsons)):
            
            m = None
            mobj = re.search(r"zprimett(\d+)", os.path.basename(jp))
            if not mobj:
                mobj = re.search(r"limits_(\d+)", os.path.basename(jp))
            if mobj:
                m = int(mobj.group(1))
            if m is None:
                continue
            j_obs, j_exp = load_obs_exp_from_json(m, search_dirs)
            bands = load_bands(m, search_dirs)
            rows.append((m, j_obs, j_exp, bands))

    if not rows:
        raise SystemExit("No inputs found (neither summaries nor JSON).")

    rows.sort(key=lambda x: x[0])
    masses = np.array([r[0] for r in rows], float)
    obs = np.array([r[1] if r[1] is not None else np.nan for r in rows], float)
    exp_med = np.array([r[2] if r[2] is not None else np.nan for r in rows], float)
    bands = [r[3] for r in rows]
    have_bands = any(b is not None for b in bands)

    plt.figure(figsize=(8, 5.2))

    if have_bands:
        exp_m2 = np.array([b[0] if b else np.nan for b in bands], float)
        exp_m1 = np.array([b[1] if b else np.nan for b in bands], float)
        exp_p1 = np.array([b[3] if b else np.nan for b in bands], float)
        exp_p2 = np.array([b[4] if b else np.nan for b in bands], float)
        plt.fill_between(masses, exp_m2, exp_p2, alpha=0.6, color="yellow", label=r"Exp. $\pm2\sigma$")
        plt.fill_between(masses, exp_m1, exp_p1, alpha=0.8, color="lime", label=r"Exp. $\pm1\sigma$")

    
    plt.plot(masses, exp_med, "--", color="black", lw=2, label="Expected")
    plt.plot(masses, obs, "-", color="black", lw=2, label="Observed")

    plt.xlabel(args.xlabel)
    plt.ylabel(args.ylabel)
    if args.title: plt.title(args.title)
    if args.logy:
        plt.yscale("log")
        finite = np.concatenate([np.nan_to_num(obs, nan=np.inf),
                                 np.nan_to_num(exp_med, nan=np.inf)])
        if have_bands:
            finite = np.concatenate([finite,
                                     np.nan_to_num(exp_m2, nan=np.inf),
                                     np.nan_to_num(exp_p2, nan=np.inf)])
        finite = finite[np.isfinite(finite) & (finite > 0)]
        if finite.size:
            plt.ylim(finite.min()/1.8, finite.max()*1.8)

    h, l = plt.gca().get_legend_handles_labels()
    order = [i for name in [r"Exp. $\pm2\sigma$", r"Exp. $\pm1\sigma$", "Expected", "Observed"] if name in l for i in [l.index(name)]]
    if order:
        plt.legend([h[i] for i in order], [l[i] for i in order], loc="best", frameon=False)

    plt.grid(True, which="both", ls=":", alpha=0.4)
    plt.tight_layout()
    plt.savefig(args.out, dpi=200)
    print(f"[OK] saved {args.out}")

if __name__ == "__main__":
    main()

import os
import sys
import json
import types
import pathlib
import math
import numpy as np

import pyhf
import cabinetry
from cabinetry import configuration, templates, workspace, model_utils


# -------------------------- small helpers --------------------------

def _to_py(x):
    import numpy as _np
    if x is None:
        return None
    if isinstance(x, _np.ndarray):
        return x.tolist()
    if isinstance(x, (_np.floating, _np.integer, _np.bool_)):
        return x.item()
    if isinstance(x, (list, tuple)):
        return [_to_py(v) for v in x]
    if isinstance(x, dict):
        return {k: _to_py(v) for k, v in x.items()}
    return x

def set_pyhf_backend():
    
    backend = pyhf.tensor.numpy_backend(precision="64b")

    # Try to get iminuit optimizer (nice to have, but optional)
    default_minimizer = None
    try:
        default_minimizer = pyhf.optimize.minuit_optimizer()
        print("[INFO] iminuit optimizer is available.")
    except Exception as e:
        print(f"[WARN] iminuit not available ({e}). Will use SciPy default optimizer.")

    # Newer pyhf (>=0.6/0.7) accepts default_minimizer=...
    try:
        if default_minimizer is not None:
            pyhf.set_backend(backend, default_minimizer=default_minimizer)
            print("[INFO] Using iminuit via set_backend(default_minimizer=...).")
        else:
            pyhf.set_backend(backend)
            print("[INFO] Using SciPy optimizer (default).")
    except TypeError:
        # Older pyhf: no 'default_minimizer' kwarg supported
        pyhf.set_backend(backend)
        print("[WARN] Your pyhf.set_backend() does not accept 'default_minimizer' (old pyhf).")
        print("[WARN] Falling back to default optimizer (SciPy).")


def try_import_hist():
    """Try to import 'hist'; return module or None."""
    try:
        import hist  # noqa: F401
        return hist
    except Exception as e:
        print(f"[WARN] 'hist' not available ({e}). AGC rebinning may be skipped.")
        return None


def try_import_agc_rebinning_module():
    """
    Import utils/rebinning.py *without* importing the 'utils' package (which pulls xgboost).
    Returns the loaded module or None if not found/could not be loaded.
    """
    repo_root = pathlib.Path(__file__).resolve().parent
    rebin_path = repo_root / "utils" / "rebinning.py"
    if not rebin_path.exists():
        print(f"[WARN] {rebin_path} not found. AGC rebinning will be skipped.")
        return None

    try:
        import importlib.util

        
        utils_pkg = types.ModuleType("utils")
        utils_pkg.__path__ = [str(rebin_path.parent)]
        sys.modules.setdefault("utils", utils_pkg)

        spec = importlib.util.spec_from_file_location("utils.rebinning", str(rebin_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["utils.rebinning"] = mod
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod
    except Exception as e:
        print(f"[WARN] Failed to import AGC rebinning module directly: {e}")
        return None


def build_templates_with_optional_rebin(cfg, merge_factor=2):
    
    used_rebinning = False

    hist_mod = try_import_hist()
    agc_rebin = try_import_agc_rebinning_module()

    if hist_mod is not None and agc_rebin is not None:
        try:
            rebinning_router = agc_rebin.get_cabinetry_rebinning_router(
                cfg,
                rebinning=slice(110j, None, hist_mod.rebin(merge_factor)),
            )
            print(f"[INFO] Building templates with AGC rebinning router (merge {merge_factor}->1)...")
            templates.build(cfg, router=rebinning_router)
            used_rebinning = True
        except Exception as e:
            print(f"[WARN] AGC rebinning failed ({e}). Building without router...")
            templates.build(cfg)
    else:
        print("[INFO] Building templates without rebinning...")
        templates.build(cfg)

    
    try:
        templates.postprocess(cfg)
    except Exception as e:
        print(f"[WARN] templates.postprocess skipped ({e})")

    return used_rebinning


def write_results(poi, observed, expected, used_rebinning, note, ok=True):
    os.makedirs("results", exist_ok=True)

   
    observed_py = _to_py(observed)
    expected_py = _to_py(expected)
    expected_median_py = None
    
    if expected is not None and hasattr(expected, "__len__") and len(expected) >= 3:
        expected_median_py = _to_py(expected[2])

    with open("results/limit_summary.txt", "w") as f:
        f.write(f"POI: {poi}\n")
        f.write(f"Observed 95% CL: {observed_py}\n")
        f.write(f"Expected (median) 95% CL: {expected_median_py}\n")
        f.write(f"AGC_rebinning_applied: {used_rebinning}\n")
        f.write(f"Note: {note}\n")
        f.write(f"Status: {'OK' if ok else 'FALLBACK'}\n")

    with open("results/limits.json", "w") as f:
        json.dump(
            {
                "poi": poi,
                "observed_95": observed_py,
                "expected_median_95": expected_median_py,
                "expected_bands_95": expected_py,
                "AGC_rebinning_applied": used_rebinning,
                "note": note,
                "status": "OK" if ok else "FALLBACK",
            },
            f,
            indent=2,
        )
    print("[OK] results written: results/limit_summary.txt, results/limits.json")


# -------------------------- robust CLs wrapper --------------------------

def robust_observed_limit_scan(model, data, cls_target=0.05, mu_min=0.0, mu_max=50.0, n_steps=200):
    
    bounds = model.config.suggested_bounds()
    par_bounds = bounds
    init_pars = model.config.suggested_init()

    last_cls = None
    last_mu = None
    best_mu = None

    for i in range(n_steps + 1):
        mu = mu_min + (mu_max - mu_min) * (i / n_steps)
        try:
            cls = float(
                pyhf.infer.hypotest(
                    mu, data, model,
                    init_pars=init_pars,
                    par_bounds=par_bounds,
                )
            )
        except pyhf.exceptions.FailedMinimization as e:
            # skip this point
            print(f"[WARN] hypotest FailedMinimization at mu={mu:.3f}: {e}")
            continue
        except Exception as e:
            print(f"[WARN] hypotest error at mu={mu:.3f}: {e}")
            continue

        # keep track of threshold crossing
        if cls <= cls_target:
            best_mu = mu
            break

        last_cls = cls
        last_mu = mu

    return best_mu


# -------------------------- main --------------------------

def main():
    print("[INFO] configuring pyhf backend ...")
    set_pyhf_backend()

    print("[INFO] loading cabinetry_config.yml ...")
    cfg = configuration.load("cabinetry_config.yml")
    templates.collect(cfg)

    # First attempt: rebin merge 2->1
    used_rebinning = build_templates_with_optional_rebin(cfg, merge_factor=2)

    # Build ws and try cabinetry limit
    print("[INFO] building workspace.json ...")
    ws = workspace.build(cfg)
    workspace.save(ws, "workspace.json")
    print("[OK] workspace.json written. AGC_rebinning_applied =", used_rebinning)

    print("[INFO] creating model & data ...")
    model, data = model_utils.model_and_data(ws)
    poi = model.config.poi_name

    # bracket
    lo, hi = model.config.suggested_bounds()[model.config.poi_index]
    lo = max(0.0, float(lo)) if math.isfinite(lo) else 0.0
    hi = float(hi) if math.isfinite(hi) and hi > 0 else 100.0
    bracket = (lo, hi)
    print(f"[INFO] limit bracket for '{poi}': {bracket}")

    # Try standard cabinetry limit
    try:
        print("[INFO] running cabinetry.fit.limit (first try) ...")
        res = cabinetry.fit.limit(
            model, data,
            poi_name=poi,
            bracket=bracket,
            strategy=1,
            maxiter=20000,
        )
        observed = getattr(res, "observed_limit", getattr(res, "upper_limit", None))
        expected = getattr(res, "expected_limit", None)
        write_results(poi, observed, expected, used_rebinning, "standard cabinetry.fit.limit", ok=True)
        return
    except Exception as e:
        print(f"[WARN] first try failed: {e}")

    # Second attempt: rebuild with stronger rebinning (merge 4->1)
    try:
        print("[INFO] retry: stronger rebinning (merge 4->1) ...")
        cfg2 = configuration.load("cabinetry_config.yml")
        templates.collect(cfg2)
        used_rebin2 = build_templates_with_optional_rebin(cfg2, merge_factor=4)
        ws2 = workspace.build(cfg2)
        workspace.save(ws2, "workspace.json")  # overwrite
        model, data = model_utils.model_and_data(ws2)
        print("[INFO] running cabinetry.fit.limit (second try) ...")
        res = cabinetry.fit.limit(
            model, data,
            poi_name=poi,
            bracket=bracket,
            strategy=1,
            maxiter=20000,
        )
        observed = getattr(res, "observed_limit", getattr(res, "upper_limit", None))
        expected = getattr(res, "expected_limit", None)
        note = "cabinetry.fit.limit with stronger rebin (merge 4->1)"
        write_results(poi, observed, expected, used_rebin2, note, ok=True)
        return
    except pyhf.exceptions.FailedMinimization as e:
        print(f"[WARN] second try FailedMinimization: {e}")
    except Exception as e:
        print(f"[WARN] second try failed: {e}")

    # Final fallback: brute scan for observed only (no expected bands)
    print("[INFO] fallback: brute observed CLs scan ...")
    # widen scan range a bit in case bracket was too small
    mu_obs = robust_observed_limit_scan(model, data, cls_target=0.05, mu_min=0.0, mu_max=max(hi, 50.0), n_steps=300)
    note = "fallback brute CLs scan (observed only); expected bands not computed"
    write_results(poi, mu_obs, None, used_rebinning, note, ok=False)


if __name__ == "__main__":
    main()
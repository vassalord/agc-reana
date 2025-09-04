import os, json
import pyhf, cabinetry
from cabinetry import configuration, templates, workspace, model_utils
import numpy as np


pyhf.set_backend(pyhf.tensor.numpy_backend())

cfg = configuration.load("cabinetry_config.yml")
templates.collect(cfg)

ws = workspace.build(cfg)
workspace.save(ws, "workspace.json")

model, data = model_utils.model_and_data(ws)
poi = model.config.poi_name


lower, upper = model.config.suggested_bounds()[model.config.poi_index]
if not np.isfinite(upper) or upper <= 0:
    upper = 100.0

res = cabinetry.fit.limit(
    model, data,
    poi_name=poi,
    bracket=(max(0.0, float(lower)), float(upper)),
    strategy=1,
    maxiter=20000,  
)

observed = getattr(res, "observed_limit", getattr(res, "upper_limit", None))
expected = getattr(res, "expected_limit", None)
expected_median = expected[2] if expected is not None and len(expected) >= 3 else None

print("POI:", poi)
print("Observed 95% CL:", observed)
print("Expected (median) 95% CL:", expected_median)

def to_jsonable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if hasattr(x, "item"):
        try:
            return x.item()
        except Exception:
            pass
    return x

os.makedirs("results", exist_ok=True)

with open("results/limit_summary.txt", "w") as f:
    f.write(f"POI: {poi}\n")
    f.write(f"Observed 95% CL: {observed}\n")
    f.write(f"Expected (median) 95% CL: {expected_median}\n")

with open("results/limits.json", "w") as f:
    json.dump(
        {
            "poi": poi,
            "observed_95": to_jsonable(observed),
            "expected_median_95": to_jsonable(expected_median),
            "expected_bands_95": to_jsonable(expected),  
        },
        f,
        indent=2,
    )

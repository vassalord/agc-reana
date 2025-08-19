# cabinetry_fit_limit.py
import dataclasses, json
import pyhf, cabinetry
from cabinetry import configuration, templates, workspace, model_utils

pyhf.set_backend(pyhf.tensor.numpy_backend(), pyhf.optimize.minuit_optimizer())

cfg = configuration.load("cabinetry_config.yml")

templates.collect(cfg)

ws = workspace.build(cfg)
workspace.save(ws, "workspace.json")

model, data = model_utils.model_and_data(ws)
poi = model.config.poi_name
upper = model.config.suggested_bounds()[model.config.poi_index][1]

res = cabinetry.fit.limit(
    model, data,
    poi_name=poi,
    bracket=(0.0, upper),    # брекет должен охватывать лимит
    strategy=1,
    maxiter=200000,
)

print("POI:", poi)
print("Observed 95% CL:", getattr(res, "observed_limit", getattr(res, "upper_limit", None)))
print("Expected (median) 95% CL:", getattr(res, "expected_limit", None))

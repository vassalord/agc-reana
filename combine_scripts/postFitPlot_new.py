#!/usr/bin/env python3
from __future__ import absolute_import
import argparse
import ctypes
import ROOT
import HiggsAnalysis.CombinedLimit.util.plotting as plot

ROOT.PyConfig.IgnoreCommandLineOptions = True
ROOT.gROOT.SetBatch(True)
plot.ModTDRStyle()

def get(dir_, name):
    obj = dir_.Get(name)
    return obj if obj else None

def first_existing(dir_, names):
    for n in names:
        o = get(dir_, n)
        if o: return o
    return None

def graph_max(g):
    # Compute max from points, avoiding g.GetHistogram() (which needs Draw)
    if not g: return 0.0
    n = g.GetN()
    y = ctypes.c_double(0.0)
    x = ctypes.c_double(0.0)
    ymax = 0.0
    for i in range(n):
        g.GetPoint(i, x, y)
        ymax = max(ymax, y.value + g.GetErrorYhigh(i))
    return ymax

def axis_edges(h1):
    ax = h1.GetXaxis()
    nb = ax.GetNbins()
    # Collect low-edges + last upper edge
    edges = [ax.GetBinLowEdge(i) for i in range(1, nb+1)]
    edges.insert(0, ax.GetXmin())
    edges.append(ax.GetXmax())
    # De-dup & sort (ROOT axes sometimes duplicate xmin as first low-edge)
    edges = sorted(set(edges))
    return edges

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_file", required=True)
    ap.add_argument("--shape_type", required=True, choices=["shapes_prefit","shapes_fit_b","shapes_fit_s"])
    ap.add_argument("--region", required=True)
    ap.add_argument("--extra_suffix", default="")
    args = ap.parse_args()

    f = ROOT.TFile.Open(args.input_file)
    if not f or f.IsZombie():
        raise RuntimeError("cannot open %s" % args.input_file)

    d = f.Get(f"{args.shape_type}/{args.region}")
    if not d:
        raise RuntimeError("missing directory %s/%s" % (args.shape_type, args.region))

    h_bkg = first_existing(d, ["total_background"])
    h_sig = first_existing(d, ["total_signal"])
    g_dat = first_existing(d, ["data", "data_obs", "data_obs_"])

    if not h_bkg:
        raise RuntimeError("total_background not found")
    # Signal may be absent in fit_b / prefit — tolerate it
    if not h_sig:
        h_sig = h_bkg.Clone("empty_signal")
        h_sig.Reset("ICES")
    if not g_dat:
        # also fine: no data graph
        pass

    # Styles
    h_bkg.SetFillColor(ROOT.TColor.GetColor(100,192,232))
    h_bkg.SetLineColor(ROOT.kAzure+2)
    h_sig.SetFillColor(ROOT.kRed)
    h_sig.SetLineColor(ROOT.kRed+1)

    # Stack
    hs = ROOT.THStack("hs", "")
    hs.Add(h_bkg, "hist")
    if h_sig.Integral() > 0:
        hs.Add(h_sig, "hist")

    # Uncertainty band on (bkg+sig)
    h_tot = h_bkg.Clone("h_tot"); h_tot.Add(h_sig)
    h_err = h_tot.Clone("h_err")
    for i in range(1, h_err.GetNbinsX()+1):
        be = h_bkg.GetBinError(i) + 1e-3
        se = h_sig.GetBinError(i) + 1e-3
        h_err.SetBinError(i, (be*be + se*se)**0.5)
    h_err.SetFillColorAlpha(12, 0.30)
    h_err.SetMarkerSize(0)
    h_err.SetLineWidth(0)

    # Optional re-range (use SetRangeUser for TH1)
    xmin, xmax = h_bkg.GetXaxis().GetXmin(), h_bkg.GetXaxis().GetXmax()
    # If you want hard limits like 110–550, uncomment:
    # xmin, xmax = 110.0, 550.0
    for h in (h_bkg, h_sig, h_tot, h_err):
        h.GetXaxis().SetRangeUser(xmin, xmax)

    # Prepare a re-centered data graph (to avoid manual bin_edges off-by-one)
    new_g = None
    if g_dat:
        new_g = ROOT.TGraphAsymmErrors(g_dat.GetN())
        nb = h_bkg.GetNbinsX()
        for i in range(g_dat.GetN()):
            x = ctypes.c_double(0.0)
            y = ctypes.c_double(0.0)
            g_dat.GetPoint(i, x, y)
            # Clamp to histogram binning
            bin_idx = min(i+1, nb)
            xc = h_bkg.GetXaxis().GetBinCenter(bin_idx)
            hw = 0.5*(h_bkg.GetXaxis().GetBinUpEdge(bin_idx) - h_bkg.GetXaxis().GetBinLowEdge(bin_idx))
            new_g.SetPoint(i, xc, y.value)
            new_g.SetPointError(i, hw, hw, g_dat.GetErrorYlow(i), g_dat.GetErrorYhigh(i))
        new_g.SetMarkerStyle(20)
        new_g.SetMarkerSize(1.0)
        new_g.SetLineColor(ROOT.kBlack)

    # Y range
    ymax_h = h_tot.GetMaximum() + h_err.GetBinError(h_err.GetMaximumBin())
    ymax_g = graph_max(new_g if new_g else g_dat)
    ymax = max(ymax_h, ymax_g) if (new_g or g_dat) else ymax_h
    c = ROOT.TCanvas("c","c",900,800)
    c.SetMargin(0.12,0.04,0.12,0.06)
    hs.SetMinimum(0.0)
    hs.SetMaximum(max(1.0, ymax*1.3))
    hs.Draw("HIST")
    hs.GetXaxis().SetTitle(args.region)
    hs.GetYaxis().SetTitle("Events")
    h_err.Draw("E2 SAME")
    if new_g:
        new_g.Draw("P SAME")

    # Legend
    leg = ROOT.TLegend(0.60,0.70,0.90,0.91,"","NBNDC")
    leg.AddEntry(h_bkg, "Background", "F")
    if h_sig.Integral() > 0:
        leg.AddEntry(h_sig, "Z'→tt", "F")
    leg.AddEntry(h_err, "Total uncertainty", "F")
    if new_g: leg.AddEntry(new_g, "Data", "PE")
    leg.SetBorderSize(0); leg.SetFillStyle(0); leg.Draw()

    # Save
    out_png = f"combine_plots/stacked_plot_{args.shape_type}_{args.region}{args.extra_suffix}.png"
    out_pdf = f"combine_plots/stacked_plot_{args.shape_type}_{args.region}{args.extra_suffix}.pdf"
    c.Print(out_png)
    c.Print(out_pdf)
    print("Saved:", out_png, "and", out_pdf)

if __name__ == "__main__":
    main()

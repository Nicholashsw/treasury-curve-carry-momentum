"""Load the canonical strategy harness by executing the notebook's code cells.

Same mechanism scripts/make_figures.py uses, so carry is evaluated on EXACTLY the
machinery that produced the frozen canonical results. No strategy logic is copied.
"""
import json, os, warnings, functools
warnings.simplefilter("ignore")
import matplotlib; matplotlib.use("Agg")

# carry/src/canonical.py -> repo root is two levels up
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NB = os.path.join(REPO, "notebooks", "treasury_curve_pipeline.ipynb")
SRC = os.environ.get("BBG_CSV") or os.path.join(REPO, "data_raw")
SCRATCH = os.path.join(REPO, "carry", "results", "_nb_scratch")


@functools.lru_cache(maxsize=1)
def load():
    os.makedirs(SCRATCH, exist_ok=True)
    os.environ["BBG_CSV"] = SRC
    os.environ["BBG_RESULTS"] = SCRATCH      # never the canonical results/ dir
    with open(NB, encoding="utf-8") as fh:
        nb = json.load(fh)
    ns = {"__name__": "__main__"}
    cwd = os.getcwd(); os.chdir(REPO)
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), "<notebook>", "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns

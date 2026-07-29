"""
sigmaflow.datasets
==================
Auto-discoverable dataset analyzer classes.

All classes in this package that inherit from BaseDataset are automatically
registered by DatasetRegistry at startup — no manual registration required.

Built-in analyzers (by priority)
---------------------------------
doe_dataset         : Design of Experiments data (priority 80)
spc_dataset         : Statistical Process Control time-series (priority 70)
capability_dataset  : Process capability with spec limits (priority 60)
root_cause_dataset  : Pareto / defect count data (priority 50)
logistics_dataset   : Supply chain / delivery data (priority 45)
service_dataset     : Service / call center data (priority 40)
"""
from sigmaflow.datasets.base_dataset import BaseDataset  # noqa: F401

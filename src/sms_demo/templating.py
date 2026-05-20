from pathlib import Path

from starlette.templating import Jinja2Templates

from sms_demo.services.pipeline import (
    intake_is_complete,
    intake_is_processing,
    intake_is_queued,
    intake_latest_extraction,
    intake_latest_partial,
    intake_latest_routing,
    intake_timing_summary,
)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["intake_is_complete"] = intake_is_complete
templates.env.globals["intake_is_processing"] = intake_is_processing
templates.env.globals["intake_is_queued"] = intake_is_queued
templates.env.globals["intake_timing_summary"] = intake_timing_summary
templates.env.globals["intake_latest_extraction"] = intake_latest_extraction
templates.env.globals["intake_latest_routing"] = intake_latest_routing
templates.env.globals["intake_latest_partial"] = intake_latest_partial

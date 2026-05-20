from pathlib import Path

from starlette.templating import Jinja2Templates

from sms_demo.services.pipeline import (
    display_extraction,
    display_partial_referral,
    display_routing,
    intake_is_processing,
    intake_is_queued,
    intake_timing_summary,
)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["display_extraction"] = display_extraction
templates.env.globals["display_partial_referral"] = display_partial_referral
templates.env.globals["display_routing"] = display_routing
templates.env.globals["intake_is_processing"] = intake_is_processing
templates.env.globals["intake_is_queued"] = intake_is_queued
templates.env.globals["intake_timing_summary"] = intake_timing_summary

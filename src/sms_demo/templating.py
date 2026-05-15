from pathlib import Path

from starlette.templating import Jinja2Templates

from sms_demo.services.pipeline import intake_is_processing

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["intake_is_processing"] = intake_is_processing

"""Deliver a live-source preview through the production alert formatter."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from bo3_alert_core import format_alert
home=Path(os.environ.get('HERMES_HOME',str(Path.home()/'.hermes')))
snapshot=json.loads((home/'data/bo3-match-alerts/real_preview.json').read_text())
print(format_alert(snapshot['match'],snapshot['streams'],datetime.now(timezone.utc)))

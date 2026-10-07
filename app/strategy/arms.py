from app.core.models import Decision,TokenSnapshot
from app.strategy.filters import reference_fact_filter

def evaluate_reference(s):
    ok,reason=reference_fact_filter(s);return Decision(arm="reference",eligible=ok,reason=reason)
def evaluate_python_only(s):
    ok,reason=reference_fact_filter(s);return Decision(arm="python_only",eligible=ok,reason=reason,metadata={"note":"baseline only; thresholds require shadow calibration"})
def evaluate_jev_python(s):
    ok,reason=reference_fact_filter(s)
    if not ok:return Decision(arm="jev_python",eligible=False,reason=reason)
    return Decision(arm="jev_python",eligible=False,reason="jev_not_configured_fail_closed")
def evaluate_all(s):return [evaluate_reference(s),evaluate_python_only(s),evaluate_jev_python(s)]

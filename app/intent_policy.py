"""Deterministic enforcement of named application metric definitions."""
import re

def apply_metric_policy(message,intent):
    adjustments=[]
    text=message.lower()
    # An explicit numerical snow amount remains the model's custom threshold.
    custom=bool(re.search(r'\d+(?:\.\d+)?\s*(?:cm|centimet(?:er|re)s?|inches|inch|mm)\b',text))
    if intent.action in ('weather','compare') and re.search(r'\bheavy\s+snow(?:fall)?\b',text) and not custom:
        if intent.hazard!='snow' or intent.threshold!=15:
            adjustments.append('Applied the application definition of heavy snow: daily snowfall >15 cm (illustrative).')
        intent=intent.model_copy(update=dict(hazard='snow',threshold=15.0))
    elif intent.action in ('weather','compare') and intent.hazard=='snow' and re.search(r'\bsnow(?:fall)?\b',text) and not custom and not re.search(r'\b(?:same|previous|that|those)\b',text):
        if intent.threshold not in (None,0):
            adjustments.append('Reset snowfall to the default definition: daily snowfall >0 cm.')
            intent=intent.model_copy(update=dict(threshold=None))
    return intent,adjustments

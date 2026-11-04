from browser.press_options import press_options
from browser.snapshot import PageSnapshot
from browser.interactions import Action


def decision_options(page: PageSnapshot, back_url: str | None = None,
                     extra: dict[str, Action] | None = None) -> dict[str, str]:
    actions = press_options(page)
    for control in page.controls:
        if control.options:
            actions.pop(control.id, None)
    actions.update({key: action.label for key, action in (extra or {}).items()})
    if back_url is not None:
        actions["go_back"] = f"Browser Back: return to {back_url} in this tab to explore another path."
    return {
        **actions,
        "done": (
            "Success: ALL required instructions have been fulfilled and observed. Verify every "
            "requested action, destination, final state, and requested fact. Seeing the information "
            "early is insufficient if an instruction to open a page or perform an action is outstanding."
        ),
        "blocked": "Stop when the goal remains unmet and none of the available actions can advance it.",
    }

"""Route oversized action menus through bounded choices without dropping targets."""

from collections.abc import Callable

from open_router.jev.limits import MAX_CHOICE_OPTIONS


GLOBAL_ACTIONS = {"done", "blocked", "go_back", "scroll_up", "scroll_down"}


def choose_from_menu(prompt: str, options: dict[str, str],
                     ask: Callable[[str, dict[str, str]], str]) -> str:
    if len(options) <= MAX_CHOICE_OPTIONS:
        return ask(prompt, options)
    global_actions = {k: v for k, v in options.items() if k in GLOBAL_ACTIONS}
    targets = [(k, v) for k, v in options.items() if k not in GLOBAL_ACTIONS]
    # Groups cover contiguous DOM-order ranges. Both endpoints give Jev landmarks.
    capacity = MAX_CHOICE_OPTIONS - len(global_actions)
    size = max(32, (len(targets) + capacity - 1) // capacity)
    groups = {f"group_{i // size + 1}": dict(targets[i:i + size]) for i in range(0, len(targets), size)}
    menu = {key: f"Inspect actions {next(iter(group))} ({next(iter(group.values()))}) through "
                 f"{next(reversed(group))} ({next(reversed(group.values()))})"
            for key, group in groups.items()}
    selected = ask(prompt, {**menu, **global_actions})
    if selected in global_actions:
        return selected
    return choose_from_menu(prompt, {**groups[selected], **global_actions}, ask)

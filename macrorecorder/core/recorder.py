"""Keyboard and mouse macro recording and playback helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pynput import keyboard, mouse
from pynput.keyboard import Controller
from pynput.mouse import Controller as MouseController, Button

from .config import DEFAULT_SETTINGS, LOG_FILE, SPECIAL_KEYS
from .storage import load_slots as _load_slots, save_slot as _save_slot

settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
_log: List[Dict[str, Any]] = []
_recording = False
_playing = False
_key_down_time: Optional[float] = None
_mouse_down_time: Optional[float] = None
_last_event_time: Optional[float] = None
_last_move_record_time: float = 0.0
_controller = Controller()
_mouse_controller = MouseController()
_listener: Optional[keyboard.Listener] = None
_mouse_listener: Optional[mouse.Listener] = None


def load_slots() -> List[Dict[str, Any]]:
    """Return all recorded slots from disk."""
    return _load_slots(LOG_FILE)


def is_recording() -> bool:
    return _recording


def is_playing() -> bool:
    return _playing


def toggle_recording(slot_index: int = 0) -> bool:
    """Start or stop recording for the selected slot."""
    global _recording
    if _recording:
        _stop_recording(slot_index)
    else:
        _start_recording()
    return _recording


def play(slot_index: int = 0) -> None:
    """Replay the events stored in the requested slot."""
    global _playing
    if _recording:
        raise RuntimeError("Cannot play back while recording is active.")

    _playing = True
    try:
        slots = load_slots()
        slot = slots[slot_index]

        events = slot.get("events")
        if not events:
            print(f"No events recorded in slot {slot_index + 1}.")
            return

        stored_settings = slot.get("settings", {})
        effective_settings = stored_settings.copy()
        effective_settings.update(settings)

        repetitions = int(effective_settings["repetitions"])
        for _ in range(repetitions):
            for event in events:
                key_name = event["key"]
                action = event["action"]

                default_delay = (
                    effective_settings["alt_tab_delay"]
                    if key_name in ("Key.tab", "Key.alt")
                    else effective_settings["regular_delay"]
                )
                duration = event.get("duration", default_delay)

                if key_name.startswith("Mouse."):
                    if action == "move":
                        x = event.get("x")
                        y = event.get("y")
                        if x is not None and y is not None:
                            _mouse_controller.position = (x, y)
                    else:
                        button_name = key_name.split(".")[1]
                        resolved_button = getattr(Button, button_name, None)
                        if resolved_button is not None:
                            x = event.get("x")
                            y = event.get("y")
                            if x is not None and y is not None:
                                _mouse_controller.position = (x, y)
                            if action == "press":
                                _mouse_controller.press(resolved_button)
                            elif action == "release":
                                _mouse_controller.release(resolved_button)
                else:
                    resolved_key = _resolve_key(key_name)
                    if action == "press":
                        _controller.press(resolved_key)
                    elif action == "release":
                        _controller.release(resolved_key)

                time.sleep(duration)
    finally:
        _playing = False


def clear_slot(slot_index: int) -> None:
    """Clear all recorded events for the selected slot."""
    _save_slot(slot_index, [], settings.copy(), LOG_FILE)


def _start_recording() -> None:
    global _recording, _listener, _mouse_listener, _key_down_time, _mouse_down_time, _last_event_time, _last_move_record_time
    _recording = True
    _log.clear()
    _key_down_time = None
    _mouse_down_time = None
    _last_event_time = None
    _last_move_record_time = 0.0
    _listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    _listener.start()
    _mouse_listener = mouse.Listener(on_click=_on_click, on_move=_on_move)
    _mouse_listener.start()


def _stop_recording(slot_index: int) -> None:
    global _recording, _listener, _mouse_listener
    _recording = False
    if _listener:
        _listener.stop()
        _listener = None
    if _mouse_listener:
        _mouse_listener.stop()
        _mouse_listener = None

    _save_slot(slot_index, _log.copy(), settings.copy(), LOG_FILE)


def _add_event(event: Dict[str, Any]) -> None:
    global _last_event_time
    current_time = time.time()
    if _log and _last_event_time is not None:
        _log[-1]["duration"] = round(current_time - _last_event_time, 3)
    _log.append(event)
    _last_event_time = current_time
    print(event)


def _on_press(key: keyboard.KeyCode | keyboard.Key) -> None:
    if _recording:
        key_name = str(key)
        _add_event({"key": key_name, "action": "press"})


def _on_release(key: keyboard.KeyCode | keyboard.Key) -> None:
    if _recording:
        key_name = str(key)
        _add_event({"key": key_name, "action": "release"})


def _on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
    if not _recording:
        return
    key_name = f"Mouse.{button.name}"
    action = "press" if pressed else "release"
    _add_event({"key": key_name, "action": action, "x": x, "y": y})


def _on_move(x: int, y: int) -> None:
    if not _recording:
        return
    global _last_move_record_time
    current_time = time.time()
    if current_time - _last_move_record_time >= 1.0:
        _add_event({"key": "Mouse.move", "action": "move", "x": x, "y": y})
        _last_move_record_time = current_time


def _resolve_key(key_name: str):
    if key_name in SPECIAL_KEYS:
        return SPECIAL_KEYS[key_name]
    if len(key_name) == 3 and key_name.startswith("'") and key_name.endswith("'"):
        return key_name.strip("'")
    raise ValueError(f"Unknown key: {key_name}")

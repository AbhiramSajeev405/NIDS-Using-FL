"""
Training Timeline Tracker for FL-NIDS.

Records the exact start/end time of every operation (client training,
server aggregation, evaluation, communication) to build a Gantt-style
timeline in the live dashboard.

Usage:
    tracker = TimelineTracker()
    eid = tracker.start_event("Client_01 Training", "training", {"round": 1})
    # ... do work ...
    tracker.end_event(eid)
    timeline = tracker.get_timeline()
"""

import time
import threading
import uuid


class TimelineTracker:
    """Singleton-style training event timeline tracker."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._events = []
        self._active = {}  # event_id -> event dict
        self._event_lock = threading.Lock()

    def start_event(self, name, category, metadata=None):
        """
        Record the start of a timed event.

        Args:
            name: Human-readable event name (e.g., "Client_01 Training R3")
            category: 'training' | 'aggregation' | 'evaluation' |
                      'communication' | 'defense' | 'other'
            metadata: Optional dict of extra info (round, client_id, etc.)

        Returns:
            event_id: str — use this to close the event
        """
        event_id = str(uuid.uuid4())[:8]
        event = {
            "id": event_id,
            "name": name,
            "category": category,
            "start": time.time(),
            "end": None,
            "duration_ms": None,
            "metadata": metadata or {},
        }

        with self._event_lock:
            self._active[event_id] = event

        return event_id

    def end_event(self, event_id):
        """
        Record the end of a timed event.

        Args:
            event_id: The ID returned by start_event()

        Returns:
            The completed event dict, or None if not found
        """
        end_time = time.time()

        with self._event_lock:
            event = self._active.pop(event_id, None)
            if event is None:
                return None

            event["end"] = end_time
            event["duration_ms"] = round((end_time - event["start"]) * 1000, 1)
            self._events.append(event)

        return event

    def log_instant(self, name, category, metadata=None):
        """
        Log an instantaneous event (zero duration).

        Args:
            name: Event name
            category: Event category
            metadata: Optional dict
        """
        now = time.time()
        event = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "category": category,
            "start": now,
            "end": now,
            "duration_ms": 0,
            "metadata": metadata or {},
        }
        with self._event_lock:
            self._events.append(event)

    def get_timeline(self, category=None, last_n=None):
        """
        Get the full event timeline.

        Args:
            category: Filter by category (None = all)
            last_n: Return only the last N events

        Returns:
            List of event dicts sorted by start time
        """
        with self._event_lock:
            events = list(self._events)
            # Include active events as in-progress
            for event in self._active.values():
                e = dict(event)
                e["end"] = time.time()
                e["duration_ms"] = round((e["end"] - e["start"]) * 1000, 1)
                e["in_progress"] = True
                events.append(e)

        if category:
            events = [e for e in events if e["category"] == category]

        events.sort(key=lambda e: e["start"])

        if last_n:
            events = events[-last_n:]

        return events

    def get_summary(self):
        """
        Get summary statistics of the timeline.

        Returns:
            Dict with per-category totals and average durations
        """
        categories = {}
        for event in self._events:
            cat = event["category"]
            if cat not in categories:
                categories[cat] = {"count": 0, "total_ms": 0.0, "events": []}
            categories[cat]["count"] += 1
            if event["duration_ms"] is not None:
                categories[cat]["total_ms"] += event["duration_ms"]

        summary = {}
        for cat, data in categories.items():
            summary[cat] = {
                "count": data["count"],
                "total_ms": round(data["total_ms"], 1),
                "avg_ms": round(data["total_ms"] / data["count"], 1) if data["count"] > 0 else 0,
            }

        summary["_total_events"] = len(self._events)
        summary["_active_events"] = len(self._active)
        return summary

    def get_gantt_data(self, last_n=50):
        """
        Get timeline data formatted for Gantt chart rendering.

        Returns:
            List of {name, category, start_offset_ms, duration_ms, color}
            where start_offset_ms is relative to the first event
        """
        events = self.get_timeline(last_n=last_n)
        if not events:
            return []

        t0 = events[0]["start"]
        color_map = {
            "training": "#00e5ff",
            "aggregation": "#76ff03",
            "evaluation": "#ff6e40",
            "communication": "#ab47bc",
            "defense": "#ffd740",
            "other": "#78909c",
        }

        return [
            {
                "name": e["name"],
                "category": e["category"],
                "start_offset_ms": round((e["start"] - t0) * 1000, 1),
                "duration_ms": e["duration_ms"] or 0,
                "color": color_map.get(e["category"], "#78909c"),
                "in_progress": e.get("in_progress", False),
            }
            for e in events
        ]

    def reset(self):
        """Clear all events and reset state."""
        with self._event_lock:
            self._events.clear()
            self._active.clear()

    @classmethod
    def destroy(cls):
        """Destroy the singleton instance (for testing)."""
        cls._instance = None

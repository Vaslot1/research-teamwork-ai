"""Atomic budget ledger: reserve before each call, settle with actual cost.

spent + reserved never exceed the user-set cap. Timeout/unknown outcomes keep
their reserve in `uncertain` (counts against the cap) until reconciled.
"""
import threading
from datetime import datetime, timezone
from decimal import Decimal

from .storage import atomic_write_json, read_json
from .env import STUDY


class BudgetExceeded(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BudgetLedger:
    def __init__(self, cap_usd):
        self.path = STUDY / "budget" / "ledger.json"
        self.cap = Decimal(str(cap_usd))
        self._lock = threading.Lock()
        self.state = read_json(self.path, None) or {
            "cap_usd": str(self.cap), "spent": "0", "reserved": {},
            "uncertain": {}, "events": []}
        self.state["cap_usd"] = str(self.cap)

    def _save(self):
        atomic_write_json(self.path, self.state)

    def totals(self):
        with self._lock:
            reserved = sum(Decimal(v) for v in self.state["reserved"].values())
            uncertain = sum(Decimal(v) for v in self.state["uncertain"].values())
            spent = Decimal(self.state["spent"])
            return {"cap": str(self.cap), "spent": str(spent),
                    "reserved": str(reserved), "uncertain": str(uncertain),
                    "available": str(self.cap - spent - reserved - uncertain)}

    def reserve(self, request_id, amount):
        amount = Decimal(str(amount))
        with self._lock:
            reserved = sum(Decimal(v) for v in self.state["reserved"].values())
            uncertain = sum(Decimal(v) for v in self.state["uncertain"].values())
            avail = self.cap - Decimal(self.state["spent"]) - reserved - uncertain
            if amount > avail:
                self.state["events"].append(
                    {"ts": _now(), "event": "reserve_denied",
                     "request_id": request_id, "amount": str(amount),
                     "available": str(avail)})
                self._save()
                raise BudgetExceeded(
                    f"need {amount} > available {avail}")
            self.state["reserved"][request_id] = str(amount)
            self.state["events"].append(
                {"ts": _now(), "event": "reserve", "request_id": request_id,
                 "amount": str(amount)})
            self._save()

    def settle(self, request_id, actual_cost):
        """Release reservation; add actual cost to spent."""
        actual_cost = Decimal(str(actual_cost))
        with self._lock:
            self.state["reserved"].pop(request_id, None)
            self.state["spent"] = str(Decimal(self.state["spent"]) + actual_cost)
            self.state["events"].append(
                {"ts": _now(), "event": "settle", "request_id": request_id,
                 "cost": str(actual_cost)})
            self._save()

    def release(self, request_id, why):
        with self._lock:
            amt = self.state["reserved"].pop(request_id, None)
            self.state["events"].append(
                {"ts": _now(), "event": "release", "request_id": request_id,
                 "amount": amt or "0", "why": why})
            self._save()

    def mark_uncertain(self, request_id):
        """Timeout/unknown outcome: keep possible charge against the cap."""
        with self._lock:
            amt = self.state["reserved"].pop(request_id, None)
            if amt is not None:
                self.state["uncertain"][request_id] = amt
            self.state["events"].append(
                {"ts": _now(), "event": "uncertain", "request_id": request_id,
                 "amount": amt})
            self._save()

    def reconcile_uncertain(self, request_id, actual_cost):
        with self._lock:
            self.state["uncertain"].pop(request_id, None)
            self.state["spent"] = str(
                Decimal(self.state["spent"]) + Decimal(str(actual_cost)))
            self.state["events"].append(
                {"ts": _now(), "event": "reconcile", "request_id": request_id,
                 "cost": str(actual_cost)})
            self._save()

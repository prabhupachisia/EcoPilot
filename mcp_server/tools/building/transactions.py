from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Transaction:

    id: int
    started_at: datetime

    snapshot: Any

    changes: list[dict] = field(default_factory=list)

    committed: bool = False
    rolled_back: bool = False


class TransactionMixin:
    """
    Transaction support for reversible building edits.
    """

    # ------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------

    def _initialize_transactions(self) -> None:

        if not hasattr(self, "_transactions"):

            self._transactions: list[Transaction] = []

        if not hasattr(self, "_active_transaction"):

            self._active_transaction: Transaction | None = None

        if not hasattr(self, "_transaction_counter"):

            self._transaction_counter = 0

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def transaction_active(self) -> bool:
        """
        Return whether a transaction is active.
        """

        self._initialize_transactions()

        return self._active_transaction is not None

    def current_transaction(self) -> Transaction | None:
        """
        Return the active transaction.
        """

        self._initialize_transactions()

        return self._active_transaction

    def transaction_history(self) -> list[Transaction]:
        """
        Return completed transaction history.
        """

        self._initialize_transactions()

        return list(self._transactions)

    # ------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------

    def _create_transaction_snapshot(self):

        """
        Create an in-memory copy of the current IDF.
        """

        return deepcopy(self.idf)

        # ------------------------------------------------------------
    # Transaction Control
    # ------------------------------------------------------------

    def begin_transaction(self) -> Transaction:
        """
        Begin a new transaction.

        Raises
        ------
        RuntimeError
            If another transaction is already active.
        """

        self._initialize_transactions()

        if self.transaction_active():
            raise RuntimeError(
                "A transaction is already active."
            )

        self._transaction_counter += 1

        transaction = Transaction(
            id=self._transaction_counter,
            started_at=datetime.utcnow(),
            snapshot=self._create_transaction_snapshot(),
        )

        self._active_transaction = transaction

        return transaction

    def commit(self) -> Transaction:
        """
        Commit the active transaction.

        Returns
        -------
        Transaction
            The committed transaction.
        """

        self._initialize_transactions()

        if not self.transaction_active():
            raise RuntimeError(
                "No active transaction."
            )

        transaction = self._active_transaction

        transaction.committed = True

        self._transactions.append(transaction)

        self._active_transaction = None

        return transaction

    def rollback(self) -> Transaction:
        """
        Restore the model to the state at the beginning
        of the transaction.
        """

        self._initialize_transactions()

        if not self.transaction_active():
            raise RuntimeError(
                "No active transaction."
            )

        transaction = self._active_transaction

        self.idf = deepcopy(
            transaction.snapshot
        )

        transaction.rolled_back = True

        self._transactions.append(transaction)

        self._active_transaction = None

        self._mark_dirty()

        return transaction

    def discard(self) -> None:
        """
        Discard the active transaction without restoring
        the snapshot.
        """

        self._initialize_transactions()

        if not self.transaction_active():
            raise RuntimeError(
                "No active transaction."
            )

        self._active_transaction = None

        # ------------------------------------------------------------
    # Transaction Information
    # ------------------------------------------------------------

    def transaction_count(self) -> int:
        """
        Return the number of completed transactions.
        """

        self._initialize_transactions()

        return len(self._transactions)

    def last_transaction(self) -> Transaction | None:
        """
        Return the most recently completed transaction.
        """

        self._initialize_transactions()

        if not self._transactions:
            return None

        return self._transactions[-1]

    def clear_transaction_history(self) -> None:
        """
        Remove all completed transactions.
        """

        self._initialize_transactions()

        self._transactions.clear()

    # ------------------------------------------------------------
    # Transaction Summary
    # ------------------------------------------------------------

    def transaction_summary(self) -> dict:
        """
        Return information about the transaction system.
        """

        self._initialize_transactions()

        active = self.current_transaction()

        return {
            "active": active is not None,
            "history_length": len(self._transactions),
            "current_id": (
                active.id if active else None
            ),
            "current_changes": (
                len(active.changes)
                if active
                else 0
            ),
        }

    # ------------------------------------------------------------
    # Context Manager
    # ------------------------------------------------------------

    class _TransactionContext:

        def __init__(self, building):

            self._building = building

        def __enter__(self):

            self._building.begin_transaction()

            return self._building

        def __exit__(
            self,
            exc_type,
            exc,
            tb,
        ):

            if exc_type is None:

                self._building.commit()

            else:

                self._building.rollback()

            return False

    def transaction(self):
        """
        Context manager interface.

        Example
        -------
        with building.transaction():

            building.set_people_count(...)
            building.set_lighting_power(...)
        """

        return self._TransactionContext(self)
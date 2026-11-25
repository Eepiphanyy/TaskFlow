"""Reusable Ticket business services."""

from .ticket_assignment import (
    TicketAssignmentAssigneeInvalid,
    TicketAssignmentError,
    TicketAssignmentNotFound,
    TicketAssignmentStateConflict,
    assign_ticket,
)
from .ticket_closing import (
    TicketCloseError,
    TicketCloseNotFound,
    TicketClosePermissionDenied,
    TicketCloseStateConflict,
    close_ticket,
)
from .ticket_creation import (
    TicketCreationError,
    TicketCreatorDepartmentMissing,
    TicketCreatorProfileMissing,
    create_ticket,
)
from .ticket_editing import (
    TicketEditError,
    TicketEditNotFound,
    TicketEditPermissionDenied,
    TicketEditStateConflict,
    update_ticket,
)
from .ticket_processing import (
    TicketProcessError,
    TicketProcessNotFound,
    TicketProcessPermissionDenied,
    TicketProcessStateConflict,
    process_ticket,
)
from .ticket_scope import (
    TicketScopeQueryBuilder,
    get_ticket_queryset_for_permission,
)

__all__ = [
    "TicketAssignmentAssigneeInvalid",
    "TicketAssignmentError",
    "TicketAssignmentNotFound",
    "TicketAssignmentStateConflict",
    "TicketCloseError",
    "TicketCloseNotFound",
    "TicketClosePermissionDenied",
    "TicketCloseStateConflict",
    "TicketCreationError",
    "TicketCreatorDepartmentMissing",
    "TicketCreatorProfileMissing",
    "TicketEditError",
    "TicketEditNotFound",
    "TicketEditPermissionDenied",
    "TicketEditStateConflict",
    "TicketScopeQueryBuilder",
    "TicketProcessError",
    "TicketProcessNotFound",
    "TicketProcessPermissionDenied",
    "TicketProcessStateConflict",
    "assign_ticket",
    "close_ticket",
    "create_ticket",
    "get_ticket_queryset_for_permission",
    "process_ticket",
    "update_ticket",
]

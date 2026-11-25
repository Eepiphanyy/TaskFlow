from .models import RolePermissionScope

DEFAULT_ROLE_CODES = (
    "admin",
    "department_manager",
    "employee",
    "ticket_handler",
)

REQUIRED_PERMISSIONS = (
    ("departments", "view_department"),
    ("departments", "add_department"),
    ("departments", "change_department"),
    ("departments", "delete_department"),
    ("departments", "view_department_members"),
    ("users", "assign_user_department"),
    ("users", "manage_user_roles"),
    ("tickets", "add_ticket"),
    ("tickets", "view_ticket"),
    ("tickets", "change_ticket"),
    ("tickets", "assign_ticket"),
    ("tickets", "process_ticket"),
    ("tickets", "close_ticket"),
)

DEFAULT_ROLE_GRANTS = (
    # admin
    ("admin", "departments", "view_department", RolePermissionScope.ALL),
    ("admin", "departments", "add_department", RolePermissionScope.ALL),
    ("admin", "departments", "change_department", RolePermissionScope.ALL),
    ("admin", "departments", "delete_department", RolePermissionScope.ALL),
    (
        "admin",
        "departments",
        "view_department_members",
        RolePermissionScope.ALL,
    ),
    ("admin", "users", "assign_user_department", RolePermissionScope.ALL),
    ("admin", "users", "manage_user_roles", RolePermissionScope.ALL),
    ("admin", "tickets", "add_ticket", RolePermissionScope.ALL),
    ("admin", "tickets", "view_ticket", RolePermissionScope.ALL),
    ("admin", "tickets", "change_ticket", RolePermissionScope.ALL),
    ("admin", "tickets", "assign_ticket", RolePermissionScope.ALL),
    ("admin", "tickets", "process_ticket", RolePermissionScope.ALL),
    ("admin", "tickets", "close_ticket", RolePermissionScope.ALL),
    # department_manager
    (
        "department_manager",
        "departments",
        "view_department",
        RolePermissionScope.ALL,
    ),
    (
        "department_manager",
        "departments",
        "change_department",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "departments",
        "view_department_members",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "users",
        "assign_user_department",
        RolePermissionScope.DEPARTMENT,
    ),
    ("department_manager", "tickets", "add_ticket", RolePermissionScope.ALL),
    (
        "department_manager",
        "tickets",
        "view_ticket",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "tickets",
        "change_ticket",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "tickets",
        "assign_ticket",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "tickets",
        "process_ticket",
        RolePermissionScope.DEPARTMENT,
    ),
    (
        "department_manager",
        "tickets",
        "close_ticket",
        RolePermissionScope.DEPARTMENT,
    ),
    # employee
    ("employee", "departments", "view_department", RolePermissionScope.ALL),
    ("employee", "tickets", "add_ticket", RolePermissionScope.ALL),
    ("employee", "tickets", "view_ticket", RolePermissionScope.SELF),
    ("employee", "tickets", "change_ticket", RolePermissionScope.SELF),
    # ticket_handler
    (
        "ticket_handler",
        "departments",
        "view_department",
        RolePermissionScope.ALL,
    ),
    ("ticket_handler", "tickets", "add_ticket", RolePermissionScope.ALL),
    ("ticket_handler", "tickets", "view_ticket", RolePermissionScope.SELF),
    (
        "ticket_handler",
        "tickets",
        "process_ticket",
        RolePermissionScope.SELF,
    ),
    ("ticket_handler", "tickets", "close_ticket", RolePermissionScope.SELF),
)

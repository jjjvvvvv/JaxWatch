#!/usr/bin/env python3
"""
Adapter registry for JaxWatch. Central, explicit mapping of adapter keys to callables.
"""

from typing import Callable, Dict, Optional

# Import fetch functions here so the registry is discoverable in CI
from .planning_commission_fetch import fetch as planning_commission_fetch  # noqa: F401
from .infrastructure_fetch import fetch as infrastructure_fetch  # noqa: F401
from .private_development_fetch import fetch as private_development_fetch  # noqa: F401
from .public_projects_fetch import fetch as public_projects_fetch  # noqa: F401
from .city_council_fetch import fetch as city_council_fetch  # noqa: F401
from .ddrb_fetch import fetch as ddrb_fetch  # noqa: F401


ADAPTER_REGISTRY: Dict[str, Callable] = {
    "planning_commission_adapter": planning_commission_fetch,
    "infrastructure_adapter": infrastructure_fetch,
    "private_development_adapter": private_development_fetch,
    "public_projects_adapter": public_projects_fetch,
    "city_council_adapter": city_council_fetch,
    "ddrb_adapter": ddrb_fetch,
}


def get_adapter(name: str) -> Optional[Callable]:
    return ADAPTER_REGISTRY.get(name)

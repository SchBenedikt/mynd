#!/usr/bin/env python3
"""
Test script for additional public API integrations.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.features.integration import (
    DWDClient,
    NINAClient,
    AutobahnClient,
    DashboardDeutschlandClient,
    DeutschlandAtlasClient
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_dwd():
    logger.info("=== Testing DWD API ===")
    client = DWDClient({})
    if client.test_connection():
        logger.info("✓ DWD connection OK")
    else:
        logger.error("✗ DWD connection failed")
        return False

    try:
        stations = client.get_station_overview_extended(["G005"])
        logger.info("✓ DWD stationOverviewExtended fetched (%s keys)", len(stations))
    except Exception as exc:
        logger.error("✗ DWD stationOverviewExtended failed: %s", exc)
        return False

    return True


def test_nina():
    logger.info("=== Testing NINA API ===")
    client = NINAClient({})
    if client.test_connection():
        logger.info("✓ NINA connection OK")
    else:
        logger.error("✗ NINA connection failed")
        return False

    try:
        event_codes = client.get_event_codes()
        logger.info("✓ NINA event codes fetched (%s entries)", len(event_codes))
    except Exception as exc:
        logger.error("✗ NINA event codes failed: %s", exc)
        return False

    try:
        regions = client.get_regional_keys(query='Berlin', limit=5)
        logger.info("✓ NINA regional keys fetched (%s entries)", regions.get('total', 0))
    except Exception as exc:
        logger.error("✗ NINA regional keys failed: %s", exc)
        return False

    try:
        items = regions.get('items', [])
        ars_candidates = []
        if items:
            ars_candidates.append(items[0].get('ars', ''))
        ars_candidates.append('110000000000')

        dashboard_ok = False
        for ars in ars_candidates:
            if not ars:
                continue
            try:
                dashboard = client.get_dashboard(ars)
                warnings = dashboard.get('warnings', []) if isinstance(dashboard, dict) else []
                logger.info("✓ NINA dashboard fetched for %s (%s warnings)", ars, len(warnings))
                dashboard_ok = True
                break
            except Exception as exc:
                logger.warning("NINA dashboard failed for %s: %s", ars, exc)

        if not dashboard_ok:
            raise RuntimeError("No valid ARS available for NINA dashboard")
    except Exception as exc:
        logger.error("✗ NINA dashboard failed: %s", exc)
        return False

    return True


def test_autobahn():
    logger.info("=== Testing Autobahn API ===")
    client = AutobahnClient({})
    if client.test_connection():
        logger.info("✓ Autobahn connection OK")
    else:
        logger.error("✗ Autobahn connection failed")
        return False

    try:
        roads = client.list_roads()
        logger.info("✓ Autobahn road list fetched (%s entries)", len(roads) if isinstance(roads, list) else 0)
    except Exception as exc:
        logger.error("✗ Autobahn list_roads failed: %s", exc)
        return False

    return True


def test_dashboard_deutschland():
    logger.info("=== Testing Dashboard Deutschland API ===")
    client = DashboardDeutschlandClient({})
    if client.test_connection():
        logger.info("✓ Dashboard Deutschland connection OK")
    else:
        logger.error("✗ Dashboard Deutschland connection failed")
        return False

    try:
        data = client.get_dashboard_entries()
        logger.info("✓ Dashboard entries fetched (%s keys)", len(data))
    except Exception as exc:
        logger.error("✗ Dashboard entries failed: %s", exc)
        return False

    return True


def test_deutschland_atlas():
    logger.info("=== Testing Deutschland Atlas API ===")
    client = DeutschlandAtlasClient({})
    if client.test_connection():
        logger.info("✓ Deutschland Atlas connection OK")
    else:
        logger.error("✗ Deutschland Atlas connection failed")
        return False

    try:
        service = client.list_services()[0]
        info = client.get_service_info(service)
        logger.info("✓ Deutschland Atlas service info fetched for %s", service)
        if not info:
            logger.warning("Service info empty for %s", service)
    except Exception as exc:
        logger.error("✗ Deutschland Atlas service info failed: %s", exc)
        return False

    return True


def main():
    results = [
        test_dwd(),
        test_nina(),
        test_autobahn(),
        test_dashboard_deutschland(),
        test_deutschland_atlas()
    ]

    if all(results):
        logger.info("All additional API tests passed")
        return 0

    logger.error("Some additional API tests failed")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

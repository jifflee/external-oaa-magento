"""
================================================================================
CSV LOADER - Data Loading Utilities (Core Module)
================================================================================

PURPOSE:
    Provides CSV loading and data manipulation utilities.
    This is a CORE module - do not modify.

FUNCTIONS:
    load_csv()              - Load CSV file into list of dictionaries
    group_by_application()  - Group rows by Application_FIN_ID
    get_unique_permissions() - Extract unique permission names
    get_application_summary() - Get statistics for each application

================================================================================
"""

import csv
from collections import defaultdict
from typing import Dict, List


def load_csv(filepath: str) -> List[Dict[str, str]]:
    """
    Load CSV file and return list of row dictionaries.

    Handles UTF-8 BOM encoding (common in Excel exports) and strips
    whitespace from all keys and values.

    ARGS:
        filepath: Path to the CSV file

    RETURNS:
        List of dictionaries, one per row, with column headers as keys
    """
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
            rows.append(cleaned_row)
    return rows


def group_by_application(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """
    Group CSV rows by Application_FIN_ID.

    ARGS:
        rows: List of CSV row dictionaries

    RETURNS:
        Dictionary mapping Application_FIN_ID to list of rows
    """
    apps = defaultdict(list)
    for row in rows:
        app_id = row.get('Application_FIN_ID', '').strip()
        if app_id:
            apps[app_id].append(row)
    return dict(apps)


def get_unique_permissions(rows: List[Dict[str, str]]) -> set:
    """
    Extract unique permission names from rows.

    ARGS:
        rows: List of CSV row dictionaries

    RETURNS:
        Set of unique permission strings
    """
    permissions = set()
    for row in rows:
        perm = row.get('Permission', '').strip()
        if perm:
            permissions.add(perm)
    return permissions


def get_application_summary(rows: List[Dict[str, str]]) -> Dict[str, Dict]:
    """
    Get summary statistics for all applications in the data.

    ARGS:
        rows: List of CSV row dictionaries

    RETURNS:
        Dictionary mapping app_id to summary containing:
        - name: Application display name
        - criticality: Criticality level
        - user_count: Number of unique users
        - row_count: Number of CSV rows
        - permissions: List of permission names
    """
    apps = group_by_application(rows)
    summary = {}

    for app_id, app_rows in apps.items():
        first_row = app_rows[0]
        users = set(row.get('User Id', '').strip() for row in app_rows if row.get('User Id'))
        permissions = get_unique_permissions(app_rows)

        summary[app_id] = {
            'name': first_row.get('Application_FIN_Name', app_id),
            'criticality': first_row.get('Application_FIN_Criticality', ''),
            'user_count': len(users),
            'row_count': len(app_rows),
            'permissions': list(permissions)
        }

    return summary

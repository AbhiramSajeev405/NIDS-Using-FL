"""
LSCUDAPORT - Input Validation Utilities
Validation functions for user inputs (Fixes BUG #006).
"""

def validate_positive_float(value_str, name, min_val=0.0, max_val=1.0):
    """Validate and convert string to positive float.

    Args:
        value_str: String to convert
        name: Parameter name for error messages
        min_val: Minimum acceptable value
        max_val: Maximum acceptable value

    Returns:
        tuple: (success: bool, value: float or None)
    """
    try:
        value = float(value_str)
        if value < min_val or value > max_val:
            print(f"Warning: {name} should be between {min_val} and {max_val}")
        return True, value
    except ValueError:
        print(f"Error: Invalid number for {name}")
        return False, None


def validate_positive_int(value_str, name, min_val=1, max_val=1024):
    """Validate and convert string to positive integer.

    Args:
        value_str: String to convert
        name: Parameter name for error messages
        min_val: Minimum acceptable value
        max_val: Maximum acceptable value

    Returns:
        tuple: (success: bool, value: int or None)
    """
    try:
        value = int(value_str)
        if value < min_val or value > max_val:
            print(f"Warning: {name} should be between {min_val} and {max_val}")
        return True, value
    except ValueError:
        print(f"Error: Invalid number for {name}")
        return False, None


def validate_client_id(client_id, valid_clients=None):
    """Validate client ID format and existence.

    Args:
        client_id: Client ID string
        valid_clients: List of valid client IDs (optional)

    Returns:
        bool: True if valid
    """
    if not client_id:
        print("Error: Client ID cannot be empty")
        return False

    # Check format: Client_XX where XX is 01-09
    if not client_id.startswith("Client_"):
        print(f"Error: Client ID must start with 'Client_', got '{client_id}'")
        return False

    number_part = client_id.replace("Client_", "")
    try:
        num = int(number_part)
        if num < 1 or num > 99:
            print(f"Error: Client number must be between 01 and 99, got {number_part}")
            return False
    except ValueError:
        print(f"Error: Invalid client number format: {number_part}")
        return False

    # Check against known clients if provided
    if valid_clients and client_id not in valid_clients:
        print(f"Error: Unknown client '{client_id}'. Valid clients: {valid_clients}")
        return False

    return True


def validate_attack_type(attack_type, valid_types=None):
    """Validate attack type.

    Args:
        attack_type: Attack type string
        valid_types: List of valid attack types (optional)

    Returns:
        bool: True if valid
    """
    if not attack_type:
        print("Error: Attack type cannot be empty")
        return False

    known_attacks = [
        'port_scan', 'ddos', 'c2_beacon',
        'exfiltration', 'label_flip', 'zero_day'
    ]

    if valid_types is None:
        valid_types = known_attacks

    if attack_type not in valid_types:
        print(f"Error: Unknown attack type '{attack_type}'")
        print(f"Valid types: {', '.join(valid_types)}")
        return False

    return True


def validate_port(port_str):
    """Validate network port number.

    Args:
        port_str: Port number as string

    Returns:
        tuple: (success: bool, port: int or None)
    """
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            print(f"Error: Port must be between 1 and 65535, got {port}")
            return False, None
        # Well-known ports (0-1023) require special permissions
        if port < 1024:
            print(f"Warning: Port {port} is a well-known port and may require admin privileges")
        return True, port
    except ValueError:
        print(f"Error: Invalid port number: {port_str}")
        return False, None


def validate_ip_address(ip_str):
    """Validate IP address format.

    Args:
        ip_str: IP address string

    Returns:
        bool: True if valid format
    """
    import re

    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'

    if not re.match(ipv4_pattern, ip_str):
        print(f"Error: Invalid IP address format: {ip_str}")
        return False

    # Check each octet
    octets = ip_str.split('.')
    for octet in octets:
        num = int(octet)
        if num < 0 or num > 255:
            print(f"Error: IP octet must be 0-255, got {num}")
            return False

    return True
